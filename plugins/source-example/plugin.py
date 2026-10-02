"""示例数据源插件。

接口约定：
    fetch(config: dict, since_hours: int, limit: int) -> list[dict]

返回的每个 dict 至少包含 title 与 url，可选 summary / published_at / raw_content / language / region。
晨析会自动完成去重、时间窗过滤、入库与溯源。
"""
from datetime import datetime, timedelta, timezone

import httpx

DEFAULT_URL = "https://hn.algolia.com/api/v1/search_by_date?tags=story"


def fetch(config: dict, since_hours: int = 24, limit: int = 60) -> list[dict]:
    url = (config.get("url") or DEFAULT_URL).strip()
    hits_path = (config.get("hits_path") or "hits").strip()
    query = (config.get("query") or "").strip()

    params = {}
    if query:
        params["query"] = query

    resp = httpx.get(url, params=params or None, timeout=25.0, follow_redirects=True)
    resp.raise_for_status()
    payload = resp.json()

    rows = payload
    for part in hits_path.split("."):
        if isinstance(rows, dict):
            rows = rows.get(part, [])
        else:
            rows = []
            break
    if not isinstance(rows, list):
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(int(since_hours), 1))
    items: list[dict] = []
    for row in rows[: max(int(limit), 1)]:
        if not isinstance(row, dict):
            continue
        title = row.get("title") or row.get("story_title") or ""
        link = row.get("url") or row.get("story_url") or ""
        if not link and row.get("objectID"):
            link = f"https://news.ycombinator.com/item?id={row['objectID']}"
        if not title or not link:
            continue

        created = row.get("created_at")
        if created:
            try:
                published = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if published < cutoff:
                    continue
            except ValueError:
                pass

        items.append({
            "title": title,
            "url": link,
            "summary": (row.get("story_text") or row.get("comment_text") or "")[:500],
            "published_at": created or "",
            "language": "en",
            "region": "国际",
        })
    return items
