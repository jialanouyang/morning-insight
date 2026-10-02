"""API 路由集合。"""
from . import (
    admin_router,
    alert_router,
    auth_router,
    competitor_router,
    config_router,
    knowledge_router,
    meta_router,
    periodical_router,
    plugin_router,
    report_router,
)

ALL_ROUTERS = [
    auth_router,
    config_router,
    report_router,
    knowledge_router,
    competitor_router,
    alert_router,
    periodical_router,
    plugin_router,
    admin_router,
    meta_router,
]

__all__ = ["ALL_ROUTERS"]
