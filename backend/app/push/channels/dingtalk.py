"""钉钉群机器人推送（支持加签）。"""
import base64
import hashlib
import hmac
import time
import urllib.parse

import httpx

from ...utils.text import truncate
from ..base import ChannelSpec, PushMessage, PushResult, register

LIMIT = 18000


def _sign(webhook: str, secret: str) -> str:
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={timestamp}&sign={sign}"


def send(config: dict, msg: PushMessage) -> PushResult:
    webhook = (config.get("webhook") or "").strip()
    if not webhook or not webhook.startswith("http"):
        return PushResult("dingtalk", False, "缺少合法的 Webhook 地址")
    secret = (config.get("secret") or "").strip()
    url = _sign(webhook, secret) if secret else webhook

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": truncate(msg.title, 60), "text": truncate(msg.content_md, LIMIT, "")},
    }
    if config.get("at_mobiles"):
        mobiles = config["at_mobiles"]
        if isinstance(mobiles, str):
            mobiles = [m.strip() for m in mobiles.split(",") if m.strip()]
        payload["at"] = {"atMobiles": mobiles, "isAtAll": bool(config.get("at_all"))}
    elif config.get("at_all"):
        payload["at"] = {"isAtAll": True}

    try:
        resp = httpx.post(url, json=payload, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return PushResult("dingtalk", False, f"请求失败：{exc}")
    if data.get("errcode") not in (0, None):
        return PushResult("dingtalk", False, f"errcode={data.get('errcode')} {data.get('errmsg')}")
    return PushResult("dingtalk", True, "已推送到钉钉群")


register(ChannelSpec(
    id="dingtalk", name="钉钉机器人",
    doc="钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义。"
        "安全设置若选「加签」，把 SEC 开头的密钥填到加签密钥处。",
    fields=[
        {"key": "webhook", "label": "Webhook 地址", "type": "password", "required": True, "secret": True,
         "placeholder": "https://oapi.dingtalk.com/robot/send?access_token=..."},
        {"key": "secret", "label": "加签密钥（可选）", "type": "password", "secret": True,
         "placeholder": "SEC..."},
        {"key": "at_mobiles", "label": "@ 手机号（可选）", "type": "list", "hint": "多个用逗号分隔"},
        {"key": "at_all", "label": "@ 所有人", "type": "boolean", "default": False},
    ],
    send=send,
))
