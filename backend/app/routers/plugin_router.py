"""插件路由：安装 / 启用 / 禁用 / 卸载 / 配置 / 市场。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..plugins import (
    PluginError,
    install,
    list_plugins,
    marketplace_catalog,
    record_download,
    run_push_plugin,
    set_enabled,
    sync_from_disk,
    uninstall,
    update_config,
)
from ..plugins.base import KNOWN_PERMISSIONS, PLUGIN_TYPES
from ..plugins.loader import plugin_root
from ..push import PushMessage
from ..security import get_current_user, require_admin
from ..settings import PLUGIN_INSTALL_ENABLED

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("")
def list_items(type: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """列出已安装插件（含校验结果）。普通用户能看到有哪些插件可用。"""
    return {"plugins": list_plugins(db, plugin_type=type), "root": str(plugin_root())}


@router.post("/sync")
def sync(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """扫描插件目录并登记（管理员）。"""
    count = sync_from_disk(db)
    return {"ok": True, "count": count, "plugins": list_plugins(db)}


class InstallIn(BaseModel):
    source: str


@router.post("/install")
def install_plugin(data: InstallIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """安装插件（管理员）。

    source 为 plugins/ 下的目录名，或插件目录的绝对路径。
    注意：插件是本机 Python 代码，安装即代表允许其在本服务进程内执行；
    请仅安装你信任来源的插件。接口会返回插件的权限声明供核对。
    """
    if not PLUGIN_INSTALL_ENABLED:
        raise HTTPException(status_code=403, detail="插件安装已被管理员通过环境变量关闭（PLUGIN_INSTALL_ENABLED=false）")
    try:
        row = install(db, data.source)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    unknown = [p for p in (row.permissions or []) if p not in KNOWN_PERMISSIONS]
    return {
        "ok": True, "id": row.id, "name": row.name, "type": row.type,
        "version": row.version, "permissions": row.permissions or [],
        "warning": "该插件声明的权限：" + ("、".join(row.permissions or []) or "无")
                   + ("；未知权限：" + "、".join(unknown) if unknown else ""),
    }


class ToggleIn(BaseModel):
    enabled: bool


@router.post("/{plugin_id}/enable")
def toggle(plugin_id: int, data: ToggleIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        row = set_enabled(db, plugin_id, data.enabled)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "enabled": bool(row.enabled)}


class ConfigIn(BaseModel):
    config: dict


@router.put("/{plugin_id}/config")
def set_config(plugin_id: int, data: ConfigIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        row = update_config(db, plugin_id, data.config)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "config": row.config or {}}


@router.delete("/{plugin_id}")
def remove(plugin_id: int, remove_files: bool = False,
           user: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        uninstall(db, plugin_id, remove_files=remove_files)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/{plugin_id}/test")
def test_plugin(plugin_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """测试插件：推送类发一条测试消息，其它类型给出启用状态说明。"""
    rows = {p["id"]: p for p in list_plugins(db)}
    info = rows.get(plugin_id)
    if info is None:
        raise HTTPException(status_code=404, detail="插件不存在")
    if not info["enabled"]:
        raise HTTPException(status_code=400, detail="插件未启用，请先启用")
    if info["type"] != "push":
        return {"ok": True, "detail": f"{info['type']} 类插件无需单独测试，已启用并会在对应流程中被调用"}
    result = run_push_plugin(
        db, plugin_id, info.get("config") or {},
        PushMessage(title="晨析插件测试", content_md="## 插件测试\n\n推送插件已正确接入。", kind="test"),
    )
    return {"ok": result.ok, "detail": result.detail}


@router.get("/marketplace/catalog")
def marketplace(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """插件市场（内置收录 + 下载量 / 评分）。"""
    return {"items": marketplace_catalog(db), "install_enabled": PLUGIN_INSTALL_ENABLED,
            "types": list(PLUGIN_TYPES)}


@router.post("/marketplace/{slug}/install")
def install_from_market(slug: str, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not PLUGIN_INSTALL_ENABLED:
        raise HTTPException(status_code=403, detail="插件安装已关闭")
    try:
        row = install(db, slug)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=f"安装失败（请确认 plugins/{slug} 目录存在）：{exc}")
    record_download(db, slug)
    return {"ok": True, "id": row.id, "name": row.name, "type": row.type}
