"""扩展推送渠道（插件式）：Bark、Server 酱、PushPlus、LINE、通用 Webhook。

文档 5.5「扩展（插件式）」部分。微信个人号不直接对接，通过 Server 酱 / PushPlus 中转。
"""
import httpx

from ...utils.text import truncate
from ..base import ChannelSpec, PushMessage, PushResult, register


# --------------------------------------------------------------------------- #
# Bark（iOS）
# --------------------------------------------------------------------------- #
def send_bark(config: dict, msg: PushMessage) -> PushResult:
    key = (config.get("device_key") or "").strip()
    if not key:
        return PushResult("bark", False, "缺少 Bark 设备 Key")
    server = (config.get("server") or "https://api.day.app").rstrip("/")
    payload = {
        "title": msg.title,
        "body": truncate(msg.plain(), 1200, "…"),
        "group": config.get("group") or "晨析",
        "sound": config.get("sound") or "bell",
        "isArchive": 1,
    }
    if msg.url:
        payload["url"] = msg.url
    try:
        resp = httpx.post(f"{server}/{key}", json=payload, timeout=20.0)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code >= 400 or (data and data.get("code") not in (200, 0, None)):
            return PushResult("bark", False, f"{resp.status_code} {str(data)[:150]}")
    except Exception as exc:
        return PushResult("bark", False, f"请求失败：{exc}")
    return PushResult("bark", True, "已推送到 Bark")


register(ChannelSpec(
    id="bark", name="Bark（iOS）",
    doc="在 iPhone 上安装 Bark App，首页即可看到设备 Key。自建服务端可修改服务器地址。",
    fields=[
        {"key": "device_key", "label": "设备 Key", "type": "password", "required": True, "secret": True},
        {"key": "server", "label": "服务器地址", "type": "text", "default": "https://api.day.app"},
        {"key": "group", "label": "分组", "type": "text", "default": "晨析"},
        {"key": "sound", "label": "提示音", "type": "text", "default": "bell"},
    ],
    group="扩展", send=send_bark,
))


# --------------------------------------------------------------------------- #
# Server 酱（微信中转）
# --------------------------------------------------------------------------- #
def send_serverchan(config: dict, msg: PushMessage) -> PushResult:
    send_key = (config.get("send_key") or "").strip()
    if not send_key:
        return PushResult("serverchan", False, "缺少 SendKey")
    base = (config.get("server") or "https://sctapi.ftqq.com").rstrip("/")
    try:
        resp = httpx.post(
            f"{base}/{send_key}.send",
            data={"title": truncate(msg.title, 100), "desp": truncate(msg.content_md, 20000, "")},
            timeout=25.0,
        )
        data = resp.json()
    except Exception as exc:
        return PushResult("serverchan", False, f"请求失败：{exc}")
    if data.get("code") not in (0, None):
        return PushResult("serverchan", False, str(data)[:200])
    return PushResult("serverchan", True, "已通过 Server 酱推送到微信")


register(ChannelSpec(
    id="serverchan", name="Server 酱（微信中转）",
    doc="在 sct.ftqq.com 微信扫码登录后创建 SendKey。支持 Markdown（desp 字段）。"
        "微信个人号不直接对接，通过此渠道中转。",
    fields=[
        {"key": "send_key", "label": "SendKey", "type": "password", "required": True, "secret": True,
         "placeholder": "SCT..."},
        {"key": "server", "label": "服务地址", "type": "text", "default": "https://sctapi.ftqq.com"},
    ],
    group="扩展", send=send_serverchan,
))


# --------------------------------------------------------------------------- #
# PushPlus（微信中转）
# --------------------------------------------------------------------------- #
def send_pushplus(config: dict, msg: PushMessage) -> PushResult:
    token = (config.get("token") or "").strip()
    if not token:
        return PushResult("pushplus", False, "缺少 Token")
    base = (config.get("server") or "https://www.pushplus.plus").rstrip("/")
    template = (config.get("template") or "html").strip()
    if template == "html":  # 公众号卡片风（品牌橙 / 蓝，inline style）
        from ..wechat_style import render_wechat_card_html

        content = render_wechat_card_html(msg.content_md, msg.title)
    else:
        content = truncate(msg.content_md, 20000, "")
    payload = {
        "token": token,
        "title": truncate(msg.title, 100),
        "content": content,
        "template": template,
    }
    if config.get("topic"):
        payload["topic"] = config["topic"]
    if config.get("channel"):
        payload["channel"] = config["channel"]
    try:
        resp = httpx.post(f"{base}/send", json=payload, timeout=25.0)
        data = resp.json()
    except Exception as exc:
        return PushResult("pushplus", False, f"请求失败：{exc}")
    if data.get("code") not in (200, 0, None):
        return PushResult("pushplus", False, str(data)[:200])
    return PushResult("pushplus", True, "已通过 PushPlus 推送到微信")


register(ChannelSpec(
    id="pushplus", name="PushPlus（微信中转）",
    doc="在 pushplus.plus 微信扫码登录获取 Token。默认「公众号卡片」版式（品牌色），"
        "也可切换为 Markdown。群组推送需填写群组编码 topic。",
    fields=[
        {"key": "token", "label": "Token", "type": "password", "required": True, "secret": True},
        {"key": "template", "label": "版式", "type": "select", "default": "html",
         "options": [{"value": "html", "label": "公众号卡片（推荐）"},
                     {"value": "markdown", "label": "Markdown"}]},
        {"key": "topic", "label": "群组编码（可选）", "type": "text"},
        {"key": "server", "label": "服务地址", "type": "text", "default": "https://www.pushplus.plus"},
    ],
    group="扩展", send=send_pushplus,
))


