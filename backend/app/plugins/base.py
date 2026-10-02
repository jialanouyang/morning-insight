"""插件接口定义与清单解析。

三类插件（文档 5.10）：
- source：数据源插件，实现 `fetch(config, since_hours, limit) -> list[dict]`
- push  ：推送插件，实现 `send(config, msg) -> dict|bool|None`
- ai    ：AI 插件，实现 `process(prompt, text, config) -> str`

插件以目录形式存在，`plugin.yaml` 声明元信息与权限，入口文件为 Python 模块。
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PLUGIN_TYPES = ("source", "push", "ai")
KNOWN_PERMISSIONS = ("network", "filesystem", "secrets", "llm", "subprocess")


@dataclass
class PluginManifest:
    name: str
    type: str
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    entry_point: str = "plugin.py"
    permissions: list[str] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name, "type": self.type, "version": self.version,
            "author": self.author, "description": self.description,
            "entry_point": self.entry_point, "permissions": self.permissions,
            "config_schema": self.config_schema, "path": self.path,
        }


class PluginError(RuntimeError):
    pass


def load_manifest(plugin_dir: Path) -> PluginManifest:
    """读取并校验 plugin.yaml。"""
    manifest_file = plugin_dir / "plugin.yaml"
    if not manifest_file.exists():
        manifest_file = plugin_dir / "plugin.yml"
    if not manifest_file.exists():
        raise PluginError(f"缺少 plugin.yaml：{plugin_dir}")

    try:
        data = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PluginError(f"plugin.yaml 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise PluginError("plugin.yaml 内容必须是键值对")

    name = str(data.get("name") or plugin_dir.name).strip()
    ptype = str(data.get("type") or "").strip().lower()
    if ptype not in PLUGIN_TYPES:
        raise PluginError(f"type 必须是 {PLUGIN_TYPES} 之一，当前为 {ptype!r}")

    entry = str(data.get("entry_point") or "plugin.py").strip()
    if not (plugin_dir / entry).exists():
        raise PluginError(f"入口文件不存在：{entry}")

    permissions = [str(p) for p in (data.get("permissions") or [])]
    unknown = [p for p in permissions if p not in KNOWN_PERMISSIONS]
    if unknown:
        raise PluginError(f"未知权限声明：{unknown}（可用：{KNOWN_PERMISSIONS}）")

    return PluginManifest(
        name=name, type=ptype, version=str(data.get("version") or "0.1.0"),
        author=str(data.get("author") or ""), description=str(data.get("description") or ""),
        entry_point=entry, permissions=permissions,
        config_schema=data.get("config_schema") or {}, path=str(plugin_dir),
    )
