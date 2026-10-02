"""网页源抓取：URL + CSS 选择器（可选用 AI 自动推断选择器）。

源配置示例（Web UI 「信息源 → 添加 → 网页」）：
{
  "type": "web",
  "name": "某网站",
  "url": "https://example.com/news",
  "list_selector": "ul.news-list > li",       # 列表项
  "title_selector": "a",                      # 相对列表项；支持 "a@title" 取属性
  "url_selector": "a@href",
  "summary_selector": "p.desc",
  "date_selector": "time@datetime",
  "content_selector": "article",              # 详情页正文（可选）
  "base_url": "https://example.com",
  "render_js": false                          # 需要 JS 渲染时用 Playwright 兜底
}
选择器语法：CSS 选择器，可选 `@属性名` 后缀用于取属性值。
"""
import logging
from datetime import timedelta
from urllib.parse import urljoin

from ..utils.text import strip_html, truncate
from .core import http_get, make_item, now_utc, parse_date_from_url, parse_datetime

logger = logging.getLogger("morning_insight.fetcher.web")


def _load_soup(html: str):
    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover
        logger.error("网页源需要 beautifulsoup4，请先安装依赖")
        return None
    for parser in ("lxml", "html.parser"):
        try:
            return BeautifulSoup(html, parser)
        except Exception:
            continue
    return None


def _matches_self(node, css: str) -> bool:
    """判断节点自身是否就匹配该选择器（select_one 只搜后代，会漏掉这种情况）。"""
    token = css.strip().split()[-1].split(">")[-1].split(":")[0]
    if not token or token in ("*", ""):
        return False
    tag = (getattr(node, "name", "") or "").lower()
    if token.startswith("."):
        classes = node.get("class") or [] if hasattr(node, "get") else []
        return token[1:] in classes
    if token.startswith("#"):
        return token[1:] == (node.get("id") if hasattr(node, "get") else None)
    return token.lower() == tag


def _extract(node, selector: str) -> str:
    """按 `css@attr` 语法从节点取值。"""
    if not node or not selector:
        return ""
    css, _, attr = selector.partition("@")
    css = css.strip()
    target = node
    if css:
        target = node.select_one(css)
        if target is None and _matches_self(node, css):
            target = node
    if target is None:
        return ""
    if attr:
        attr = attr.strip()
        if attr == "text":
            return target.get_text(" ", strip=True)
        value = target.get(attr)
        if isinstance(value, list):
            value = " ".join(value)
        return (value or "").strip()
    return target.get_text(" ", strip=True)


def parse_with_selectors(html: str, source: dict, limit: int = 60, since_hours: int = 24) -> list[dict]:
    soup = _load_soup(html)
    if soup is None:
        return []

    list_selector = (source.get("list_selector") or "").strip()
    name = source.get("name") or source.get("url") or ""
    base_url = (source.get("base_url") or source.get("url") or "").strip()
    cutoff = now_utc() - timedelta(hours=max(int(since_hours), 1))

    if list_selector:
        nodes = soup.select(list_selector)
    else:
        nodes = soup.select("article") or soup.select("li") or [soup]

    items: list[dict] = []
    for node in nodes[:limit]:
        link = _extract(node, source.get("url_selector") or "a@href")
        if not link:
            anchor = node.select_one("a[href]") if hasattr(node, "select_one") else None
            link = (anchor.get("href") if anchor else "") or ""
        if link and not link.startswith("http"):
            link = urljoin(base_url, link)
        title = _extract(node, source.get("title_selector") or "a") or (
            node.get_text(" ", strip=True) if hasattr(node, "get_text") else ""
        )
        published_raw = _extract(node, source.get("date_selector") or "")
        published_dt = parse_datetime(published_raw)
        if published_dt is None:
            # 列表页没有时间元素时，回退到链接内嵌日期（新华社 /20260929/、
            # 人民日报 /2026/1001/、央行 /20260929.../），否则时间窗无法生效
            published_dt = parse_date_from_url(link)
            if published_dt is not None:
                published_raw = published_dt.date().isoformat()
        if published_dt is not None and published_dt < cutoff:
            continue
        item = make_item(
            title=title,
            url=link,
            source=name,
            summary=truncate(_extract(node, source.get("summary_selector") or ""), 800),
            published_at=published_raw,
            source_meta=source,
        )
        if item:
            items.append(item)
    return items


def fetch_web(source: dict, since_hours: int = 24, limit: int = 60) -> list[dict]:
    url = (source.get("url") or "").strip()
    name = source.get("name") or url
    if not url:
        return []

    html = ""
    if not source.get("render_js"):
        try:
            html = http_get(url, headers=source.get("headers")).text
        except Exception as exc:
            logger.warning("网页源直连失败 [%s] %s: %s，尝试浏览器兜底", name, url, exc)

    items = parse_with_selectors(html, source, limit=limit, since_hours=since_hours) if html else []

    if not items:
        # 直连拿不到内容（多为 JS 渲染站点）→ Playwright 兜底
        from .browser import render_html

        rendered = render_html(url)
        if rendered:
            items = parse_with_selectors(rendered, source, limit=limit, since_hours=since_hours)
    if not items:
        logger.warning("网页源未解析出条目 [%s] %s（检查 list_selector）", name, url)
    return items


AI_SELECTOR_PROMPT = """你是网页解析助手。下面是一个新闻列表页的 HTML 片段。
请提取 CSS 选择器，输出严格 JSON（不要解释）：
{"list_selector": "", "title_selector": "", "url_selector": "", "summary_selector": "", "date_selector": ""}
说明：url_selector 用 `css@href` 形式取链接属性；若某字段不存在则留空字符串。

HTML 片段：
{html}
"""


def ai_suggest_selectors(url: str, llm_complete=None) -> dict:
    """让 AI 推断 CSS 选择器（对应文档「或让 AI 解析」）。

    llm_complete: 可调用的 (system_prompt, user_prompt) -> str；由上层注入 LLM 客户端。
    """
    if llm_complete is None:
        raise ValueError("未提供 AI 客户端，无法自动解析选择器")
    import json

    html = ""
    try:
        html = http_get(url).text[:12000]
    except Exception as exc:
        raise ValueError(f"抓取页面失败：{exc}") from exc
    raw = llm_complete("你只输出 JSON。", AI_SELECTOR_PROMPT.replace("{html}", html))
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI 返回的选择器不是合法 JSON：{raw[:200]}") from exc
    return {k: str(v or "") for k, v in data.items()}


def extract_article_content(url: str, selector: str = "") -> str:
    """抓取详情页正文（用于「单条摘要」与知库切片）。"""
    try:
        html = http_get(url).text
    except Exception:
        return ""
    soup = _load_soup(html)
    if soup is None:
        return ""
    node = soup.select_one(selector) if selector else None
    if node is None:
        for candidate in ("article", "main", ".article-content", ".content", "#content"):
            node = soup.select_one(candidate)
            if node is not None:
                break
    target = node or soup
    for tag in target.select("script, style, nav, footer, aside, .ad, .comment"):
        tag.decompose()
    return truncate(strip_html(target.get_text("\n", strip=True)), 20000)
