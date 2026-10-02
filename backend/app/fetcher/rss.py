"""RSS / Atom 源抓取。"""
import logging
from datetime import timedelta

import feedparser

from ..utils.text import strip_html, truncate
from .core import http_get, make_item, now_utc, parse_datetime

logger = logging.getLogger("morning_insight.fetcher.rss")


def _entry_body(entry) -> str:
    for key in ("content", "summary_detail", "summary"):
        value = entry.get(key)
        if isinstance(value, list) and value:
            return value[0].get("value", "")
        if isinstance(value, dict):
            return value.get("value", "")
    return ""


def fetch_rss(source: dict, since_hours: int = 24, limit: int = 60) -> list[dict]:
    """抓取单个 RSS/Atom 源，返回时间窗内的条目。

    无发布时间字段的条目不做时间过滤（否则整源会被过滤掉）。
    """
    url = (source.get("url") or "").strip()
    name = source.get("name") or url
    if not url:
        return []
    try:
        resp = http_get(url, headers=source.get("headers"))
    except Exception as exc:
        logger.warning("RSS 抓取失败 [%s] %s: %s", name, url, exc)
        return []

    parsed = feedparser.parse(resp.content)
    if not parsed.entries:
        logger.warning("RSS 无有效条目 [%s] %s（可能已不是 RSS 或需要浏览器渲染）", name, url)
        return []

    cutoff = now_utc() - timedelta(hours=max(int(since_hours), 1))
    items: list[dict] = []
    for entry in parsed.entries:
        published_dt = (
            parse_datetime(entry.get("published_parsed"))
            or parse_datetime(entry.get("updated_parsed"))
            or parse_datetime(entry.get("published"))
            or parse_datetime(entry.get("updated"))
        )
        if published_dt is not None and published_dt < cutoff:
            continue
        feed_title = ""
        if entry.get("source") and isinstance(entry["source"], dict):
            feed_title = entry["source"].get("title", "")
        item = make_item(
            title=entry.get("title") or "",
            url=entry.get("link") or "",
            source=name,
            summary=truncate(strip_html(_entry_body(entry)), 800),
            published_at=str(entry.get("published") or entry.get("updated") or ""),
            raw_content=_entry_body(entry),
            source_meta={**source, "extra_origin": feed_title},
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items
