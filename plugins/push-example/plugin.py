"""示例推送插件。

接口约定：
    send(config: dict, msg) -> dict | bool | PushResult
    msg 是 app.push.base.PushMessage，提供 title / content_md / content_html / plain() / html() / attachments

返回 dict 时支持 {"ok": bool, "detail": str}。
"""
import httpx


def send(config: dict, msg) -> dict:
    url = (config.get("url") or "").strip()
    if not url or not url.startswith("http"):
        return {"ok": False, "detail": "未配置目标接口地址"}

    mode = (config.get("mode") or "json").strip().lower()
    headers = {"Content-Type": "application/json"}
    token = (config.get("token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Morning-Insight-Signature"] = token[:8]  # 演示自定义签名头

    if mode == "markdown":
        payload = {"text": f"# {msg.title}\n\n{msg.content_md}"}
    else:
        payload = {
            "title": msg.title,
            "markdown": msg.content_md,
            "html": msg.html(),
            "text": msg.plain(),
            "kind": msg.kind,
            "attachments": [a.get("name") for a in (msg.attachments or [])],
        }

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=25.0)
    except Exception as exc:
        return {"ok": False, "detail": f"请求失败：{exc}"}
    if resp.status_code >= 400:
        return {"ok": False, "detail": f"接口返回 {resp.status_code}：{resp.text[:200]}"}
    return {"ok": True, "detail": f"已发送到 {url}"}
