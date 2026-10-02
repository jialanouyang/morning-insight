"""推送调度：多渠道独立发送 + 失败隔离 + 推送记录入库。"""
import logging

from sqlalchemy.orm import Session

from ..models import PushLog
from .base import CHANNEL_MAP, CHANNEL_SPECS, PushMessage, PushResult, channel_catalog

logger = logging.getLogger("morning_insight.push")


def default_push_config() -> dict:
    """所有渠道的默认配置（默认全部关闭，与文档「推送渠道默认全部显示」一致）。"""
    cfg: dict = {}
    for spec in CHANNEL_SPECS:
        item: dict = {"enabled": False}
        for f in spec.fields:
            if "default" in f:
                item[f["key"]] = f["default"]
            elif f["type"] == "list":
                item[f["key"]] = []
            elif f["type"] == "boolean":
                item[f["key"]] = False
            else:
                item[f["key"]] = ""
        cfg[spec.id] = item
    return cfg


def merge_push_config(current: dict | None, incoming: dict | None) -> dict:
    """合并推送配置，保留未提交的渠道，并处理密钥掩码占位 "***"。"""
    merged = default_push_config()
    merged.update(current or {})
    for channel_id, values in (incoming or {}).items():
        if channel_id not in merged:
            merged[channel_id] = {}
        secret_keys = {f["key"] for f in CHANNEL_MAP.get(channel_id, None).fields if f.get("secret")} if channel_id in CHANNEL_MAP else set()
        target = dict(merged.get(channel_id) or {})
        for key, value in (values or {}).items():
            if key in secret_keys and value == "***":
                continue  # 掩码表示保持原值
            target[key] = value
        merged[channel_id] = target
    return merged


def mask_push_config(cfg: dict | None) -> dict:
    """读取时掩码敏感字段，避免密钥回传到前端。"""
    out: dict = {}
    for channel_id, values in (cfg or {}).items():
        spec = CHANNEL_MAP.get(channel_id)
        secret_keys = {f["key"] for f in spec.fields if f.get("secret")} if spec else set()
        masked = dict(values or {})
        for key in secret_keys:
            if masked.get(key):
                masked[key] = "***"
        out[channel_id] = masked
    return out


def enabled_channels(push_config: dict | None) -> list[str]:
    return [
        cid for cid, values in (push_config or {}).items()
        if isinstance(values, dict) and values.get("enabled") and cid in CHANNEL_MAP
    ]


def send_one(channel_id: str, config: dict, msg: PushMessage) -> PushResult:
    spec = CHANNEL_MAP.get(channel_id)
    if spec is None:
        return PushResult(channel_id, False, f"未知渠道：{channel_id}")
    try:
        return spec.send(dict(config or {}), msg)
    except Exception as exc:  # 任一渠道异常都不应中断其它渠道
        logger.warning("渠道 %s 发送异常：%s", channel_id, exc)
        return PushResult(channel_id, False, str(exc)[:300])


def dispatch(
    db: Session | None,
    user_id: int,
    push_config: dict | None,
    msg: PushMessage,
    *,
    report_id: int | None = None,
    periodical_id: int | None = None,
    channels: list[str] | None = None,
) -> list[PushResult]:
    """向所有启用渠道推送（或指定渠道），逐条记录 push_logs。

    一个渠道失败不影响其它渠道（文档 5.5 明确要求）。
    """
    targets = channels if channels is not None else enabled_channels(push_config)
    results: list[PushResult] = []
    for channel_id in targets:
        config = (push_config or {}).get(channel_id) or {}
        if channels is None and not config.get("enabled"):
            continue
        result = send_one(channel_id, config, msg)
        results.append(result)
        if db is not None:
            try:
                db.add(PushLog(
                    user_id=user_id,
                    report_id=report_id,
                    periodical_id=periodical_id,
                    kind=msg.kind,
                    channel=channel_id,
                    status="success" if result.ok else "failed",
                    error="" if result.ok else result.detail[:1000],
                ))
                db.commit()
            except Exception as exc:
                logger.debug("写入推送记录失败：%s", exc)
    return results


def test_channel(channel_id: str, config: dict, msg: PushMessage | None = None) -> PushResult:
    msg = msg or PushMessage(
        title="晨析测试推送",
        content_md="## 测试成功\n\n这是一条来自 **晨析 Morning Insight** 的测试推送。\n\n"
                   "- 渠道配置正确\n- 内容渲染正常\n\n配置完成后即可在晨报生成时自动推送。",
        kind="test",
    )
    return send_one(channel_id, config, msg)


__all__ = [
    "CHANNEL_SPECS", "CHANNEL_MAP", "PushMessage", "PushResult",
    "channel_catalog", "default_push_config", "merge_push_config", "mask_push_config",
    "enabled_channels", "dispatch", "send_one", "test_channel",
]
