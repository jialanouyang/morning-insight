"""抓取编排：按类型分发 → 去重 → 入库。

对外提供：
- fetch_source_items(source, since_hours)   抓取单个源（不落库）
- fetch_all_sources(db, user_id, sources)   抓取全部启用源，去重后入库
- save_articles(db, user_id, items)         入库（三级去重）
- test_source(source)                       设置页「测试源」用
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Article
from ..utils.text import content_hash, title_hash
from . import dedup as dedup_mod
from .api_source import fetch_api
from .core import sort_by_priority
from .rss import fetch_rss
from .web_source import fetch_web

logger = logging.getLogger("morning_insight.fetcher")

SUPPORTED_TYPES = ("rss", "api", "web", "plugin")

# 并发抓取：默认启用源已达 50+（文档「信息源默认全选」），
# 串行 + 单源 20s 超时会让一次生成最坏拖到十几分钟，故用线程池并发。
# 8 个 worker 对目标站点友好，也把最坏耗时压到约 (源数/8)×超时。
FETCH_WORKERS = 8


def fetch_source_items(source: dict, since_hours: int = 24, limit: int = 80) -> list[dict]:
    """按源类型分发抓取。返回归一化后的条目列表。"""
    stype = (source.get("type") or "rss").lower()
    if not source.get("url") and stype != "plugin":
        return []
    if stype == "rss":
        return fetch_rss(source, since_hours=since_hours, limit=limit)
    if stype == "api":
        return fetch_api(source, since_hours=since_hours, limit=limit)
    if stype == "web":
        return fetch_web(source, since_hours=since_hours, limit=limit)
    if stype == "plugin":
        try:  # 延迟导入避免循环依赖
            from ..plugins.registry import run_source_plugin

            return run_source_plugin(source, since_hours=since_hours, limit=limit)
        except Exception as exc:
            logger.warning("插件源抓取失败 [%s]: %s", source.get("name"), exc)
            return []
    logger.warning("未知信息源类型：%s（源：%s）", stype, source.get("name"))
    return []


def _article_row(user_id: int, item: dict) -> Article:
    return Article(
        user_id=user_id,
        title=item.get("title", "")[:500],
        url=item.get("url", "")[:1000],
        source=item.get("source", "")[:200],
        published_at=item.get("published_at", "")[:50],
        summary=item.get("summary", ""),
        raw_content=item.get("raw_content", ""),
        category=item.get("category", "")[:100],
        language=item.get("language", "")[:10],
        region=item.get("region", "")[:20],
        score=float(item.get("priority") or 0),
        title_hash=item.get("title_hash") or title_hash(item.get("title", "")),
        content_hash=item.get("content_hash")
        or content_hash(f"{item.get('title','')}\n{item.get('summary','')}"),
    )


def save_articles(db: Session, user_id: int, items: list[dict], index: dedup_mod.DedupIndex | None = None) -> list[dict]:
    """入库去重（URL 精确 / 标题哈希 / 内容相似度），返回新增条目。"""
    index = index or dedup_mod.load_index(db, user_id)
    new_items: list[dict] = []
    for item in items:
        if not item.get("url") or not item.get("title"):
            continue
        if not index.accept(item):
            continue
        db.add(_article_row(user_id, item))
        try:
            db.flush()
            new_items.append(item)
        except IntegrityError:
            db.rollback()
            index.urls.add(item["url"])
    db.commit()
    return new_items


def fetch_all_sources(
    db: Session,
    user_id: int,
    sources: list[dict],
    since_hours: int = 24,
    *,
    limit_per_source: int = 60,
) -> list[dict]:
    """抓取用户全部启用的源：并发抓取 → 按优先级归并 → 去重 → 入库。

    单个源失败不影响其他源（文档要求：多渠道/多源独立容错）。
    条目归并按源的优先级顺序拼接，保证高优素材排在前面。
    """
    index = dedup_mod.load_index(db, user_id)
    errors: list[str] = []

    ordered = sorted(
        [s for s in (sources or []) if s.get("enabled", True)],
        key=lambda s: -int(s.get("priority") or 0),
    )
    by_index: dict[int, list[dict]] = {}
    if ordered:
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            futures = {
                pool.submit(
                    fetch_source_items, source, since_hours=since_hours, limit=limit_per_source
                ): i
                for i, source in enumerate(ordered)
            }
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    by_index[i] = fut.result()
                except Exception as exc:  # 单源异常隔离
                    name = ordered[i].get("name") or ordered[i].get("url")
                    errors.append(f"{name}: {exc}")
                    logger.warning("信息源抓取异常 [%s]: %s", name, exc)

    collected: list[dict] = []
    for i in range(len(ordered)):
        collected.extend(by_index.get(i, []))

    ordered_items = sort_by_priority(collected)
    new_items = save_articles(db, user_id, ordered_items, index=index)
    if errors:
        logger.info("本轮有 %d 个源抓取失败：%s", len(errors), "; ".join(errors[:5]))
    return new_items


def test_source(source: dict, since_hours: int = 720) -> dict:
    """测试单个源是否可抓取（设置页「测试」按钮），返回样例与统计。"""
    try:
        items = fetch_source_items(source, since_hours=since_hours, limit=10)
    except Exception as exc:
        return {"ok": False, "count": 0, "error": str(exc), "samples": []}
    if not items:
        hint = "未抓到条目：请检查 URL、选择器或访问权限"
        if (source.get("type") or "rss") == "web":
            hint = "未抓到条目：多为 JS 渲染页面，请开启「浏览器渲染」或调整 CSS 选择器"
        return {"ok": False, "count": 0, "error": hint, "samples": []}
    return {
        "ok": True,
        "count": len(items),
        "error": "",
        "samples": [{"title": i["title"], "url": i["url"], "published_at": i.get("published_at", "")} for i in items[:5]],
    }
