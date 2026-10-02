"""晨析 Morning Insight — 后端入口。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .migrate import run_migrations
from .routers import ALL_ROUTERS
from .services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("morning_insight")

VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    try:
        changes = run_migrations()
        if changes:
            logger.info("数据库结构已更新：%s", ", ".join(changes[:10]))
    except Exception as exc:
        logger.warning("数据库迁移失败：%s", exc)

    try:  # 登记磁盘上的插件（不自动启用，需管理员手动开启）
        from .database import SessionLocal
        from .plugins import sync_from_disk

        db = SessionLocal()
        try:
            sync_from_disk(db)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("插件同步失败：%s", exc)

    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="晨析 Morning Insight API",
    description=(
        "开源自托管的行业分析晨报平台：抓取信息源 → AI 生成角色化晨报 → 多渠道定时推送，"
        "并沉淀为可检索的知识库。"
    ),
    version=VERSION,
    lifespan=lifespan,
)

# 生产环境建议将 allow_origins 收紧为你的前端域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in ALL_ROUTERS:
    app.include_router(module.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "app": "morning-insight", "version": VERSION}


@app.get("/api/features", tags=["system"])
def features():
    """当前环境的能力自检：可选依赖是否就绪（前端「关于」页展示）。"""
    from .fetcher.browser import is_available as playwright_available
    from .push import CHANNEL_SPECS
    from .push.channels.webpush import is_available as webpush_available

    optional = {
        "playwright": playwright_available(),
        "webpush": webpush_available(),
    }
    try:
        import edge_tts  # noqa: F401

        optional["edge_tts"] = True
    except ImportError:
        optional["edge_tts"] = False

    return {
        "version": VERSION,
        "capabilities": {
            "source_types": ["rss", "api", "web", "plugin"],
            "push_channels": len(CHANNEL_SPECS),
            "templates": 6,
            "report_formats": ["markdown", "html", "pdf", "image"],
            "knowledge_vector_store": "builtin（可切换 chroma / qdrant / pgvector）",
            "languages": ["zh", "en"],
        },
        "optional": optional,
    }
