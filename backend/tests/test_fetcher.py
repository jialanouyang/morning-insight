"""抓取层测试：时间窗过滤、失效源容错、三级去重、源目录。

使用本地 HTTP 服务提供固定 RSS，不依赖外网。
"""
import sys
import threading
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.fetcher import DEFAULT_SOURCES, SOURCE_CATALOG, fetch_rss, keyword_source  # noqa: E402
from app.fetcher.dedup import DedupIndex  # noqa: E402
from app.utils.text import is_duplicate, normalize, title_hash  # noqa: E402


def _rss(pubdate: datetime, title: str) -> str:
    return f"""
    <item>
      <title>{title}</title>
      <link>https://example.com/{title}</link>
      <pubDate>{format_datetime(pubdate)}</pubDate>
    </item>
    """


FRESH = datetime.now(timezone.utc) - timedelta(hours=2)
STALE = datetime.now(timezone.utc) - timedelta(days=30)

FRESH_FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>测试源</title>
  <link>https://example.com</link>
  <description>test</description>
  {_rss(FRESH, "新鲜条目")}
  {_rss(STALE, "过期条目")}
</channel></rss>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/feed.xml":
            body = FRESH_FEED.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        elif self.path == "/not-rss":
            body = b"<html><body>not a feed</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            body = b"not found"
            self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 静默测试日志
        pass


@pytest.fixture(scope="module")
def feed_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


# --------------------------------------------------------------------------- #
# RSS 抓取
# --------------------------------------------------------------------------- #
def test_time_window_filters_stale_entries(feed_server):
    items = fetch_rss({"name": "测试源", "url": f"{feed_server}/feed.xml"}, since_hours=24)
    titles = [i["title"] for i in items]
    assert "新鲜条目" in titles
    assert "过期条目" not in titles  # 30 天前的条目应被时间窗过滤


def test_wide_window_keeps_all(feed_server):
    items = fetch_rss({"name": "测试源", "url": f"{feed_server}/feed.xml"}, since_hours=24 * 60)
    assert len(items) == 2


def test_non_rss_response_returns_empty(feed_server):
    assert fetch_rss({"name": "网页", "url": f"{feed_server}/not-rss"}) == []


def test_broken_source_does_not_raise():
    # 不可达地址应被吞掉并返回空列表，不能影响其它源
    assert fetch_rss({"name": "坏源", "url": "http://127.0.0.1:1/none.xml"}) == []


def test_empty_url_returns_empty():
    assert fetch_rss({"name": "空源", "url": ""}) == []


def test_items_are_normalized(feed_server):
    items = fetch_rss({"name": "测试源", "url": f"{feed_server}/feed.xml"}, since_hours=24)
    item = items[0]
    assert item["source"] == "测试源"
    assert item["url"].startswith("http")
    assert item["title_hash"] and item["content_hash"]
    assert "priority" in item


# --------------------------------------------------------------------------- #
# 三级去重
# --------------------------------------------------------------------------- #
def _item(title, url, summary=""):
    return {
        "title": title,
        "url": url,
        "summary": summary,
        "title_hash": title_hash(title),
    }


def test_dedup_by_url():
    idx = DedupIndex()
    assert idx.check(_item("标题 A", "https://a.com/1")) == ""
    idx.accept(_item("标题 A", "https://a.com/1"))
    assert idx.check(_item("完全不同的标题", "https://a.com/1")) == "url"


def test_dedup_by_title_hash():
    idx = DedupIndex()
    idx.accept(_item("同一个标题很长很长", "https://a.com/1"))
    assert idx.check(_item("同一个标题很长很长", "https://a.com/2")) == "title_hash"


def test_dedup_normalizes_title_whitespace():
    """标题只差空格/大小写/标点时，应按标题哈希判定为重复。"""
    idx = DedupIndex()
    idx.accept(_item("某公司完成 B 轮融资", "https://a.com/1"))
    assert idx.check(_item("某公司完成B轮融资", "https://a.com/2")) == "title_hash"


def test_dedup_catches_near_duplicate_story():
    """标题微调、正文几乎一致时，应被模糊匹配拦下（标题或内容相似均可）。"""
    idx = DedupIndex()
    idx.accept(
        _item(
            "某公司完成 B 轮融资",
            "https://a.com/1",
            "某公司今日宣布完成 B 轮融资，金额 3 亿元，由某某资本领投，资金将用于产线扩张",
        )
    )
    dup = _item(
        "某公司完成 C 轮融资",
        "https://b.com/9",
        "某公司今日宣布完成 B 轮融资，金额 3 亿元，由某某资本领投，资金将用于产线扩张",
    )
    assert idx.check(dup) in ("title_similar", "content_similar")


