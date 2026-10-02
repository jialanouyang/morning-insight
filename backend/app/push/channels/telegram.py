"""Telegram Bot 推送（支持发送语音晨报音频）。"""
import httpx

from ...utils.text import truncate
from ..base import ChannelSpec, PushMessage, PushResult, register

LIMIT = 3800


def _chunks(text: str, size: int = LIMIT) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def send(config: dict, msg: PushMessage) -> PushResult:
    token = (config.get("bot_token") or "").strip()
    chat_id = str(config.get("chat_id") or "").strip()
    if not token or not chat_id:
        return PushResult("telegram", False, "缺少 Bot Token 或 Chat ID")
    api = (config.get("api_base") or "https://api.telegram.org").rstrip("/")

    errors: list[str] = []
    for chunk in _chunks(msg.content_md):
        try:
            resp = httpx.post(
                f"{api}/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"<b>{msg.title}</b>\n\n{chunk}",
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=25.0,
            )
            data = resp.json()
            if not data.get("ok"):
                errors.append(str(data.get("description"))[:200])
        except Exception as exc:
            errors.append(str(exc))
            break

    # 附件：音频用 sendAudio（可显示为语音条），其它用 sendDocument
    for att in msg.attachments:
        path = att.get("path")
        if not path:
            continue
        try:
            is_audio = str(att.get("name", "")).lower().endswith((".mp3", ".ogg", ".m4a"))
            endpoint = "sendAudio" if is_audio else "sendDocument"
            field = "audio" if is_audio else "document"
            with open(path, "rb") as fh:
                resp = httpx.post(
                    f"{api}/bot{token}/{endpoint}",
                    data={"chat_id": chat_id},
                    files={field: (att.get("name") or "file", fh)},
                    timeout=120.0,
                )
            if not resp.json().get("ok"):
                errors.append(f"附件发送失败：{str(resp.json())[:150]}")
        except Exception as exc:
            errors.append(f"附件发送失败：{exc}")

    if errors:
        return PushResult("telegram", False, "; ".join(errors)[:300])
    return PushResult("telegram", True, "已推送到 Telegram")


register(ChannelSpec(
    id="telegram", name="Telegram Bot",
    doc="1) 在 Telegram 里找 @BotFather，发送 /newbot 创建机器人，拿到 Bot Token；"
        "2) 给机器人发一条消息；3) 用 @userinfobot 获取自己的 Chat ID（群聊需把机器人拉进群并用负数 ID）。"
        "国内网络需自行配置可访问 api.telegram.org 的网络环境，可填自定义 API 地址。",
    fields=[
        {"key": "bot_token", "label": "Bot Token", "type": "password", "required": True, "secret": True,
         "placeholder": "123456:ABC-DEF..."},
        {"key": "chat_id", "label": "Chat ID", "type": "text", "required": True, "placeholder": "123456789 或 -1001234567890"},
        {"key": "api_base", "label": "自定义 API 地址（可选）", "type": "text",
         "placeholder": "https://api.telegram.org"},
    ],
    send=send,
))
