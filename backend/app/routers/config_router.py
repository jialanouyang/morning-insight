"""配置路由：用户晨报配置的读取 / 更新，以及信息源与推送渠道的测试工具。

- 密钥类字段（ai_config.api_key、push_config 中标注 secret 的字段）读取时以 "***" 掩码返回；
  更新时若传回 "***" 表示保持原值不变。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..ai.catalog import default_focus_points, default_roles, merge_focus_points
from ..ai.llm import complete_fn
from ..database import get_db
from ..fetcher import DEFAULT_SOURCES, keyword_source, test_source
from ..fetcher.catalog import SEARCH_ENGINES
from ..fetcher.web_source import ai_suggest_selectors
from ..models import User, UserConfig
from ..push import CHANNEL_MAP, PushMessage, merge_push_config, mask_push_config, test_channel
from ..push.channels.webpush import generate_vapid_keys, is_available as webpush_available
from ..security import get_current_user
from ..services.pipeline import DEFAULT_AI_CONFIG, ensure_default_config
from ..services.scheduler import _sync_jobs

logger = logging.getLogger("morning_insight.config")

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigIn(BaseModel):
    industry: str | None = None
    industries: list | None = None
    keywords: list | None = None
    focus_points: list | None = None
    roles: list | None = None
    sources: list | None = None
    ai_config: dict | None = None
    push_config: dict | None = None
    schedule: dict | None = None
    template: str | None = None
    template_config: dict | None = None
    ui_language: str | None = None
    report_language: str | None = None
    translate_enabled: bool | None = None
    tts_config: dict | None = None
    knowledge_config: dict | None = None
    fetch_config: dict | None = None


def _mask_ai(ai: dict) -> dict:
    safe = dict(ai or {})
    if safe.get("api_key"):
        safe["api_key"] = "***"
    return safe


def _merge_ai(current: dict, incoming: dict) -> dict:
    merged = {**DEFAULT_AI_CONFIG, **(current or {})}
    for key, value in (incoming or {}).items():
        if key == "api_key" and value == "***":
            continue
        merged[key] = value
    return merged


def _merge_dict(current: dict | None, incoming: dict | None, keys: list[str] | None = None) -> dict:
    merged = {**(current or {}), **(incoming or {})}
    if keys:
        merged = {k: v for k, v in merged.items() if k in keys or k not in (incoming or {})}
    return merged


@router.get("")
def get_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = ensure_default_config(db, user.id)
    # 老配置可能只剩早期保存的部分关注点（覆盖了内置清单）——自动补齐并回写
    merged = merge_focus_points(cfg.focus_points)
    if merged != (cfg.focus_points or []):
        cfg.focus_points = merged
        db.commit()
    return {
        "industry": cfg.industry or "",
        "industries": cfg.industries or [],
        "keywords": cfg.keywords or [],
        "focus_points": merged,
        "roles": cfg.roles or [],
        "sources": cfg.sources or [],
        "ai_config": _mask_ai(cfg.ai_config or {}),
        "push_config": mask_push_config(cfg.push_config or {}),
        "schedule": cfg.schedule or {},
        "template": cfg.template or "brief",
        "template_config": cfg.template_config or {},
        "ui_language": cfg.ui_language or "zh",
        "report_language": cfg.report_language or "zh",
        "translate_enabled": bool(cfg.translate_enabled),
        "tts_config": cfg.tts_config or {},
        "knowledge_config": cfg.knowledge_config or {},
        "fetch_config": cfg.fetch_config or {},
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else "",
    }


@router.put("")
def update_config(data: ConfigIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = ensure_default_config(db, user.id)
    payload = data.model_dump(exclude_none=True)

    for field in ("industry", "template", "ui_language", "report_language"):
        if field in payload:
            setattr(cfg, field, payload[field])
    for field in ("industries", "keywords", "focus_points", "roles", "sources",
                  "template_config", "schedule", "tts_config", "knowledge_config", "fetch_config"):
        if field in payload:
            setattr(cfg, field, payload[field])
    if "translate_enabled" in payload:
        cfg.translate_enabled = bool(payload["translate_enabled"])
    if "ai_config" in payload:
        cfg.ai_config = _merge_ai(cfg.ai_config, payload["ai_config"])
    if "push_config" in payload:
        cfg.push_config = merge_push_config(cfg.push_config, payload["push_config"])

    db.commit()
    db.refresh(cfg)
    try:
        _sync_jobs()
    except Exception as exc:
        logger.warning("同步定时任务失败：%s", exc)
    return {"ok": True, "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else ""}


@router.post("/reset")
def reset_config(section: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """重置指定配置段（section 为空则重置关注点与角色）。"""
    cfg = ensure_default_config(db, user.id)
    if section == "sources":
        cfg.sources = [dict(s) for s in DEFAULT_SOURCES]
    elif section == "focus_points":
        cfg.focus_points = default_focus_points()
    elif section == "roles":
        cfg.roles = default_roles()
    elif section == "ai_config":
        cfg.ai_config = dict(DEFAULT_AI_CONFIG)
    elif section == "all":
        cfg.industry = ""
        cfg.industries = []
        cfg.keywords = []
        cfg.focus_points = default_focus_points()
        cfg.roles = default_roles()
        cfg.sources = [dict(s) for s in DEFAULT_SOURCES]
        cfg.ai_config = dict(DEFAULT_AI_CONFIG)
    else:
        cfg.focus_points = default_focus_points()
        cfg.roles = default_roles()
    db.commit()
    _sync_jobs()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# 信息源工具
# --------------------------------------------------------------------------- #
class SourceIn(BaseModel):
    source: dict


@router.post("/sources/test")
def source_test(data: SourceIn, user: User = Depends(get_current_user)):
    """测试单个信息源是否能抓到内容，返回样例。"""
    result = test_source(data.source or {})
    return result


class KeywordSourceIn(BaseModel):
    keywords: list[str]
    lang: str = "zh"
    engine: str = "so360"   # 搜索引擎索引后端：so360（默认，国内可达）/ google


@router.post("/sources/from-keywords")
def sources_from_keywords(data: KeywordSourceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按行业关键词批量生成搜索引擎索引源（对应文档「按内容相关性筛」）。

    默认走 360 资讯搜索（服务端渲染，国内网络可达）；
    engine=google 时走 Google News RSS（海外网络可达时使用）。
    """
    cfg = ensure_default_config(db, user.id)
    existing = {s.get("name") for s in (cfg.sources or [])}
    added = []
    for kw in data.keywords:
        kw = (kw or "").strip()
        if not kw:
            continue
        src = keyword_source(kw, data.lang, data.engine)
        if src["name"] in existing:
            continue
        cfg.sources = list(cfg.sources or []) + [src]
        added.append(src)
    cfg.keywords = sorted(set((cfg.keywords or []) + [k.strip() for k in data.keywords if k and k.strip()]))
    db.commit()
    engine_label = SEARCH_ENGINES.get(data.engine, {}).get("label", data.engine)
    return {"ok": True, "added": added, "engines": SEARCH_ENGINES,
            "note": f"关键词源基于「{engine_label}」搜索引擎索引，按内容相关性筛选。"}


