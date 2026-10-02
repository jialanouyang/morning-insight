"""插件注册与运行：安装 / 启用 / 禁用 / 卸载 / 调用。"""
import logging
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Plugin
from ..push.base import PushResult
from .base import PluginError, PluginManifest, load_manifest
from .loader import discover, load_module, plugin_root, validate

logger = logging.getLogger("morning_insight.plugins")

BUILTIN_MARKET_PLUGINS = [
    {
        "name": "source-example", "type": "source", "slug": "source-example",
        "title": "示例数据源插件", "author": "morning-insight", "version": "0.1.0",
        "description": "演示如何写一个数据源插件：从任意 JSON 接口拉取条目并转换为晨析素材格式。",
        "permissions": ["network"],
    },
    {
        "name": "push-example", "type": "push", "slug": "push-example",
        "title": "示例推送插件", "author": "morning-insight", "version": "0.1.0",
        "description": "演示如何写一个推送插件：把晨报以自定义格式发送到任意 HTTP 接口。",
        "permissions": ["network"],
    },
    {
        "name": "ai-example", "type": "ai", "slug": "ai-example",
        "title": "示例 AI 插件", "author": "morning-insight", "version": "0.1.0",
        "description": "演示如何写一个 AI 处理插件：对文本做自定义加工（如添加摘要、翻译、纠错）。",
        "permissions": ["llm"],
    },
]


# --------------------------------------------------------------------------- #
# 注册表维护
# --------------------------------------------------------------------------- #
def sync_from_disk(db: Session) -> int:
    """把磁盘上的插件登记进数据库（已存在的更新元信息，不覆盖用户的配置与开关）。"""
    count = 0
    for manifest in discover():
        row = db.scalar(select(Plugin).where(Plugin.name == manifest.name, Plugin.type == manifest.type))
        if row is None:
            row = Plugin(
                name=manifest.name, type=manifest.type, version=manifest.version,
                author=manifest.author, description=manifest.description,
                entry_point=manifest.entry_point, path=manifest.path,
                config_schema=manifest.config_schema, permissions=manifest.permissions,
                config=_default_config_from_schema(manifest.config_schema), enabled=False,
            )
            db.add(row)
        else:
            row.version = manifest.version
            row.author = manifest.author
            row.description = manifest.description
            row.entry_point = manifest.entry_point
            row.path = manifest.path
            row.config_schema = manifest.config_schema
            row.permissions = manifest.permissions
        count += 1
    db.commit()
    return count


def _default_config_from_schema(schema: dict) -> dict:
    out: dict = {}
    props = (schema or {}).get("properties") or {}
    for key, spec in props.items():
        if isinstance(spec, dict) and "default" in spec:
            out[key] = spec["default"]
    return out


def list_plugins(db: Session, plugin_type: str = "") -> list[dict]:
    stmt = select(Plugin)
    if plugin_type:
        stmt = stmt.where(Plugin.type == plugin_type)
    rows = db.scalars(stmt.order_by(Plugin.type, Plugin.name)).all()
    out = []
    for row in rows:
        manifest = PluginManifest(
            name=row.name, type=row.type, version=row.version, author=row.author,
            description=row.description, entry_point=row.entry_point,
            permissions=row.permissions or [], config_schema=row.config_schema or {},
            path=row.path,
        )
        ok, error = validate(manifest) if Path(row.path or "").exists() else (False, "插件目录不存在")
        out.append({
            "id": row.id, "name": row.name, "type": row.type, "version": row.version,
            "author": row.author, "description": row.description,
            "permissions": row.permissions or [], "config_schema": row.config_schema or {},
            "config": row.config or {}, "enabled": bool(row.enabled),
            "path": row.path, "installed_at": row.installed_at.isoformat() if row.installed_at else "",
            "valid": ok, "error": error,
        })
    return out


def install(db: Session, source: str) -> Plugin:
    """安装插件：source 可以是插件名（已放在 plugins/ 目录）或目录绝对路径。"""
    candidate = Path(source)
    if not candidate.is_absolute():
        candidate = plugin_root() / source
    if not candidate.exists() or not candidate.is_dir():
        raise PluginError(f"插件目录不存在：{candidate}")

    manifest = load_manifest(candidate)
    ok, error = validate(manifest)
    if not ok:
        raise PluginError(error)

    row = db.scalar(select(Plugin).where(Plugin.name == manifest.name, Plugin.type == manifest.type))
    if row is None:
        row = Plugin(name=manifest.name, type=manifest.type)
        db.add(row)
    row.version = manifest.version
    row.author = manifest.author
    row.description = manifest.description
    row.entry_point = manifest.entry_point
    row.path = manifest.path
    row.config_schema = manifest.config_schema
    row.permissions = manifest.permissions
    row.config = row.config or _default_config_from_schema(manifest.config_schema)
    db.commit()
    db.refresh(row)
    return row


def set_enabled(db: Session, plugin_id: int, enabled: bool) -> Plugin:
    row = db.get(Plugin, plugin_id)
    if row is None:
        raise PluginError("插件不存在")
    if enabled:
        manifest = load_manifest(Path(row.path))
        ok, error = validate(manifest)
        if not ok:
            raise PluginError(f"插件不可用，无法启用：{error}")
    row.enabled = bool(enabled)
    db.commit()
    db.refresh(row)
    return row


