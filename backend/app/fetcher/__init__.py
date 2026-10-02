"""抓取层：RSS / API / 网页 / 插件源 + 三级去重 + 时间窗过滤。"""
from .api_source import fetch_api
from .browser import is_available as browser_available, render_html
from .catalog import (
    DEFAULT_SOURCES,
    SOURCE_CATALOG,
    build_google_news_url,
    catalog_by_category,
    keyword_source,
    source_templates,
)
from .dedup import DedupIndex, load_index
from .rss import fetch_rss
from .service import fetch_all_sources, fetch_source_items, save_articles, test_source
from .web_source import fetch_web

__all__ = [
    "DEFAULT_SOURCES",
    "SOURCE_CATALOG",
    "build_google_news_url",
    "keyword_source",
    "catalog_by_category",
    "source_templates",
    "fetch_all_sources",
    "fetch_source_items",
    "save_articles",
    "test_source",
    "fetch_rss",
    "fetch_api",
    "fetch_web",
    "render_html",
    "browser_available",
    "DedupIndex",
    "load_index",
]
