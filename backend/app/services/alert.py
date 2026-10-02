"""关键词预警：命中判定 → 触发条件 → 推送 → 历史留痕。

对应文档 5.8：
- 关键词列表，精确 / 模糊匹配
- 触发条件：出现即推 / 达到频次才推 / 重要来源才推
- 推送渠道复用推送模块
- 冷却时间，避免同一关键词反复推
- 预警历史可查
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import processing
from ..models import Alert, AlertLog, Article
from ..push import PushMessage, dispatch
from ..utils.text import normalize, tokenize_for_search, truncate

logger = logging.getLogger("morning_insight.alert")

IMPORTANT_SOURCE_PRIORITY = 7  # 「重要来源」的判定阈值


def _searchable(article) -> str:
    if isinstance(article, dict):
        return " ".join(str(article.get(k, "")) for k in ("title", "summary", "raw_content"))
    return " ".join([article.title or "", article.summary or "", article.raw_content or ""])


def _article_dict(article) -> dict:
    if isinstance(article, dict):
        return article
    return {
        "title": article.title, "url": article.url, "source": article.source,
        "summary": article.summary, "published_at": article.published_at,
    }


def text_match(keyword: str, text: str, match_type: str) -> bool:
    """纯文本匹配兜底：精确用子串，模糊用归一化子串 + 2-gram 覆盖率。"""
    if not keyword or not text:
        return False
    if match_type == "exact":
        return keyword.lower() in text.lower()
    nk, nt = normalize(keyword), normalize(text)
    if not nk or not nt:
        return False
    if nk in nt:
        return True
    k_tokens = set(tokenize_for_search(keyword))
    if not k_tokens:
        return False
    t_tokens = set(tokenize_for_search(text))
    coverage = len(k_tokens & t_tokens) / len(k_tokens)
    return coverage >= 0.75


def _source_priority_map(cfg: dict) -> dict[str, int]:
    return {
        (s.get("name") or ""): int(s.get("priority") or 0)
        for s in (cfg.get("sources") or [])
    }


def evaluate(
    db: Session,
    user_id: int,
    cfg: dict,
    articles: list,
    *,
    use_ai: bool = True,
    push: bool = True,
) -> list[dict]:
    """评估全部启用预警。返回本轮触发记录列表。"""
    alerts = list(db.scalars(
        select(Alert).where(Alert.user_id == user_id, Alert.enabled == True)  # noqa: E712
    ).all())
    if not alerts or not articles:
        return []

    now = datetime.now(timezone.utc)
    priorities = _source_priority_map(cfg)
    ai_cfg = cfg.get("ai_config") or {}
    fired: list[dict] = []

    for alert in alerts:
        if alert.last_fired_at:
            last = alert.last_fired_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if now - last < timedelta(minutes=max(int(alert.cooldown_minutes or 0), 0)):
                continue

        # 第一步：候选筛选（精确匹配直接文本命中；模糊匹配先粗筛再交 AI 判定）
        candidates: list[int] = []
        for idx, art in enumerate(articles):
            if text_match(alert.keyword, _searchable(art), "exact" if alert.match_type == "exact" else "fuzzy"):
                candidates.append(idx)
        if not candidates:
            continue

        hits = list(candidates)
        reasons: dict[int, str] = {i: "文本命中" for i in candidates}

        if use_ai and alert.match_type == "fuzzy":
            subset = [articles[i] for i in candidates[:20]]
            judged = processing.judge_alerts(
                alert.keyword, alert.match_type,
                [_article_dict(a) for a in subset], ai_cfg, db=db, user_id=user_id,
            )
            if judged:
                subset_hits = [j["index"] for j in judged if j.get("hit")]
                reasons = {candidates[i]: judged[i].get("reason", "AI 判定命中") for i in subset_hits if i < len(candidates)}
                hits = [candidates[i] for i in subset_hits if i < len(candidates)]

        if not hits:
            continue

        # 第二步：触发条件
        if alert.condition == "frequency":
            need = max(int(alert.condition_value or 1), 1)
            if len(hits) < need:
                continue
        elif alert.condition == "source":
            important = [
                i for i in hits
                if priorities.get(str(_article_dict(articles[i]).get("source") or ""), 0) >= IMPORTANT_SOURCE_PRIORITY
            ]
            if not important:
                continue
            hits = important

        # 第三步：留痕 + 推送
        logs = []
        for i in hits[:20]:
            art = _article_dict(articles[i])
            log = AlertLog(
                user_id=user_id, alert_id=alert.id, keyword=alert.keyword,
                title=truncate(art.get("title", ""), 500), url=art.get("url", ""),
                pushed=False, detail=reasons.get(i, ""),
            )
            db.add(log)
            logs.append(log)
        alert.last_fired_at = now
        db.commit()

        if push and logs:
            lines = [f"## 关键词预警：{alert.keyword}", f"匹配方式：{'精确' if alert.match_type == 'exact' else '模糊'}"
                     f"｜触发条件：{ {'always':'出现即推','frequency':'达到频次','source':'重要来源'}.get(alert.condition, alert.condition) }",
                     ""]
            for i in hits[:20]:
                art = _article_dict(articles[i])
                lines.append(f"- {art.get('title', '')}（[{art.get('source', '')}]({art.get('url', '')})）")
                if reasons.get(i):
                    lines.append(f"  > {reasons[i]}")
            msg = PushMessage(
                title=f"【预警】{alert.keyword}",
                content_md="\n".join(lines),
                kind="alert",
            )
            targets = alert.channels if alert.channels else None
            results = dispatch(db, user_id, cfg.get("push_config") or {}, msg, channels=targets)
            ok = any(r.ok for r in results)
            for log in logs:
                log.pushed = ok
            db.commit()
            fired.append({
                "alert_id": alert.id, "keyword": alert.keyword, "hits": len(hits),
                "channels": [r.channel for r in results if r.ok],
                "channel_results": [{"channel": r.channel, "ok": r.ok, "detail": r.detail} for r in results],
                "items": [
                    {"title": _article_dict(articles[i]).get("title", ""),
                     "url": _article_dict(articles[i]).get("url", ""),
                     "reason": reasons.get(i, "")}
                    for i in hits[:20]
                ],
            })
        else:
            fired.append({"alert_id": alert.id, "keyword": alert.keyword, "hits": len(hits),
                          "channels": [], "channel_results": [], "items": []})
    return fired


def history(db: Session, user_id: int, limit: int = 100) -> list[dict]:
    rows = db.scalars(
        select(AlertLog).where(AlertLog.user_id == user_id).order_by(AlertLog.id.desc()).limit(min(limit, 500))
    ).all()
    return [
        {"id": r.id, "alert_id": r.alert_id, "keyword": r.keyword, "title": r.title,
         "url": r.url, "pushed": r.pushed, "detail": r.detail,
         "pushed_at": r.pushed_at.isoformat() if r.pushed_at else ""}
        for r in rows
    ]


def scan_existing_articles(db: Session, user_id: int, cfg: dict, *, limit: int = 200) -> list[dict]:
    """对已入库文章补跑一次预警（用于新建预警规则后立即检查）。"""
    rows = db.scalars(
        select(Article).where(Article.user_id == user_id).order_by(Article.id.desc()).limit(limit)
    ).all()
    return evaluate(db, user_id, cfg, list(rows), push=True)
