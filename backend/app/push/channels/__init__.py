"""导入全部内置渠道以完成注册。新增渠道文件请在此处 import。"""
from . import dingtalk, discord, email, feishu, misc, slack, telegram, wecom, webpush  # noqa: F401

__all__ = ["dingtalk", "discord", "email", "feishu", "misc", "slack", "telegram", "wecom", "webpush"]
