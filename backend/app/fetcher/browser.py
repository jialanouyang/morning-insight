"""Playwright 浏览器兜底：用于 JS 渲染站点。

Playwright 属可选依赖（体积较大），未安装时静默降级并在日志中提示。
安装：`pip install playwright && playwright install chromium`

注意：Playwright 同步 API 非线程安全。抓取层是多线程并发的，
这里用进程内互斥锁把渲染串行化（渲染本身耗时长，不影响 RSS 并发）。
"""
import logging
import threading

logger = logging.getLogger("morning_insight.fetcher.browser")

_warned = False
_render_lock = threading.Lock()


def is_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def render_html(url: str, wait_ms: int = 1800, timeout_ms: int = 30000) -> str:
    """用无头浏览器渲染页面，返回渲染后的 HTML；不可用时返回空串。"""
    global _warned
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if not _warned:
            logger.info("未安装 Playwright，跳过浏览器兜底（如需抓取 JS 站点请安装：pip install playwright）")
            _warned = True
        return ""

    try:
        with _render_lock, sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                    ),
                    locale="zh-CN",
                )
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                page.wait_for_timeout(wait_ms)
                return page.content()
            finally:
                browser.close()
    except Exception as exc:
        logger.warning("Playwright 渲染失败 %s: %s", url, exc)
        return ""