def test_similarity_threshold_is_conservative():
    """换了标题的同一件事：标题占比较小时不会误判（宁可漏去重，不可误杀）。"""
    from app.utils.text import similarity

    a = "晨报快讯：某公司获巨额融资 某公司今日宣布完成 B 轮融资，金额 3 亿元，由某某资本领投"
    b = "今日融资速递 某公司今日宣布完成 B 轮融资，金额 3 亿元，由某某资本领投。"
    assert 0.5 < similarity(a, b) < 0.86


def test_distinct_items_are_not_duplicates():
    idx = DedupIndex()
    idx.accept(_item("半导体设备出口管制更新", "https://a.com/1"))
    assert idx.check(_item("新能源汽车销量创新高", "https://b.com/2")) == ""


def test_similarity_helper():
    assert is_duplicate(normalize("测试文本 ABC"), normalize("测试文本 ABC"), 0.9)
    assert not is_duplicate(normalize("完全不同的内容一"), normalize("毫无关系的另一段文字"), 0.9)


# --------------------------------------------------------------------------- #
# 源目录
# --------------------------------------------------------------------------- #
def test_default_sources_reachable_shape():
    # 文档验收标准「信息源默认全选」：全部 RSS + 实测可用（verified、无 JS 渲染）的 web/api 源
    assert len(DEFAULT_SOURCES) >= 60
    names = [s["name"] for s in DEFAULT_SOURCES]
    assert len(names) == len(set(names))  # 去重，不重复
    types = {s["type"] for s in DEFAULT_SOURCES}
    assert "rss" in types
    assert {"api", "web"} & types  # 中文权威媒体/政府机构以 web/api 源形式默认启用
    for s in DEFAULT_SOURCES:
        assert s.get("name") and s.get("url")
        assert s.get("type") in ("rss", "api", "web", "plugin")
        assert isinstance(s.get("priority"), int)
        assert not s.get("render_js")  # 需 JS 渲染的源不应默认启用（Playwright 为可选依赖）


def test_default_sources_cover_chinese_media_and_gov():
    names = {s["name"] for s in DEFAULT_SOURCES}
    # 文档「中文权威媒体」与「政府与机构」清单默认启用（实测可用者）
    for name in ("新华社", "人民日报", "央视新闻", "财新", "第一财经", "南方周末"):
        assert name in names, f"权威媒体 {name} 未默认启用"
    for name in ("国务院", "国家发改委", "科学技术部", "财政部",
                 "中国人民银行", "中国证监会", "国家统计局"):
        assert name in names, f"政府机构 {name} 未默认启用"
    # 默认启用的 web 源必须带列表选择器
    for s in DEFAULT_SOURCES:
        if s["type"] == "web":
            assert s.get("list_selector"), f"web 源 {s['name']} 缺少 list_selector"


def test_catalog_covers_chinese_and_english():
    names = " ".join(s.get("name", "") for s in SOURCE_CATALOG)
    urls = " ".join(s.get("url", "") or "" for s in SOURCE_CATALOG)
    assert any(k in names for k in ("36氪", "财新", "新华社", "钛媒体", "界面"))
    assert any(k in names for k in ("Reuters", "TechCrunch", "Hacker News", "MIT"))
    assert "gov.cn" in urls  # 政府机构来源


def test_catalog_has_verified_flag():
    assert all("verified" in s for s in SOURCE_CATALOG)


def test_keyword_source_builds_google_news_rss():
    src = keyword_source("半导体", "zh", engine="google")
    assert src["type"] == "rss"
    assert "news.google.com" in src["url"]
    assert "半导体" in src["name"]


def test_keyword_source_default_engine_is_360_news():
    """默认引擎走 360 资讯搜索（服务端渲染，国内网络可达）。"""
    src = keyword_source("半导体")
    assert src["type"] == "web"
    assert "news.so.com/ns?q=" in src["url"]
    assert src["list_selector"] == "li.res-list"
    assert src["title_selector"] == "a@title"
    assert src["date_selector"] == "span.time"
    assert "关键词·半导体" == src["name"]
    # 引擎清单须暴露给前端说明
    from app.fetcher.catalog import SEARCH_ENGINES

    assert set(SEARCH_ENGINES) == {"so360", "google"}


# --------------------------------------------------------------------------- #
# API 源：JSONP 解析与查询串保留
# --------------------------------------------------------------------------- #
def test_parse_payload_text_handles_jsonp():
    from app.fetcher.api_source import parse_payload_text

    # 普通 JSON
    data = parse_payload_text('{"data": {"list": [1, 2]}}')
    assert data["data"]["list"] == [1, 2]
    # JSONP 包装（央视新闻接口形式）
    data = parse_payload_text('news({"data": {"list": [{"title": "t"}]}})')
    assert data["data"]["list"][0]["title"] == "t"
    data = parse_payload_text('ns.web.cb({"ok": 1});')
    assert data["ok"] == 1
    # 列表 JSON
    assert parse_payload_text("[1, 2, 3]") == [1, 2, 3]


