"""邮件推送（SMTP）。"""
import smtplib
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from ..base import ChannelSpec, PushMessage, PushResult, register


def send(config: dict, msg: PushMessage) -> PushResult:
    host = (config.get("smtp_host") or "").strip()
    port = int(config.get("smtp_port") or 465)
    user = (config.get("smtp_user") or "").strip()
    password = config.get("smtp_pass") or ""
    to_list = [t.strip() for t in (config.get("to") or []) if str(t).strip()]
    use_ssl = bool(config.get("use_ssl", True))
    sender_name = config.get("from_name") or "晨析 Morning Insight"

    if not (host and user and password and to_list):
        return PushResult("email", False, "SMTP 配置不完整：需要服务器、账号、密码与收件人")

    root = MIMEMultipart("alternative")
    root["Subject"] = Header(msg.title or "晨析晨报", "utf-8")
    root["From"] = formataddr((str(sender_name), user))
    root["To"] = ", ".join(to_list)
    root.attach(MIMEText(msg.plain(), "plain", "utf-8"))
    root.attach(MIMEText(msg.html(), "html", "utf-8"))

    if msg.attachments:
        mixed = MIMEMultipart("mixed")
        mixed.attach(root)
        for att in msg.attachments:
            path = att.get("path")
            if not path:
                continue
            try:
                with open(path, "rb") as fh:
                    part = MIMEApplication(fh.read())
                part.add_header(
                    "Content-Disposition", "attachment",
                    filename=("utf-8", "", att.get("name") or "attachment"),
                )
                mixed.attach(part)
            except OSError:
                continue
        root = mixed

    try:
        if use_ssl:
            client = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            client = smtplib.SMTP(host, port, timeout=30)
            try:
                client.starttls()
            except smtplib.SMTPException:
                pass
        try:
            client.login(user, password)
            client.sendmail(user, to_list, root.as_string())
        finally:
            try:
                client.quit()
            except Exception:
                pass
    except Exception as exc:
        return PushResult("email", False, f"发送失败：{exc}")
    return PushResult("email", True, f"已发送至 {len(to_list)} 个收件人")


register(ChannelSpec(
    id="email", name="邮件 SMTP",
    doc="在邮箱设置中开启 SMTP 服务并获取授权码。常见配置：QQ 邮箱 smtp.qq.com:465(SSL)、"
        "163 邮箱 smtp.163.com:465(SSL)、Gmail smtp.gmail.com:587(STARTTLS)。",
    fields=[
        {"key": "smtp_host", "label": "SMTP 服务器", "type": "text", "required": True, "placeholder": "smtp.qq.com"},
        {"key": "smtp_port", "label": "端口", "type": "number", "required": True, "default": 465},
        {"key": "smtp_user", "label": "发件邮箱", "type": "text", "required": True, "placeholder": "you@example.com"},
        {"key": "smtp_pass", "label": "授权码 / 密码", "type": "password", "required": True, "secret": True},
        {"key": "use_ssl", "label": "使用 SSL", "type": "boolean", "default": True},
        {"key": "from_name", "label": "发件人显示名", "type": "text", "default": "晨析 Morning Insight"},
        {"key": "to", "label": "收件人", "type": "list", "required": True,
         "hint": "多个收件人用逗号分隔"},
    ],
    send=send,
))
