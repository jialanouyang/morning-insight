"""插件系统：数据源插件 / 推送插件 / AI 插件。

- `base`     接口定义与 plugin.yaml 清单
- `loader`   目录扫描与动态导入
- `registry` 安装 / 启用 / 禁用 / 卸载 / 调用 / 市场

安全提示：插件是本机 Python 代码，加载即执行。`permissions` 为声明式标记，
安装前界面会展示权限清单并要求用户确认。
"""
from .base import KNOWN_PERMISSIONS, PLUGIN_TYPES, PluginError, PluginManifest, load_manifest
from .loader import discover, load_module, plugin_root, validate
from .registry import (
    BUILTIN_MARKET_PLUGINS,
    install,
    list_plugins,
    marketplace_catalog,
    record_download,
    run_ai_plugin,
    run_push_plugin,
    run_source_plugin,
    set_enabled,
    sync_from_disk,
    uninstall,
    update_config,
)

__all__ = [
    "KNOWN_PERMISSIONS", "PLUGIN_TYPES", "PluginError", "PluginManifest", "load_manifest",
    "discover", "load_module", "plugin_root", "validate",
    "BUILTIN_MARKET_PLUGINS", "install", "list_plugins", "marketplace_catalog",
    "record_download", "run_ai_plugin", "run_push_plugin", "run_source_plugin",
    "set_enabled", "sync_from_disk", "uninstall", "update_config",
]
