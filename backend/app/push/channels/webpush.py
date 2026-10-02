"""Web Push 浏览器推送（VAPID）。

需要可选依赖：`pip install pywebpush`（会一并安装 cryptography）。
未安装时该渠道会返回明确提示，不影响其它渠道。

浏览器订阅信息由前端 `pushManager.subscribe()` 生成，POST 到
`/api/config/webpush/subscribe` 保存到本渠道配置的 `subscriptions` 字段。
"""
import base64
import json

from ..base import ChannelSpec, PushMessage, PushResult, register


def is_available() -> bool:
    try:
        import pywebpush  # noqa: F401

        return True
    except ImportError:
        return False


def generate_vapid_keys() -> dict:
    """生成一对 VAPID 密钥（P-256）。返回 {"private_key", "public_key"}。"""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要 cryptography：pip install pywebpush") from exc

    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(public_raw).decode("utf-8").rstrip("=")
    return {"private_key": private_pem, "public_key": public_b64}


def send(config: dict, msg: PushMessage) -> PushResult:
    if not is_available():
        return PushResult("webpush", False, "未安装 pywebpush，请执行：pip install pywebpush")

    from pywebpush import WebPushException, webpush

    subscriptions = config.get("subscriptions") or []
    if not subscriptions:
        return PushResult("webpush", False, "尚无浏览器订阅，请先在设置页点击「订阅浏览器通知」")
    private_key = (config.get("vapid_private_key") or "").strip()
    if not private_key:
        return PushResult("webpush", False, "缺少 VAPID 私钥，请在设置页点击「生成密钥」")
    subject = (config.get("vapid_subject") or "mailto:admin@example.com").strip()

    payload = json.dumps({
        "title": msg.title,
        "body": msg.plain()[:400],
        "url": msg.url or "/reports",
    }, ensure_ascii=False)

    ok, expired, errors = 0, [], []
    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
            )
            ok += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):  # 订阅已失效
                expired.append(sub.get("endpoint"))
            else:
                errors.append(str(exc)[:150])
        except Exception as exc:
            errors.append(str(exc)[:150])

    if expired:
        config["subscriptions"] = [s for s in subscriptions if s.get("endpoint") not in expired]
    if errors and not ok:
        return PushResult("webpush", False, "; ".join(errors)[:300])
    note = f"成功 {ok} 个"
    if expired:
        note += f"，清理失效订阅 {len(expired)} 个"
    return PushResult("webpush", True, note)


register(ChannelSpec(
    id="webpush", name="Web Push 浏览器推送",
    doc="在设置页点击「生成密钥」后，再点击「订阅本浏览器通知」并允许权限即可。"
        "需要 HTTPS 或 localhost 环境（浏览器限制）。",
    fields=[
        {"key": "vapid_public_key", "label": "VAPID 公钥", "type": "text", "readonly": True},
        {"key": "vapid_private_key", "label": "VAPID 私钥", "type": "password", "secret": True},
        {"key": "vapid_subject", "label": "联系邮箱（VAPID subject）", "type": "text",
         "placeholder": "mailto:you@example.com"},
    ],
    group="首发",
    send=send,
))
