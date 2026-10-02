"""API 接口源抓取：URL + Key + 字段映射。

源配置示例（Web UI 「信息源 → 添加 → API」）：
{
  "type": "api",
  "name": "某数据平台",
  "url": "https://api.example.com/v1/news",
  "method": "GET",
  "api_key": "xxxx",
  "api_key_header": "X-API-KEY",        # 以请求头传递；留空则用 api_key_query
  "api_key_query": "",                   # 以查询参数传递，如 "apikey"
  "params": {"limit": 20},
  "items_path": "data.items",            # 列表所在路径，支持 a.b.0.c
  "field_map": {                         # 左侧为晨析字段，右侧为接口字段路径
    "title": "title",
    "url": "link",
    "summary": "desc",
    "published_at": "pubDate",
    "content": "content"
  },
  "base_url": "https://example.com",     # 相对链接补全
  "json_var": "initialState",            # 可选：接口实为 HTML 时，提取 window.<json_var> 内嵌 JSON
  "url_template": "https://example.com/news/{contId}"  # 可选：链接需拼接时按行内字段渲染
}

`json_var` 用于「页面无独立接口、数据内嵌在 window.xxx = {...}」的站点
（如 36氪移动端）；`url_template` 用于接口只给 ID 不给链接的站点
（如澎湃 hotNews 只返回 contId，用 newsDetail_forward_{contId} 拼接）。
"""
import logging
import re
from datetime import timedelta
from urllib.parse import urljoin

import httpx

from ..utils.text import strip_html, truncate
from .core import FETCH_TIMEOUT, HEADERS, make_item, now_utc, parse_date_from_url, parse_datetime

logger = logging.getLogger("morning_insight.fetcher.api")

# JSONP 包装：如 `callback({...})` 或 `cb.namespace({...});`
_JSONP_RE = re.compile(r"^[\w$.]+\((.*)\)[;\s]*$", re.S)


def parse_payload_text(text: str):
    """解析响应文本为 JSON，自动剥掉 JSONP 包装（如央视新闻接口）。"""
    text = (text or "").strip()
    if text[:1] not in ("{", "["):
        m = _JSONP_RE.match(text)
        if m:
            text = m.group(1).strip()
    import json

    return json.loads(text)


def extract_json_var(text: str, var: str):
    """从 HTML 中提取 `window.<var> = {...};` 内嵌的 JSON 对象。

    用括号配对扫描而非正则（JSON 体内可含 `}` 字符串字面量），
    支持 36氪移动端 `window.initialState={...}` 这类服务端注水数据。
    """
    import json

    marker = f"window.{var}"
    start = (text or "").find(marker)
    if start < 0:
        return None
    brace = text.find("{", start + len(marker))
    if brace < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(brace, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace : i + 1])
                except ValueError:
                    return None
    return None


def render_url_template(template: str, row: dict) -> str:
    """按行内字段渲染链接模板：{contId} 取行内 contId，{a.b.c} 按点号路径取值。"""
    import re as _re

    def _sub(m: "_re.Match") -> str:
        return str(dig(row, m.group(1).strip(), "") or "")

    try:
        return _re.sub(r"\{([^{}]+)\}", _sub, template)
    except Exception:
        return ""


def _is_timestamp(value) -> bool:
    """是否为纯数字时间戳（秒 10 位 / 毫秒 13 位）。"""
    if isinstance(value, int):
        return True
    return isinstance(value, str) and value.strip().isdigit()

DEFAULT_FIELD_MAP = {
    "title": "title",
    "url": "url",
    "summary": "summary",
    "published_at": "published_at",
    "content": "content",
}


def dig(obj, path: str, default=None):
    """按点号路径取值，支持列表下标：data.items.0.title。"""
    if not path:
        return default
    cur = obj
    for part in str(path).split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part, default)
        elif isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return cur


def fetch_api(source: dict, since_hours: int = 24, limit: int = 100) -> list[dict]:
    url = (source.get("url") or "").strip()
    name = source.get("name") or url
    if not url:
        return []

    headers = dict(HEADERS)
    headers.update({k: v for k, v in (source.get("headers") or {}).items() if v})
    params = dict(source.get("params") or {})

    api_key = (source.get("api_key") or "").strip()
    if api_key:
        header_name = (source.get("api_key_header") or "").strip()
        query_name = (source.get("api_key_query") or "").strip()
        if header_name:
            headers[header_name] = api_key
        elif query_name:
            params[query_name] = api_key
        else:
            headers.setdefault("Authorization", f"Bearer {api_key}")

    method = (source.get("method") or "GET").upper()
    path = source.get("items_path") or ""
    json_var = (source.get("json_var") or "").strip()
    url_template = (source.get("url_template") or "").strip()
    # 注意：httpx 的 params 会整体替换 URL 上的查询串，为空时必须不传，
    # 否则「URL 自带 query + 空 params」会把 query 丢掉
    request_kwargs: dict = {"headers": headers, "timeout": FETCH_TIMEOUT, "follow_redirects": True}
    if params:
        request_kwargs["params"] = params
    # 部分接口（如国务院政策文件库）会间歇性返回空列表（限流），
    # items_path 未命中列表时最多重试 2 次
    attempts = 3 if path else 1
    payload = None
    rows = None
    for attempt in range(attempts):
        try:
            if method == "POST":
                resp = httpx.post(url, json=source.get("body") or {}, **request_kwargs)
            else:
                resp = httpx.get(url, **request_kwargs)
            resp.raise_for_status()
            if json_var:
                # HTML 页面 + 内嵌 JSON 状态（如 36氪移动端 window.initialState）
                payload = extract_json_var(resp.text, json_var)
            else:
                payload = parse_payload_text(resp.text)
        except Exception as exc:
            logger.warning("API 源抓取失败 [%s] %s: %s", name, url, exc)
            return []
        rows = dig(payload, path, payload if not path else None)
        if isinstance(rows, list) and rows:
            break
        if attempt < attempts - 1:
            import time

            time.sleep(1.5)
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list):
        logger.warning("API 源 items_path 未命中列表 [%s] path=%s", name, path)
        return []

    field_map = {**DEFAULT_FIELD_MAP, **(source.get("field_map") or {})}
    base_url = (source.get("base_url") or url).strip()
    cutoff = now_utc() - timedelta(hours=max(int(since_hours), 1))

    items: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        link = str(dig(row, field_map["url"], "") or "")
        if not link and url_template:
            # 接口只给 ID 时按模板拼链接（如澎湃 newsDetail_forward_{contId}）
            link = render_url_template(url_template, row)
        if link and not link.startswith("http"):
            link = urljoin(base_url, link)
        published_raw = dig(row, field_map["published_at"], "")
        published_dt = parse_datetime(published_raw)
        if published_dt is None and link:
            # 接口未给时间时回退到链接内嵌日期，保证时间窗对旧文生效
            published_dt = parse_date_from_url(link)
            if published_dt is not None:
                published_raw = published_dt.date().isoformat()
        if published_dt is not None and published_dt < cutoff:
            continue
        if published_dt is not None and _is_timestamp(published_raw):
            # 毫秒/秒级时间戳统一转成可读的 ISO 格式入库
            published_raw = published_dt.isoformat(timespec="seconds")
        item = make_item(
            title=str(dig(row, field_map["title"], "") or ""),
            url=link,
            source=name,
            summary=truncate(strip_html(str(dig(row, field_map["summary"], "") or "")), 800),
            published_at=str(published_raw or ""),
            raw_content=str(dig(row, field_map["content"], "") or ""),
            source_meta=source,
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items