def uninstall(db: Session, plugin_id: int, *, remove_files: bool = False) -> None:
    row = db.get(Plugin, plugin_id)
    if row is None:
        raise PluginError("插件不存在")
    path = Path(row.path or "")
    db.delete(row)
    db.commit()
    if remove_files and path.exists() and path.parent.resolve() == plugin_root().resolve():
        # 只允许删除 plugins/ 目录下的一级子目录，避免误删
        shutil.rmtree(path, ignore_errors=True)


def update_config(db: Session, plugin_id: int, config: dict) -> Plugin:
    row = db.get(Plugin, plugin_id)
    if row is None:
        raise PluginError("插件不存在")
    merged = dict(row.config or {})
    merged.update(config or {})
    row.config = merged
    db.commit()
    db.refresh(row)
    return row


# --------------------------------------------------------------------------- #
# 运行时调用
# --------------------------------------------------------------------------- #
def _get_enabled(db: Session, name_or_id) -> Plugin | None:
    row = None
    if isinstance(name_or_id, int) or str(name_or_id).isdigit():
        row = db.get(Plugin, int(name_or_id))
    if row is None:
        row = db.scalar(select(Plugin).where(Plugin.name == str(name_or_id)))
    if row is None or not row.enabled:
        return None
    return row


def _load(row: Plugin):
    manifest = PluginManifest(
        name=row.name, type=row.type, version=row.version, author=row.author,
        description=row.description, entry_point=row.entry_point,
        permissions=row.permissions or [], config_schema=row.config_schema or {},
        path=row.path,
    )
    return load_module(manifest), manifest


def run_source_plugin(source: dict, since_hours: int = 24, limit: int = 60) -> list[dict]:
    """供抓取层调用：执行 source 类插件。source 需包含 `plugin` 字段（插件名或 ID）。"""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        row = _get_enabled(db, source.get("plugin") or source.get("name"))
        if row is None or row.type != "source":
            logger.warning("插件源未找到或未启用：%s", source.get("plugin"))
            return []
        module, manifest = _load(row)
        config = {**(row.config or {}), **(source.get("config") or {})}
        if source.get("url"):
            config.setdefault("url", source["url"])
        items = module.fetch(config, since_hours, limit)
        results = []
        for item in items or []:
            if not isinstance(item, dict) or not item.get("title") or not item.get("url"):
                continue
            item.setdefault("source", source.get("name") or manifest.name)
            results.append(item)
        return results
    except Exception as exc:
        logger.warning("插件源 %s 执行失败：%s", source.get("plugin"), exc)
        return []
    finally:
        db.close()


def run_push_plugin(db: Session, plugin_id: int, config: dict, msg) -> PushResult:
    row = _get_enabled(db, plugin_id)
    if row is None or row.type != "push":
        return PushResult(str(plugin_id), False, "推送插件未找到或未启用")
    name = row.name
    try:
        module, manifest = _load(row)
        name = manifest.name
        result = module.send(config or row.config or {}, msg)
    except Exception as exc:
        return PushResult(name, False, str(exc)[:300])
    if isinstance(result, PushResult):
        return result
    if isinstance(result, dict):
        return PushResult(name, bool(result.get("ok", True)), str(result.get("detail") or "已发送"))
    return PushResult(name, bool(result), "已发送" if result else "插件返回失败")


def run_ai_plugin(db: Session, plugin_id: int, prompt: str, text: str, config: dict | None = None) -> str:
    row = _get_enabled(db, plugin_id)
    if row is None or row.type != "ai":
        raise PluginError("AI 插件未找到或未启用")
    module, _ = _load(row)
    return str(module.process(prompt, text, {**(row.config or {}), **(config or {})}) or "")


def marketplace_catalog(db: Session) -> list[dict]:
    """插件市场：内置条目 + 数据库中记录的下载 / 评分。"""
    from ..models import MarketplaceItem

    out = []
    for entry in BUILTIN_MARKET_PLUGINS:
        row = db.scalar(select(MarketplaceItem).where(
            MarketplaceItem.slug == entry["slug"], MarketplaceItem.type == "plugin"
        ))
        installed = db.scalar(select(Plugin).where(
            Plugin.name == entry["name"], Plugin.type == entry["type"]
        ))
        out.append({
            **entry,
            "downloads": row.downloads if row else 0,
            "rating": row.rating if row else 0.0,
            "rating_count": row.rating_count if row else 0,
            "installed": installed is not None,
            "installed_enabled": bool(installed.enabled) if installed else False,
        })
    return out


def record_download(db: Session, slug: str) -> None:
    from ..models import MarketplaceItem

    row = db.scalar(select(MarketplaceItem).where(MarketplaceItem.slug == slug, MarketplaceItem.type == "plugin"))
    if row is None:
        row = MarketplaceItem(type="plugin", name=slug, slug=slug, downloads=0)
        db.add(row)
    row.downloads = (row.downloads or 0) + 1
    db.commit()