def test_api_source_url_query_preserved():
    """httpx 的 params 会整体替换 URL 查询串 —— fetch_api 不得在 params 为空时传 params。"""
    import inspect

    from app.fetcher import api_source

    src = inspect.getsource(api_source.fetch_api)
    assert 'if params:' in src  # 空 params 时不传，保留 URL 自带查询串


# --------------------------------------------------------------------------- #
# API 源：内嵌 JSON 状态提取 / URL 模板 / 时间戳解析（36氪、澎湃）
# --------------------------------------------------------------------------- #
def test_extract_json_var():
    from app.fetcher.api_source import extract_json_var

    html = (
        "<script>window.__cfg = 1;</script>"
        "<script>window.initialState={\"a\": {\"b\": \"}\"}, \"n\": [1, 2]};</script>"
    )
    data = extract_json_var(html, "initialState")
    assert data == {"a": {"b": "}"}, "n": [1, 2]}  # 值内的 } 不能截断
    assert extract_json_var(html, "notExist") is None


def test_render_url_template():
    from app.fetcher.api_source import render_url_template

    row = {"contId": "34184563", "meta": {"itemId": 42}}
    assert render_url_template("https://x.cn/d_{contId}", row) == "https://x.cn/d_34184563"
    assert render_url_template("https://x.cn/p/{meta.itemId}.html", row) == "https://x.cn/p/42.html"
    # 缺字段渲染为空串但不抛异常
    assert render_url_template("https://x.cn/{gone}", row) == "https://x.cn/"


def test_parse_datetime_handles_timestamps():
    from app.fetcher.core import parse_datetime

    # 毫秒时间戳（int / 字符串）
    dt = parse_datetime(1790842510000)
    assert dt is not None and dt.year == 2026
    dt2 = parse_datetime("1790842510000")
    assert dt2 == dt
    # 秒级时间戳
    assert parse_datetime(1790842510).year == 2026
    # 非时间戳数字（如 ID）交给后续逻辑，返回 None
    assert parse_datetime("123") is None


def test_default_sources_include_36kr_huxiu_thepaper():
    names = {s["name"] for s in DEFAULT_SOURCES}
    for name in ("36氪", "虎嗅", "澎湃新闻"):
        src = next(s for s in DEFAULT_SOURCES if s["name"] == name)
        assert not src.get("render_js"), f"{name} 不应再依赖 JS 渲染"
    assert {"36氪", "虎嗅", "澎湃新闻"} <= names


# --------------------------------------------------------------------------- #
# 关注点内容供给：学术与专利 / 人才情报 / 行业分析 类源
# --------------------------------------------------------------------------- #
def test_catalog_covers_tech_talent_market_topics():
    """技术突破 / 人才流动 / 行业分析三个关注点须有对应数据源目录。"""
    by_cat = {}
    for s in SOURCE_CATALOG:
        by_cat.setdefault(s["category"], set()).add(s["name"])

    tech = by_cat.get("学术与专利", set())
    assert {"arXiv · 人工智能", "Nature 新闻", "IEEE Spectrum", "知领·中国工程科技",
            "Lens.org", "SpecialSci", "EPO TIP / PATSTAT"} <= tech

    talent = by_cat.get("人才情报", set())
    assert {"企名片", "智联招聘·就业市场报告", "Lusha", "Lightcast",
            "Zeki Talent Alpha", "Coresignal", "Mercer Workforce"} <= talent

    industry = by_cat.get("行业数据库", set())
    assert {"GlobalData", "国研网", "Speeda Business Insights", "Veridion"} <= industry


def test_default_sources_include_topic_feeds():
    """实测可用的学术/人才/行业源应默认启用（关注点板块开箱有料）。"""
    names = {s["name"] for s in DEFAULT_SOURCES}
    assert {"arXiv · 人工智能", "arXiv · 机器学习", "arXiv · 自然语言处理",
            "Nature 新闻", "IEEE Spectrum", "知领·中国工程科技",
            "GitHub Trending", "Hacker News 招聘", "GlobalData"} <= names
    # JS 渲染的科讯头条/企名片留在目录中，不进默认
    assert "科讯头条（PubScholar）" not in names
    assert "企名片" not in names


