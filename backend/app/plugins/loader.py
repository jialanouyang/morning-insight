"""插件加载器：扫描目录、动态导入入口模块、校验接口实现。

安全说明：插件是本地 Python 代码，加载即执行（与所有自托管插件系统一致）。
`permissions` 为**声明式**权限标记，用于安装前提示用户，不做运行期沙箱限制。
因此 `PLUGIN_INSTALL_ENABLED` 默认虽为开启，界面仍要求用户显式确认后才安装。
"""
import importlib.util
import logging
from pathlib import Path

from ..settings import PLUGIN_DIR
from .base import PluginError, PluginManifest, load_manifest

logger = logging.getLogger("morning_insight.plugins")

REQUIRED_FUNCS = {"source": "fetch", "push": "send", "ai": "process"}


def plugin_root() -> Path:
    path = Path(PLUGIN_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def discover() -> list[PluginManifest]:
    """扫描插件目录，返回所有可用的插件清单（跳过解析失败的目录并记录原因）。"""
    manifests: list[PluginManifest] = []
    root = plugin_root()
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        try:
            manifests.append(load_manifest(child))
        except PluginError as exc:
            logger.warning("跳过插件目录 %s：%s", child.name, exc)
    return manifests


def load_module(manifest: PluginManifest, module_name: str | None = None):
    """按入口文件动态导入模块。"""
    entry = Path(manifest.path) / manifest.entry_point
    if not entry.exists():
        raise PluginError(f"入口文件不存在：{entry}")
    mod_name = module_name or f"morning_insight_plugin_{manifest.type}_{manifest.name}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(mod_name, entry)
    if spec is None or spec.loader is None:
        raise PluginError(f"无法加载插件模块：{entry}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise PluginError(f"插件导入失败：{exc}") from exc

    required = REQUIRED_FUNCS.get(manifest.type)
    if required and not callable(getattr(module, required, None)):
        raise PluginError(f"{manifest.type} 类插件必须实现 {required}() 函数")
    return module


def validate(manifest: PluginManifest) -> tuple[bool, str]:
    try:
        load_module(manifest)
        return True, ""
    except PluginError as exc:
        return False, str(exc)
