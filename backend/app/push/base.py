"""推送层基础：消息对象、结果对象、渠道规格（供 Web UI 自动渲染配置表单）。

新增渠道只需：
1. 写一个 `send(config: dict, msg: PushMessage) -> PushResult` 函数
2. 在 `CHANNEL_SPECS` 里登记（含字段定义与获取参数的引导文案）

UI 会依据 fields 自动生成配置项与「测试推送」按钮。
"""
from dataclasses import dataclass, field
from typing import Callable

import markdown as md_lib

from ..utils.text import md_to_plain


@dataclass
class PushMessage:
    title: str
    content_md: str = ""
    content_html: str = ""
    url: str = ""
    attachments: list[dict] = field(default_factory=list)  # [{"path": ..., "name": ...}]
    kind: str = "report"  # report / periodical / alert / test

    def html(self) -> str:
        return self.content_html or render_html(self.content_md, self.title)

    def plain(self) -> str:
        return md_to_plain(self.content_md)


@dataclass
class PushResult:
    channel: str
    ok: bool
    detail: str = ""


def render_html(content_md: str, title: str = "", accent: str = "#F6A821") -> str:
    """把 Markdown 渲染为适合邮件 / 网页展示的 HTML。"""
    body = md_lib.markdown(
        content_md or "",
        extensions=["extra", "tables", "sane_lists", "nl2br"],
    )
    return f"""<div style="max-width:720px;margin:0 auto;font-family:-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;color:#25313f;line-height:1.75">
  <div style="border-left:4px solid {accent};padding:8px 0 8px 14px;margin-bottom:20px">
    <div style="font-size:20px;font-weight:700">{title or "晨析 Morning Insight"}</div>
    <div style="font-size:12px;color:#8b98a8">由 晨析 Morning Insight 自动生成</div>
  </div>
  <div style="font-size:15px">{body}</div>
  <div style="margin-top:28px;padding-top:12px;border-top:1px solid #e8ecf1;font-size:12px;color:#8b98a8">
    本邮件由开源项目 晨析 Morning Insight 发送
  </div>
</div>"""


@dataclass
class ChannelSpec:
    id: str
    name: str
    doc: str
    fields: list[dict]
    send: Callable[[dict, PushMessage], PushResult]
    group: str = "首发"  # 首发 / 扩展


CHANNEL_SPECS: list[ChannelSpec] = []
CHANNEL_MAP: dict[str, ChannelSpec] = {}


def register(spec: ChannelSpec) -> ChannelSpec:
    CHANNEL_SPECS.append(spec)
    CHANNEL_MAP[spec.id] = spec
    return spec


def channel_catalog() -> list[dict]:
    """给前端：全部渠道的元信息（不含函数）。"""
    return [
        {
            "id": s.id,
            "name": s.name,
            "doc": s.doc,
            "fields": s.fields,
            "group": s.group,
        }
        for s in CHANNEL_SPECS
    ]