_GITHUB_TRENDING_HTML = """
<article class="Box-row">
  <div class="float-right d-flex"><a href="/sponsors/foo">Sponsor</a></div>
  <h2 class="h3 lh-condensed"><a href="/foo/bar">foo / bar</a></h2>
  <p class="col-9 color-fg-muted my-1 pr-4"> A neat project </p>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/alice/repo">alice / repo</a></h2>
  <p> Another project </p>
</article>
"""


def test_github_trending_selectors_flat_and_working():
    """GitHub Trending 的选择器必须展平在源配置顶层（嵌套在 selectors 键里抓取器读不到）。"""
    src = next(s for s in SOURCE_CATALOG if s["name"] == "GitHub Trending")
    assert src.get("list_selector") == "article.Box-row"
    assert "selectors" not in src  # 防止回退到嵌套写法
    from app.fetcher.web_source import parse_with_selectors

    items = parse_with_selectors(_GITHUB_TRENDING_HTML, src, limit=10, since_hours=24)
    assert [i["title"] for i in items] == ["foo / bar", "alice / repo"]
    assert items[0]["url"] == "https://github.com/foo/bar"
    assert "neat project" in items[0]["summary"]


# --------------------------------------------------------------------------- #
# 时间解析：中文站点日期写法 / 相对时间 / 链接内嵌日期
# （曾因 2026/07/31 这类格式解析失败，旧文绕过时间窗混入素材库）
# --------------------------------------------------------------------------- #
def test_parse_datetime_chinese_date_formats():
    from app.fetcher.core import parse_datetime

    assert parse_datetime("2026/07/31").date().isoformat() == "2026-07-31"
    assert parse_datetime("2026.07.14").date().isoformat() == "2026-07-14"
    assert parse_datetime("2026年7月31日").date().isoformat() == "2026-07-31"
    assert parse_datetime("2026年7月31日 10:30:00").hour == 10
    assert parse_datetime("2026/7/31 10:30").minute == 30
    assert parse_datetime("20260731").date().isoformat() == "2026-07-31"
    # 无年份的「09-28」按当年推断（证监会列表写法）
    assert parse_datetime("09-28").month == 9
    # 非法日期不能瞎猜
    assert parse_datetime("13/45") is None
    assert parse_datetime("没有日期") is None


def test_parse_datetime_relative_time():
    from app.fetcher.core import now_utc, parse_datetime

    now = now_utc()
    dt = parse_datetime("3小时前")
    assert dt is not None and 2.9 * 3600 < (now - dt).total_seconds() < 3.1 * 3600
    dt = parse_datetime("昨天 23:50")
    assert dt is not None and (dt.hour, dt.minute) == (23, 50)
    assert parse_datetime("刚刚") is not None


def test_parse_date_from_url():
    from app.fetcher.core import parse_date_from_url

    cases = {
        "https://www.news.cn/politics/20260929/0dfa19a8/c.html": "2026-09-29",
        "http://finance.people.com.cn/n1/2026/1001/c1004-40808619.html": "2026-10-01",
        "https://weekly.caixin.com/2026-08-21/102476335.html": "2026-08-21",
        "https://www.ndrc.gov.cn/xwdt/xwfb/202607/t20260731_1406862.html": "2026-07-31",
        "http://www.pbc.gov.cn/x/2026092917153548424/index.html": "2026-09-29",
    }
    for url, expected in cases.items():
        dt = parse_date_from_url(url)
        assert dt is not None and dt.date().isoformat() == expected, url
    # 纯 ID（36氪快讯 4006930331701384）不能误判为日期
    assert parse_date_from_url("https://36kr.com/newsflashes/4006930331701384") is None


def test_web_source_filters_stale_items_by_url_date():
    """列表页没有时间元素时，必须用链接内嵌日期做时间窗过滤，否则旧文会照单全收。

    链接内嵌日期由「当前日期」动态生成，避免测试随年月推移自然失效。
    """
    from app.fetcher.web_source import parse_with_selectors

    now = datetime.now(timezone.utc)
    fresh_path = now.strftime("/%Y/%m%d/") + "new.html"
    stale_path = (now - timedelta(days=70)).strftime("/%Y/%m%d/") + "old.html"

    html = f"""
    <ul class="list">
      <li><a href="{stale_path}">两个月前的旧闻</a></li>
      <li><a href="{fresh_path}">今天的新闻</a></li>
    </ul>
    """
    source = {
        "name": "测试源", "type": "web", "url": "https://example.com/news/",
        "list_selector": "ul.list li", "title_selector": "a", "url_selector": "a@href",
    }
    items = parse_with_selectors(html, source, limit=10, since_hours=24)
    titles = [i["title"] for i in items]
    assert "今天的新闻" in titles
    assert "两个月前的旧闻" not in titles
