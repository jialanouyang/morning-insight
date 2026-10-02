"""飞书群机器人推送（支持加签，使用交互式卡片渲染 Markdown）。"""
import base64
import hashlib
import hmac
import time

import httpx

from ...utils.text import truncate
from ..base import ChannelSpec, PushMessage, PushResult, register

LIMIT = 4000


def _gen_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _chunks(text: str, size: int = LIMIT) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def send(config: dict, msg: PushMessage) -> PushResult:
    webhook = (config.get("webhook") or "").strip()
    if not webhook or not webhook.startswith("http"):
        return PushResult("feishu", False, "缺少合法的 Webhook 地址")

    secret = (config.get("secret") or "").strip()
    if secret:
        ts = str(int(time.time()))
        webhook = f"{webhook}&timestamp={ts}&sign={_gen_sign(ts, secret)}"

    errors: list[str] = []
    for idx, chunk in enumerate(_chunks(msg.content_md)):
        card_title = truncate(msg.title, 80) if idx == 0 else truncate(f"{msg.title}（续 {idx + 1}）", 80)
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": card_title},
                    "template": "orange",
                },
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": chunk}}],
            },
        }
        try:
            resp = httpx.post(webhook, json=payload, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") not in (0, None) and data.get("StatusCode") not in (0, None):
                errors.append(str(data)[:200])
        except Exception as exc:
            errors.append(str(exc))
            break
    if errors:
        return PushResult("feishu", False, "; ".join(errors)[:300])
    return PushResult("feishu", True, "已推送到飞书群")


register(ChannelSpec(
    id="feishu", name="飞书机器人",
    doc="飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人，复制 Webhook 地址。"
        "若开启「签名校验」，把密钥填到加签密钥处。",
    fields=[
        {"key": "webhook", "label": "Webhook 地址", "type": "password", "required": True, "secret": True,
         "placeholder": "https://open.feishu.cn/open-apis/bot/v2/hook/..."},
        {"key": "secret", "label": "加签密钥（可选）", "type": "password", "secret": True},
    ],
    send=send,
))
