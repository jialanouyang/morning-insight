"""Slack Incoming Webhook 推送。"""
import httpx

from ...utils.text import truncate
from ..base import ChannelSpec, PushMessage, PushResult, register

LIMIT = 3800


def send(config: dict, msg: PushMessage) -> PushResult:
    webhook = (config.get("webhook") or "").strip()
    if not webhook or not webhook.startswith("http"):
        return PushResult("slack", False, "缺少合法的 Webhook 地址")
    channel = (config.get("channel") or "").strip()

    text = truncate(msg.content_md, LIMIT, "\n\n…（内容过长已截断）")
    payload = {
        "text": f"*{msg.title}*\n\n{text}",
        "mrkdwn": True,
    }
    if channel:
        payload["channel"] = channel
    if msg.url:
        payload["blocks"] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{msg.title}*\n{truncate(text, 2800, '')}"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "查看完整晨报"}, "url": msg.url}
            ]},
        ]

    try:
        resp = httpx.post(webhook, json=payload, timeout=25.0)
        if resp.status_code >= 400:
            return PushResult("slack", False, f"返回 {resp.status_code}：{resp.text[:200]}")
    except Exception as exc:
        return PushResult("slack", False, f"请求失败：{exc}")
    return PushResult("slack", True, "已推送到 Slack")


register(ChannelSpec(
    id="slack", name="Slack",
    doc="在 Slack 中创建 App → 启用 Incoming Webhooks → 添加到目标频道 → 复制 Webhook URL。",
    fields=[
        {"key": "webhook", "label": "Webhook URL", "type": "password", "required": True, "secret": True,
         "placeholder": "https://hooks.slack.com/services/..."},
        {"key": "channel", "label": "目标频道（可选）", "type": "text", "placeholder": "#general"},
    ],
    send=send,
))
