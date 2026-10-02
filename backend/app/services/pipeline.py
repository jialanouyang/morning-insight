"""晨报流水线：抓取 → AI 处理 → 动态追踪 → 生成 → 入库 → 知识库 → 预警 → 推送 → 语音。

对外提供：
- `ensure_default_config(db, user_id)`  首次访问写入默认配置（含老库迁移）
- `config_payload(cfg)`                 把配置整理成 AI 可用的 dict
- `run_pipeline(db, user_id, ...)`      执行完整链路，返回生成的 Report
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..ai import processing
from ..ai.catalog import default_focus_points, default_roles
from ..fetcher import DEFAULT_SOURCES, fetch_all_sources
from ..models import Report, UserConfig
from ..push import PushMessage, default_push_config, dispatch
from ..report import render_report_html
from ..settings import TIMEZONE
from ..utils.text import truncate
from . import alert as alert_service
from . import competitor as competitor_service
from . import knowledge, tts

logger = logging.getLogger("morning_insight.pipeline")

DEFAULT_AI_CONFIG = {
    "base_url": "",
    "api_key": "",
    "model": "gpt-4o-mini",
    "models": [],
    "prompt": "",
    "language": "zh",
    "length": "brief",
    "temperature": 0.45,
    "embedding_provider": "auto",
    "embedding_model": "",
    "tts_model": "tts-1",
}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "time": "07:30",
    "days": "daily",          # daily / weekday / weekly / custom
    "weekday": 1,             # 1=周一
    "cron": "",               # days=custom 时生效，如 "0 7 * * 1-5"
    "timezone": TIMEZONE,
    "periodical": {
        "weekly": {"enabled": False, "weekday": 1, "time": "08:30"},
        "monthly": {"enabled": False, "day": 1, "time": "08:30"},
    },
}

DEFAULT_TTS_CONFIG = {
    "enabled": False,
    "provider": "edge",
    "voice": "zh-CN-XiaoxiaoNeural",
    "format": "mp3",
    "length": "brief",
    "push": False,
}

DEFAULT_KNOWLEDGE_CONFIG = {
    "enabled": True,
    "auto_ingest": True,
    "top_k": 6,
    "embedding_provider": "auto",
    "embedding_model": "",
    "vector_store": "builtin",
}

DEFAULT_FETCH_CONFIG = {
    "since_hours": 24,
    "limit_per_source": 60,
    "use_ai_summary": False,
    "use_ai_classify": False,
    "translate_enabled": False,
    "render_js": False,
}

SECRET_PATHS = [("ai_config", "api_key"), ("push_config", None), ("tts_config", None)]


def ensure_default_config(db: Session, user_id: int) -> UserConfig:
    cfg = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    if cfg is None:
        cfg = UserConfig(
            user_id=user_id,
            industry="",
            industries=[],
            keywords=[],
            focus_points=default_focus_points(),
            roles=default_roles(),
            sources=[dict(s) for s in DEFAULT_SOURCES],
            ai_config=dict(DEFAULT_AI_CONFIG),
            push_config=default_push_config(),
            push_email={},
            schedule=dict(DEFAULT_SCHEDULE),
            template="brief",
            template_config={},
            ui_language="zh",
            report_language="zh",
            translate_enabled=False,
            tts_config=dict(DEFAULT_TTS_CONFIG),
            knowledge_config=dict(DEFAULT_KNOWLEDGE_CONFIG),
            fetch_config=dict(DEFAULT_FETCH_CONFIG),
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        return cfg

    # 老库迁移：把 v0.1 的 push_email 内容并入 push_config.email
    changed = False
    legacy = cfg.push_email or {}
    if legacy.get("smtp_host") and not (cfg.push_config or {}).get("email", {}).get("smtp_host"):
        merged = dict(cfg.push_config or default_push_config())
        email_cfg = dict(merged.get("email") or {})
        email_cfg.update({k: v for k, v in legacy.items() if v not in (None, "")})
        email_cfg["enabled"] = bool(legacy.get("enabled"))
        merged["email"] = email_cfg
        cfg.push_config = merged
        changed = True
    for field_name, default in (
        ("schedule", DEFAULT_SCHEDULE), ("tts_config", DEFAULT_TTS_CONFIG),
        ("knowledge_config", DEFAULT_KNOWLEDGE_CONFIG), ("fetch_config", DEFAULT_FETCH_CONFIG),
    ):
        current = getattr(cfg, field_name) or {}
        merged = {**default, **current}
        if field_name == "schedule":
            merged["periodical"] = {**DEFAULT_SCHEDULE["periodical"], **(current.get("periodical") or {})}
        if merged != current:
            setattr(cfg, field_name, merged)
            changed = True
    if not cfg.focus_points:
        cfg.focus_points = default_focus_points()
        changed = True
    if not cfg.roles:
        cfg.roles = default_roles()
        changed = True
    if not cfg.sources:
        cfg.sources = [dict(s) for s in DEFAULT_SOURCES]
        changed = True
    ai = {**DEFAULT_AI_CONFIG, **(cfg.ai_config or {})}
    if ai != (cfg.ai_config or {}):
        cfg.ai_config = ai
        changed = True
    if changed:
        db.commit()
        db.refresh(cfg)
    return cfg


def combined_push_config(cfg: UserConfig) -> dict:
    return dict(cfg.push_config or {})


def config_payload(cfg: UserConfig, *, tracked_objects: list | None = None) -> dict:
    """整理成 Prompt / 服务可用的配置字典（把 report_language 映射进 ai_config）。"""
    payload = {
        "industry": cfg.industry,
        "industries": cfg.industries or ([cfg.industry] if cfg.industry else []),
        "keywords": cfg.keywords or [],
        "focus_points": cfg.focus_points or [],
        "roles": cfg.roles or [],
        "sources": cfg.sources or [],
        "template": cfg.template or "brief",
        "report_language": cfg.report_language or "zh",
        "ui_language": cfg.ui_language or "zh",
        "translate_enabled": bool(cfg.translate_enabled),
        "tracked_objects": tracked_objects or [],
    }
    ai = dict(cfg.ai_config or {})
    ai.setdefault("report_language", payload["report_language"])
    payload["ai_config"] = ai
    payload.update({k: v for k, v in ai.items() if k in ("length", "prompt")})
    return payload


def _custom_template(cfg) -> str:
    """读取高级用户自定义 HTML/CSS 模板（兼容 html/css 与 custom_html/custom_css 两种键名）。

    模板占位符：{{title}} 标题、{{content}} 正文 HTML、{{accent}} 主题色、{{css}} 样式。
    - 片段（不含 <html>）会自动包一层最小 HTML 骨架，保证导出与预览都是完整文档
    - 只填了 CSS 时会生成默认骨架
    """
    tpl_cfg = cfg.template_config or {}
    html = str(tpl_cfg.get("custom_html") or tpl_cfg.get("html") or "").strip()
    css = str(tpl_cfg.get("custom_css") or tpl_cfg.get("css") or "").strip()
    if not html and not css:
        return ""

    if not html:
        html = "<article><h1>{{title}}</h1>{{content}}</article>"

    if "{{css}}" in html:
        html = html.replace("{{css}}", css)
    elif css:
        if "</head>" in html:
            html = html.replace("</head>", f"<style>{css}</style></head>", 1)
        elif "<style" not in html:
            html = f"<style>{css}</style>\n{html}"

    if "<html" not in html.lower():
        html = (
            '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{{{{title}}}}</title></head><body>{html}</body></html>"
        )
    return html


def run_pipeline(
    db: Session,
    user_id: int,
    push: bool = True,
    *,
    use_ai: bool = True,
    ingest: bool = True,
    tracking: bool = True,
    alerts: bool = True,
    make_tts: bool = False,
) -> Report:
    """执行完整链路并返回生成的晨报。"""
    started = datetime.now(timezone.utc)
    cfg = ensure_default_config(db, user_id)
    fetch_cfg = cfg.fetch_config or {}
    since_hours = int(fetch_cfg.get("since_hours") or 24)

    # 1) 抓取
    articles = fetch_all_sources(
        db, user_id, cfg.sources or [], since_hours=since_hours,
        limit_per_source=int(fetch_cfg.get("limit_per_source") or 60),
    )

    # 2) 可选的 AI 摘要 / 自动分类
    ai_cfg = dict(cfg.ai_config or {})
    if use_ai and articles and fetch_cfg.get("use_ai_summary") and ai_cfg.get("base_url"):
        try:
            articles = processing.summarize_articles(articles[:20], ai_cfg, db=db, user_id=user_id) + articles[20:]
        except Exception as exc:
            logger.warning("批量摘要失败：%s", exc)

    tracked = competitor_service.active_objects(db, user_id) if tracking else []
    tracked_payload = [{"name": o.name, "level": o.level, "keywords": o.keywords or []} for o in tracked]

    if use_ai and articles and fetch_cfg.get("use_ai_classify") and ai_cfg.get("base_url"):
        try:
            classified = processing.classify_articles(articles, config_payload(cfg), db=db, user_id=user_id)
            for row in classified:
                item = articles[row["index"]]
                item["focus_point"] = row.get("focus_point") or ""
                item["category"] = row.get("category") or item.get("category") or ""
                item["importance"] = row.get("importance") or 3
        except Exception as exc:
            logger.warning("自动分类失败：%s", exc)

    # 3) 动态追踪事件沉淀（晨报内的「动态追踪」板块由 Prompt 中的 tracked_objects 驱动）
    if tracking and articles and tracked:
        try:
            competitor_service.run_tracking(db, user_id, config_payload(cfg), articles, use_ai=use_ai)
        except Exception as exc:
            logger.warning("动态追踪失败：%s", exc)

    # 4) 生成晨报
    payload = config_payload(cfg, tracked_objects=tracked_payload)
    error = ""
    if use_ai and ai_cfg.get("base_url"):
        try:
            content_md = processing.generate_report(payload, articles, db=db, user_id=user_id)
        except Exception as exc:
            error = str(exc)
            logger.warning("晨报生成失败，改用结构化兜底：%s", exc)
            content_md = ""
    else:
        error = "AI 配置不完整：请先在「设置 → AI 模型」填写 API 地址与密钥"
        content_md = ""
    if not content_md:
        content_md = _fallback_report(cfg, articles, error)

    today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    first_heading = next((ln for ln in content_md.splitlines() if ln.strip().startswith("# ")), "")
    default_title = (
        f"Morning Insight Briefing {today}"
        if (cfg.report_language or "zh") == "en"
        else f"晨析晨报 {today}"
    )
    title = (first_heading[2:].strip() if first_heading else "") or default_title

    meta = {
        "article_count": len(articles),
        "source_count": len(articles),
        "model": ai_cfg.get("model") or "",
        "template": cfg.template or "brief",
        "generated_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
        "duration_sec": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "error": error,
    }
    content_html = render_report_html(
        content_md, title=title, template=cfg.template or "brief",
        meta={**meta, "industry": cfg.industry, "report_date": today},
        custom_template=_custom_template(cfg),
    )

    report = Report(
        user_id=user_id,
        report_date=today,
        industry=cfg.industry or "",
        title=title[:200],
        template=cfg.template or "brief",
        content_md=content_md,
        content_html=content_html,
        sources_used=[a["url"] for a in articles],
        meta=meta,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # 5) 知识库入库
    if ingest and (cfg.knowledge_config or {}).get("enabled", True):
        try:
            knowledge.ingest_report(db, user_id, report, payload)
        except Exception as exc:
            logger.warning("晨报入库失败：%s", exc)

    # 6) 关键词预警
    if alerts and articles:
        try:
            alert_service.evaluate(db, user_id, payload, articles, use_ai=use_ai, push=push)
        except Exception as exc:
            logger.warning("关键词预警执行失败：%s", exc)

    # 7) 语音晨报
    tts_cfg = cfg.tts_config or {}
    if make_tts or tts_cfg.get("enabled"):
        try:
            asset = tts.full_flow(db, user_id, payload, content_md, report_id=report.id)
            if tts_cfg.get("push"):
                dispatch(
                    db, user_id, combined_push_config(cfg),
                    PushMessage(
                        title=title, content_md=f"语音晨报已生成：{title}",
                        attachments=[{"path": asset.path, "name": f"{title}.{asset.fmt}"}],
                        kind="report",
                    ),
                )
        except Exception as exc:
            logger.warning("语音晨报生成失败：%s", exc)

    # 8) 推送
    if push:
        msg = PushMessage(title=title, content_md=content_md, content_html=content_html, kind="report")
        dispatch(db, user_id, combined_push_config(cfg), msg, report_id=report.id)

    return report


def _fallback_report(cfg: UserConfig, articles: list[dict], error: str) -> str:
    """AI 不可用时的结构化兜底晨报：按关注点分组的原始素材清单（跟随晨报语言）。"""
    today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    is_en = (cfg.report_language or "zh") == "en"
    if is_en:
        lines = [f"# {today} Industry Briefing (Raw Material)", ""]
        if error:
            lines += [f"> AI generation unavailable: {error}", "> Below is the raw material fetched this round. Configure an AI model to get structured briefings.", ""]
        if not articles:
            lines += ["## Key Points", "- No new material was fetched this round. Check your sources in Settings, or widen the time window.", ""]
            return "\n".join(lines)
        lines += ["## Key Points"]
        for a in articles[:5]:
            lines.append(f"- [{a.get('source', '')}] {a.get('title', '')}")
        lines.append("")
        grouped: dict[str, list[dict]] = {}
        for a in articles:
            key = a.get("focus_point") or a.get("category") or "Other Updates"
            grouped.setdefault(key, []).append(a)
        for name, items in grouped.items():
            lines.append(f"## {name}")
            for a in items[:15]:
                line = f"- [{a.get('title', '')}]({a.get('url', '')})"
                if a.get("source"):
                    line += f"（{a['source']}）"
                if a.get("summary"):
                    line += f"：{truncate(a['summary'], 120)}"
                lines.append(line)
            lines.append("")
        return "\n".join(lines)

    lines = [f"# {today} 行业分析晨报（素材版）", ""]
    if error:
        lines += [f"> 未启用 AI 生成：{error}", "> 以下为本轮抓取到的原始素材，配置 AI 模型后将自动生成结构化晨报。", ""]
    if not articles:
        lines += ["## 今日要点", "- 本轮没有抓取到新素材。请在「设置 → 信息源」检查源是否可用，或放宽时间窗口。", ""]
        return "\n".join(lines)

    lines += ["## 今日要点"]
    for a in articles[:5]:
        lines.append(f"- [{a.get('source', '')}] {a.get('title', '')}")
    lines.append("")

    grouped: dict[str, list[dict]] = {}
    for a in articles:
        key = a.get("focus_point") or a.get("category") or "其他动态"
        grouped.setdefault(key, []).append(a)
    for name, items in grouped.items():
        lines.append(f"## {name}")
        for a in items[:15]:
            line = f"- [{a.get('title', '')}]({a.get('url', '')})"
            if a.get("source"):
                line += f"（{a['source']}）"
            if a.get("summary"):
                line += f"：{truncate(a['summary'], 120)}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines)