# --------------------------------------------------------------------------- #
# LINE
# --------------------------------------------------------------------------- #
def send_line(config: dict, msg: PushMessage) -> PushResult:
    mode = (config.get("mode") or "messaging").strip()
    text = f"{msg.title}\n\n{truncate(msg.plain(), 4500, '…')}"

    if mode == "notify":  # 旧版 LINE Notify（官方已于 2025-03 停止服务，保留兼容）
        token = (config.get("notify_token") or "").strip()
        if not token:
            return PushResult("line", False, "缺少 LINE Notify Token")
        try:
            resp = httpx.post(
                "https://notify-api.line.me/api/notify",
                headers={"Authorization": f"Bearer {token}"},
                data={"message": truncate(text, 950, "…")},
                timeout=20.0,
            )
            if resp.status_code >= 400:
                return PushResult("line", False, f"{resp.status_code} {resp.text[:150]}")
        except Exception as exc:
            return PushResult("line", False, f"请求失败：{exc}")
        return PushResult("line", True, "已通过 LINE Notify 推送")

    token = (config.get("channel_access_token") or "").strip()
    to = (config.get("to") or "").strip()
    if not token or not to:
        return PushResult("line", False, "缺少 Channel Access Token 或接收者 ID")
    try:
        resp = httpx.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"to": to, "messages": [{"type": "text", "text": truncate(text, 4900, "…")}]},
            timeout=25.0,
        )
        if resp.status_code >= 400:
            return PushResult("line", False, f"{resp.status_code} {resp.text[:150]}")
    except Exception as exc:
        return PushResult("line", False, f"请求失败：{exc}")
    return PushResult("line", True, "已通过 LINE Messaging API 推送")


register(ChannelSpec(
    id="line", name="LINE（日韩 / 东南亚）",
    doc="推荐使用 LINE Messaging API：在 LINE Developers 创建 Messaging API 频道，"
        "获取 Channel Access Token，接收者为用户 / 群组 ID（U 或 C 开头）。"
        "LINE Notify 已于 2025 年停止服务，仅作兼容保留。",
    fields=[
        {"key": "mode", "label": "模式", "type": "select", "default": "messaging",
         "options": [{"value": "messaging", "label": "Messaging API（推荐）"},
                     {"value": "notify", "label": "LINE Notify（已停服，兼容用）"}]},
        {"key": "channel_access_token", "label": "Channel Access Token", "type": "password", "secret": True},
        {"key": "to", "label": "接收者 ID", "type": "text", "placeholder": "U1234... 或 C1234..."},
        {"key": "notify_token", "label": "LINE Notify Token（兼容）", "type": "password", "secret": True},
    ],
    group="扩展", send=send_line,
))


# --------------------------------------------------------------------------- #
# 通用 Webhook
# --------------------------------------------------------------------------- #
def send_webhook(config: dict, msg: PushMessage) -> PushResult:
    url = (config.get("url") or "").strip()
    if not url or not url.startswith("http"):
        return PushResult("webhook", False, "缺少合法的 URL")
    method = (config.get("method") or "POST").upper()

    payload = {
        "title": msg.title,
        "content_md": msg.content_md,
        "content_html": msg.html(),
        "content_text": msg.plain(),
        "url": msg.url,
        "kind": msg.kind,
    }
    template = (config.get("body_template") or "").strip()
    if template:  # 支持自定义 JSON 模板，用 {{title}} / {{content}} / {{content_text}} 占位
        from ...utils.text import truncate as _t

        rendered = (
            template.replace("{{title}}", msg.title.replace('"', "'"))
            .replace("{{content}}", msg.content_md.replace('"', "'").replace("\n", "\\n"))
            .replace("{{content_text}}", _t(msg.plain(), 2000, "").replace('"', "'").replace("\n", "\\n"))
            .replace("{{url}}", msg.url or "")
        )
        try:
            import json as _json

            payload = _json.loads(rendered)
        except Exception:
            return PushResult("webhook", False, "body_template 不是合法 JSON")
    if config.get("body"):
        payload.update(config["body"] if isinstance(config["body"], dict) else {})

    headers = {k: v for k, v in (config.get("headers") or {}).items() if k}
    if config.get("auth_header") and config.get("auth_value"):
        headers[config["auth_header"]] = config["auth_value"]

    try:
        if method == "GET":
            resp = httpx.get(url, params={"title": msg.title, "content": truncate(msg.plain(), 1500, "")},
                             headers=headers, timeout=25.0)
        else:
            resp = httpx.request(method, url, json=payload, headers=headers, timeout=25.0)
        if resp.status_code >= 400:
            return PushResult("webhook", False, f"返回 {resp.status_code}：{resp.text[:200]}")
    except Exception as exc:
        return PushResult("webhook", False, f"请求失败：{exc}")
    return PushResult("webhook", True, f"已调用 {method} {url}")


register(ChannelSpec(
    id="webhook", name="通用 Webhook",
    doc="把晨报 POST 到任意 HTTP 接口，可接入内部系统、自动化平台或自建服务。"
        "body_template 支持 {{title}} / {{content}} / {{content_text}} / {{url}} 占位符。",
    fields=[
        {"key": "url", "label": "URL", "type": "text", "required": True, "placeholder": "https://your-service/hook"},
        {"key": "method", "label": "方法", "type": "select", "default": "POST",
         "options": [{"value": "POST", "label": "POST"}, {"value": "PUT", "label": "PUT"},
                     {"value": "GET", "label": "GET"}]},
        {"key": "auth_header", "label": "鉴权 Header 名（可选）", "type": "text", "placeholder": "Authorization"},
        {"key": "auth_value", "label": "鉴权 Header 值（可选）", "type": "password", "secret": True},
        {"key": "body_template", "label": "自定义 JSON 模板（可选）", "type": "textarea"},
    ],
    group="扩展", send=send_webhook,
))
