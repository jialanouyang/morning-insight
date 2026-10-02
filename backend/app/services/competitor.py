"""动态追踪：关注对象（公司 / 产品）的动作识别、事件沉淀与并列对比。

对应文档 5.7：关注列表增删改、关注级别、自动追踪（新闻/公告/融资/产品更新/高管变动）、
晨报单独板块、重大变化高亮、多对象并列展示。
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import processing
from ..models import Article, Competitor, CompetitorEvent
from ..utils.text import truncate

logger = logging.getLogger("morning_insight.competitor")

EVENT_TYPES = ["新闻", "公告", "融资", "产品更新", "高管变动", "其他"]

# 无 AI 时的关键词规则（兜底）
_RULES = [
    ("融资", ["融资", "投资", "轮", "领投", "估值", "并购", "收购", "IPO", "上市", "raise", "funding", "acquire"]),
    ("产品更新", ["发布", "上线", "推出", "更新", "迭代", "开源", "launch", "release", "unveil"]),
    ("高管变动", ["离职", "加入", "任命", "辞任", "出任", "CEO", "CTO", "CFO", "hire", "appoint", "resign"]),
    ("公告", ["公告", "年报", "季报", "财报", "earnings", "announce"]),
]


def guess_event_type(text: str) -> str:
    lowered = (text or "").lower()
    for etype, words in _RULES:
        if any(w.lower() in lowered for w in words):
            return etype
    return "新闻"


def active_objects(db: Session, user_id: int) -> list[Competitor]:
    return list(db.scalars(
        select(Competitor).where(Competitor.user_id == user_id, Competitor.enabled == True)  # noqa: E712
    ).all())


def run_tracking(db: Session, user_id: int, cfg: dict, articles: list[dict], *, use_ai: bool = True) -> dict:
    """对一批文章做追踪识别并写入 competitor_events。返回统计。"""
    objects = active_objects(db, user_id)
    if not objects or not articles:
        return {"objects": len(objects), "events": 0, "highlights": 0, "items": []}

    obj_payload = [
        {"name": o.name, "level": o.level, "keywords": o.keywords or []} for o in objects
    ]
    matches = []
    if use_ai:
        try:
            matches = processing.recognize_tracking(articles, obj_payload, cfg.get("ai_config") or {}, db=db, user_id=user_id)
        except Exception as exc:
            logger.warning("AI 追踪识别失败，使用关键词兜底：%s", exc)
    if not matches:
        matches = processing.keyword_tracking_fallback(articles, obj_payload)

    name_map = {o.name: o for o in objects}
    by_url = {a.get("url"): a for a in articles}
    created = 0
    highlights = 0
    items: list[dict] = []

    for m in matches:
        obj = name_map.get(m.get("object"))
        if obj is None:
            # AI 可能返回别名，做一次包含匹配
            for name, candidate in name_map.items():
                if name and (name in str(m.get("object") or "") or str(m.get("object") or "") in name):
                    obj = candidate
                    break
        if obj is None:
            continue
        try:
            article = articles[int(m.get("index"))]
        except (TypeError, ValueError, IndexError):
            continue

        url = article.get("url") or ""
        exists = db.scalar(select(CompetitorEvent).where(
            CompetitorEvent.user_id == user_id,
            CompetitorEvent.competitor_id == obj.id,
            CompetitorEvent.url == url,
        ))
        if exists:
            continue

        etype = m.get("event_type") or guess_event_type(article.get("title", ""))
        if etype not in EVENT_TYPES:
            etype = "新闻"
        is_highlight = bool(m.get("is_highlight")) or obj.level == "high" and etype in ("融资", "高管变动", "产品更新")
        row = CompetitorEvent(
            user_id=user_id, competitor_id=obj.id, article_id=None,
            event_type=etype, title=truncate(article.get("title", ""), 500), url=url,
            source=article.get("source", ""),
            is_highlight=is_highlight,
            event_date=(article.get("published_at") or "")[:19] or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        db.add(row)
        created += 1
        highlights += 1 if is_highlight else 0
        items.append({
            "object": obj.name, "level": obj.level, "event_type": etype,
            "title": row.title, "url": url, "is_highlight": is_highlight,
            "one_line": m.get("one_line") or row.title,
        })
        obj.last_seen_at = row.event_date
    db.commit()
    return {"objects": len(objects), "events": created, "highlights": highlights, "items": items}


def build_section(db: Session, user_id: int, articles: list[dict], cfg: dict) -> str:
    """生成晨报里的「动态追踪」板块 Markdown（无追踪对象时返回空串）。"""
    result = run_tracking(db, user_id, cfg, articles)
    items = result.get("items") or []
    if not items:
        return ""
    grouped: dict[str, list[dict]] = {}
    for it in items:
        grouped.setdefault(it["object"], []).append(it)

    lines = ["## 动态追踪"]
    for name, entries in grouped.items():
        level = entries[0].get("level")
        lines.append(f"### {name}{'（重点）' if level == 'high' else ''}")
        for e in entries:
            flag = "**" if e.get("is_highlight") else ""
            lines.append(f"- {flag}[{e['event_type']}] {e['one_line']}（[来源]({e['url']})）{flag}")
    return "\n".join(lines)


def compare(db: Session, user_id: int, *, days: int = 30) -> list[dict]:
    """多对象并列对比：各自在时间窗内的事件数量与最新动作。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(days, 1))).strftime("%Y-%m-%d")
    objects = list(db.scalars(select(Competitor).where(Competitor.user_id == user_id)).all())
    out: list[dict] = []
    for obj in objects:
        events = list(db.scalars(
            select(CompetitorEvent)
            .where(CompetitorEvent.user_id == user_id, CompetitorEvent.competitor_id == obj.id,
                   CompetitorEvent.created_at >= datetime.now(timezone.utc) - timedelta(days=max(days, 1)))
            .order_by(CompetitorEvent.id.desc())
        ).all())
        counts: dict[str, int] = {}
        for e in events:
            counts[e.event_type] = counts.get(e.event_type, 0) + 1
        out.append({
            "id": obj.id,
            "name": obj.name,
            "type": obj.type,
            "level": obj.level,
            "enabled": obj.enabled,
            "keywords": obj.keywords or [],
            "event_count": len(events),
            "highlight_count": sum(1 for e in events if e.is_highlight),
            "by_type": counts,
            "last_seen_at": obj.last_seen_at,
            "latest": [
                {"event_type": e.event_type, "title": e.title, "url": e.url,
                 "is_highlight": e.is_highlight, "event_date": e.event_date}
                for e in events[:3]
            ],
        })
    out.sort(key=lambda x: (-x["highlight_count"], -x["event_count"]))
    return out


def timeline(db: Session, user_id: int, competitor_id: int, limit: int = 100) -> list[dict]:
    rows = db.scalars(
        select(CompetitorEvent)
        .where(CompetitorEvent.user_id == user_id, CompetitorEvent.competitor_id == competitor_id)
        .order_by(CompetitorEvent.id.desc())
        .limit(min(limit, 500))
    ).all()
    return [
        {"id": e.id, "event_type": e.event_type, "title": e.title, "url": e.url,
         "source": e.source, "is_highlight": e.is_highlight, "event_date": e.event_date,
         "created_at": e.created_at.isoformat() if e.created_at else ""}
        for e in rows
    ]