class SelectorIn(BaseModel):
    url: str
    fields: list[str] | None = None


@router.post("/sources/ai-selectors")
def ai_selectors(data: SelectorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """让 AI 推断网页源的 CSS 选择器（对应文档「或让 AI 解析」）。"""
    cfg = ensure_default_config(db, user.id)
    ai_cfg = cfg.ai_config or {}
    if not ai_cfg.get("base_url"):
        raise HTTPException(status_code=400, detail="请先在「设置 → AI 模型」配置 API 地址与密钥")
    try:
        selectors = ai_suggest_selectors(data.url, llm_complete=complete_fn(ai_cfg, scene="selector", db=db, user_id=user.id))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"解析失败：{exc}")
    return {"ok": True, "selectors": selectors,
            "source": {"type": "web", "url": data.url, "base_url": data.url, **selectors}}


# --------------------------------------------------------------------------- #
# 推送渠道工具
# --------------------------------------------------------------------------- #
class ChannelTestIn(BaseModel):
    channel: str
    config: dict | None = None
    title: str = "晨析测试推送"


@router.post("/channels/test")
def channel_test(data: ChannelTestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """测试推送渠道。config 为空时使用已保存配置（掩码字段自动回填真实值）。"""
    cfg = ensure_default_config(db, user.id)
    spec = CHANNEL_MAP.get(data.channel)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知渠道：{data.channel}")

    saved = dict((cfg.push_config or {}).get(data.channel) or {})
    incoming = dict(data.config or {})
    secret_keys = {f["key"] for f in spec.fields if f.get("secret")}
    for key in secret_keys:
        if incoming.get(key) in ("***", "", None) and saved.get(key):
            incoming[key] = saved[key]
    config = {**saved, **incoming}

    msg = PushMessage(
        title=data.title,
        content_md="## 测试成功\n\n这是一条来自 **晨析 Morning Insight** 的测试推送。\n\n"
                   "- 渠道配置正确\n- 内容渲染正常\n\n配置完成后，晨报生成时将自动推送到该渠道。",
        kind="test",
    )
    result = test_channel(data.channel, config, msg)
    return {"ok": result.ok, "channel": result.channel, "detail": result.detail}


@router.post("/webpush/keys")
def webpush_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """生成并保存 VAPID 密钥对。"""
    if not webpush_available():
        raise HTTPException(status_code=400, detail="未安装 pywebpush，请执行：pip install pywebpush")
    cfg = ensure_default_config(db, user.id)
    try:
        keys = generate_vapid_keys()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    push_cfg = dict(cfg.push_config or {})
    webpush_cfg = {**(push_cfg.get("webpush") or {}), **keys}
    push_cfg["webpush"] = webpush_cfg
    cfg.push_config = push_cfg
    db.commit()
    return {"ok": True, "public_key": keys["public_key"]}


class SubscribeIn(BaseModel):
    subscription: dict


@router.post("/webpush/subscribe")
def webpush_subscribe(data: SubscribeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = ensure_default_config(db, user.id)
    endpoint = (data.subscription or {}).get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="订阅信息缺少 endpoint")
    push_cfg = dict(cfg.push_config or {})
    webpush_cfg = dict(push_cfg.get("webpush") or {})
    subs = [s for s in (webpush_cfg.get("subscriptions") or []) if s.get("endpoint") != endpoint]
    subs.append(data.subscription)
    webpush_cfg["subscriptions"] = subs
    webpush_cfg["enabled"] = True
    push_cfg["webpush"] = webpush_cfg
    cfg.push_config = push_cfg
    db.commit()
    return {"ok": True, "count": len(subs)}


@router.get("/webpush/key")
def webpush_public_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = ensure_default_config(db, user.id)
    cfg_map = (cfg.push_config or {}).get("webpush") or {}
    return {"available": webpush_available(), "public_key": cfg_map.get("vapid_public_key") or ""}


# --------------------------------------------------------------------------- #
# 大模型连通性测试
# --------------------------------------------------------------------------- #
class AiTestIn(BaseModel):
    model: str = ""


@router.post("/ai/test")
def ai_test(data: AiTestIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """用已保存的 AI 配置实调一次模型，验证地址 / 密钥 / 模型名是否正确。"""
    cfg = ensure_default_config(db, user.id)
    ai_cfg = dict(cfg.ai_config or {})
    if not ai_cfg.get("base_url"):
        raise HTTPException(status_code=400, detail="请先填写 API 地址（base_url）")
    if not ai_cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="请先填写 API Key")
    if data and data.model:
        ai_cfg["model"] = data.model
    try:
        text = complete_fn(ai_cfg, scene="test", db=db, user_id=user.id)(
            "你是一个测试助手，只回复一个词。",
            "请只回复：OK",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"调用失败：{exc}")
    return {
        "ok": True,
        "model": ai_cfg.get("model") or "",
        "detail": (text or "").strip()[:120] or "连接正常",
    }


# --------------------------------------------------------------------------- #
# 用量统计
# --------------------------------------------------------------------------- #
@router.get("/usage")
def usage(days: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """大模型调用与成本概览（成本控制）。"""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select

    from ..models import LLMUsage

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(int(days), 1))
    rows = db.scalars(select(LLMUsage).where(LLMUsage.user_id == user.id, LLMUsage.created_at >= cutoff)).all()
    total_tokens = sum(r.total_tokens or 0 for r in rows)
    total_cost = sum(r.cost or 0 for r in rows)
    by_scene: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    for r in rows:
        for bucket, key in ((by_scene, r.scene or "other"), (by_model, r.model or "unknown")):
            item = bucket.setdefault(key, {"calls": 0, "tokens": 0, "cost": 0.0})
            item["calls"] += 1
            item["tokens"] += r.total_tokens or 0
            item["cost"] += r.cost or 0.0
    return {
        "calls": len(rows),
        "cached_calls": sum(1 for r in rows if r.cached),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "by_scene": by_scene,
        "by_model": by_model,
        "days": days,
    }
