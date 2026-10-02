"""企业微信群机器人推送。

排版走 wechat_style.format_wecom：栏目头橙色高亮、元信息灰色，
按章节 + UTF-8 字节双重切块（机器人单条上限 4096 字节，中文按 3 字节计），
不会把一条新闻从中间切断。
"""
import httpx

from ..base import ChannelSpec, PushMessage, PushResult, register
from ..wechat_style import format_wecom


def send(config: dict, msg: PushMessage) -> PushResult:
    webhook = (config.get("webhook") or "").strip()
    if not webhook:
        return PushResult("wecom", False, "缺少 Webhook 地址")
    if not webhook.startswith("http"):
        return PushResult("wecom", False, "Webhook 地址不合法")

    errors = []
    messages = format_wecom(msg.content_md, msg.title)
    for chunk in messages:
        try:
            resp = httpx.post(
                webhook,
                json={"msgtype": "markdown", "markdown": {"content": chunk}},
                timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") not in (0, None):
                errors.append(f"errcode={data.get('errcode')} {data.get('errmsg')}")
                break
        except Exception as exc:
            errors.append(str(exc))
            break
    if errors:
        return PushResult("wecom", False, "; ".join(errors)[:300])
    return PushResult("wecom", True, f"已推送到企业微信群（{len(messages)} 条消息）")


register(ChannelSpec(
    id="wecom", name="企业微信机器人",
    doc="在企业微信群 → 群设置 → 群机器人 → 添加机器人，复制 Webhook 地址。"
        "晨报自动排版为微信版式（栏目高亮 + 卡片条目），超长自动分多条发送。",
    fields=[{"key": "webhook", "label": "Webhook 地址", "type": "password", "required": True, "secret": True,
             "placeholder": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."}],
    send=send,
))
