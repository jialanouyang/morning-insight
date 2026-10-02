"""推送层：13 个内置渠道 + 调度与失败隔离。"""
from . import channels  # noqa: F401  触发渠道注册
from .base import CHANNEL_MAP, CHANNEL_SPECS, ChannelSpec, PushMessage, PushResult, channel_catalog, render_html
from .dispatcher import (
    default_push_config,
    dispatch,
    enabled_channels,
    mask_push_config,
    merge_push_config,
    send_one,
    test_channel,
)

__all__ = [
    "CHANNEL_MAP", "CHANNEL_SPECS", "ChannelSpec", "PushMessage", "PushResult",
    "channel_catalog", "render_html",
    "default_push_config", "dispatch", "enabled_channels", "mask_push_config",
    "merge_push_config", "send_one", "test_channel",
]
