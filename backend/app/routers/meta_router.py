"""元信息路由：前端「设置」页所需的全部内置目录。

一次请求返回，避免前端多次往返；也方便用户对照文档确认功能是否齐全。
"""
from fastapi import APIRouter, Depends

from ..ai.catalog import (
    AI_PROVIDERS,
    BUILTIN_FOCUS_POINTS,
    EMBEDDING_PROVIDERS,
    INDUSTRY_PRESETS,
    REPORT_LANGUAGES,
    REPORT_LENGTHS,
    REPORT_TEMPLATES,
    ROLE_TEMPLATES,
    TTS_FORMATS,
    TTS_PROVIDERS,
    UI_LANGUAGES,
    VECTOR_STORES,
)
from ..fetcher.catalog import DEFAULT_SOURCES, SOURCE_CATALOG, catalog_by_category, source_templates
from ..plugins.base import KNOWN_PERMISSIONS, PLUGIN_TYPES
from ..push import channel_catalog
from ..services.i18n import SUPPORTED_LANGUAGES
from ..settings import ALLOW_REGISTRATION, PLUGIN_INSTALL_ENABLED

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("")
def meta():
    return {
        "app": {
            "name": "晨析 Morning Insight",
            "version": "0.2.0",
            "allow_registration": ALLOW_REGISTRATION,
            "plugin_install_enabled": PLUGIN_INSTALL_ENABLED,
        },
        "focus_points": BUILTIN_FOCUS_POINTS,
        "roles": ROLE_TEMPLATES,
        "templates": REPORT_TEMPLATES,
        "industries": INDUSTRY_PRESETS,
        "ai_providers": AI_PROVIDERS,
        "embedding_providers": EMBEDDING_PROVIDERS,
        "vector_stores": VECTOR_STORES,
        "tts_providers": TTS_PROVIDERS,
        "tts_formats": TTS_FORMATS,
        "ui_languages": UI_LANGUAGES,
        "backend_languages": SUPPORTED_LANGUAGES,
        "report_languages": REPORT_LANGUAGES,
        "report_lengths": REPORT_LENGTHS,
        "channels": channel_catalog(),
        "default_sources": DEFAULT_SOURCES,
        "source_catalog": SOURCE_CATALOG,
        "source_catalog_grouped": catalog_by_category(),
        "source_templates": source_templates(),
        "plugin_types": list(PLUGIN_TYPES),
        "plugin_permissions": list(KNOWN_PERMISSIONS),
    }
