"""Discord Webhook 推送（单条上限 2000 字符，自动分段）。"""
import httpx

from ...utils.text import truncate
from ..base import ChannelSpec, PushMessage, PushResult, register

LIMIT = 1900


def _chunks(text: str, size: int = LIMIT) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def send(config: dict, msg: PushMessage) -> PushResult:
    webhook = (config.get("webhook") or "").strip()
    if not webhook or not webhook.startswith("http"):
        return PushResult("discord", False, "缺少合法的 Webhook 地址")

    errors: list[str] = []
    for idx, chunk in enumerate(_chunks(msg.content_md)):
        content = f"**{msg.title}**\n\n{chunk}" if idx == 0 else chunk
        payload = {
            "content": truncate(content, 1990, ""),
            "username": config.get("username") or "晨析 Morning Insight",
        }
        try:
            resp = httpx.post(webhook, json=payload, timeout=25.0)
            if resp.status_code >= 400:
                errors.append(f"{resp.status_code}: {resp.text[:150]}")
                break
        except Exception as exc:
            errors.append(str(exc))
            break
    if errors:
        return PushResult("discord", False, "; ".join(errors)[:300])
    return PushResult("discord", True, "已推送到 Discord")


register(ChannelSpec(
    id="discord", name="Discord",
    doc="在 Discord 频道 → 编辑频道 → 整合 → Webhook → 新建 Webhook，复制 Webhook URL。",
    fields=[
        {"key": "webhook", "label": "Webhook URL", "type": "password", "required": True, "secret": True,
         "placeholder": "https://discord.com/api/webhooks/..."},
        {"key": "username", "label": "显示名称（可选）", "type": "text",
         "default": "晨析 Morning Insight"},
    ],
    send=send,
))
