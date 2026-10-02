"""微信渠道排版：把晨报 Markdown 渲染成微信友好的版式。

两套渲染（参考公众号推文版式，色彩沿用品牌橙 #F6A821 / 品牌蓝 #2B9CD8）：

1. ``format_wecom(md)`` —— 企业微信群机器人 Markdown 方言：
   - 仅使用机器人支持的语法（标题 / 加粗 / 链接 / 引用 / <font color=...>）
   - 三色限制：warning(橙红) 做栏目头、comment(灰) 做元信息
   - **按 UTF-8 字节切块**（单条上限 4096 字节，此处留余量取 3800），
     且只在章节边界切分，不切断条目
2. ``render_wechat_card_html(md)`` —— 公众号卡片风 HTML（PushPlus / 邮件 / 内嵌预览用）：
   - 全部 inline style，不依赖外部 CSS（微信内嵌浏览器可完整渲染）
   - 顶部品牌色横幅 + 日期条 + 橙色栏目条 + 卡片式条目 + 蓝色来源标签
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import re

# 品牌色
ORANGE = "#F6A821"
ORANGE_DARK = "#E08E06"
ORANGE_BG = "#FFF7EA"
BLUE = "#2B9CD8"
INK = "#25313F"
GRAY = "#8B98A8"
CARD_BG = "#FCFBF8"
CARD_BORDER = "#F3E3C8"

WEEKDAYS = "一二三四五六日"

# 企业微信机器人单条 Markdown 上限 4096 字节（UTF-8），留余量
WECOM_BYTE_LIMIT = 3800

_DATE_IN_TITLE_RE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})")
_LIST_MARKER_RE = re.compile(r"^(?:(\d+)[.、)]|[-*•])\s+(.*)$", re.S)
_LINK_ITEM_RE = re.compile(r"^\[(.+?)\]\((https?://\S+?)\)（(.+?)）\s*[:：]?\s*(.*)$", re.S)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


# --------------------------------------------------------------------------- #
# 晨报 Markdown 结构解析（AI 版 / 素材版两种结构都兼容）
# --------------------------------------------------------------------------- #
class Item:
    """一条条目：链接式（素材版）或纯文本式（AI 版）。"""

    __slots__ = ("text", "url", "source", "summary", "num")

    def __init__(self, text: str = "", url: str = "", source: str = "", summary: str = "", num: str = ""):
        self.text, self.url, self.source, self.summary, self.num = text, url, source, summary, num


class Section:
    __slots__ = ("title", "quotes", "blocks")

    def __init__(self, title: str = ""):
        self.title = title
        self.quotes: list[str] = []
        self.blocks: list[tuple[str, object]] = []  # ("item", Item) / ("para", str)


def parse_report_md(md: str, fallback_title: str = "") -> tuple[str, list[str], list[Section]]:
    """解析晨报 Markdown → (标题, 引言引用, 章节列表)。"""
    title = fallback_title
    intro_quotes: list[str] = []
    sections: list[Section] = []
    cur: Section | None = None

    for raw in (md or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
        elif line.startswith("## "):
            cur = Section(line[3:].strip())
            sections.append(cur)
        elif line.startswith(">"):
            q = line.lstrip(">").strip()
            (cur.quotes if cur else intro_quotes).append(q)
        else:
            if cur is None:
                cur = Section("")
                sections.append(cur)
            m = _LIST_MARKER_RE.match(line)
            if m:
                num, rest = m.group(1) or "", m.group(2).strip()
                lm = _LINK_ITEM_RE.match(rest)
                if lm:
                    it = Item(num=lm.group(1) if not num and lm else num, text=lm.group(1),
                              url=lm.group(2), source=lm.group(3), summary=lm.group(4).strip())
                    it.num = num or lm.group(1)
                    cur.blocks.append(("item", it))
                else:
                    cur.blocks.append(("item", Item(num=num, text=rest)))
            else:
                cur.blocks.append(("para", line))
    return title, intro_quotes, sections


def _report_date(doc_title: str) -> str:
    m = _DATE_IN_TITLE_RE.search(doc_title or "")
    if m:
        try:
            d = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return f"{d.isoformat()} · 星期{WEEKDAYS[d.weekday()]}"
        except ValueError:
            pass
    return _dt.date.today().isoformat()


# --------------------------------------------------------------------------- #
# 一、企业微信机器人 Markdown
# --------------------------------------------------------------------------- #
def _wecom_inline(text: str) -> str:
    """WeCom 方言内联转换：去掉不支持的写法，保留加粗与链接。"""
    text = _BOLD_RE.sub(r"**\1**", text or "")
    return text.strip()


def _wecom_item_lines(it: Item) -> list[str]:
    if it.url:
        head = f"{it.num + '. ' if it.num else ''}[{_wecom_inline(it.text)}]({it.url})"
        lines = [head]
        meta = " · ".join(x for x in (f"来源：{it.source}" if it.source else "",) if x)
        if it.summary:
            meta = (meta + "｜" if meta else "") + it.summary[:100]
        if meta:
            lines.append(f'<font color="comment">{meta}</font>')
        return lines
    return [f"{it.num + '. ' if it.num else ''}{_wecom_inline(it.text)}"]


def format_wecom(md: str, title: str = "") -> list[str]:
    """把晨报 Markdown 排版为企业微信机器人消息列表（按字节、按章节切块）。"""
    doc_title, intro_quotes, sections = parse_report_md(md, title)
    date_str = _report_date(doc_title)

    pieces: list[str] = []
    pieces.append(
        f'**<font color="warning">☀ 晨析 MORNING INSIGHT</font>**\n'
        f'<font color="comment">{date_str} · 行业分析晨报</font>'
    )
    for q in intro_quotes[:3]:
        pieces.append(f"> {_wecom_inline(q)}")

    for sec in sections:
        buf: list[str] = []
        if sec.title:
            buf.append(f'**<font color="warning">▎{sec.title}</font>**')
        for q in sec.quotes[:2]:
            buf.append(f"> {_wecom_inline(q)}")
        for kind, payload in sec.blocks:
            if kind == "item":
                buf.extend(_wecom_item_lines(payload))
            else:
                text = _wecom_inline(str(payload))
                if text in ("（无新动态）", "(无新动态)"):
                    buf.append('<font color="comment">（无新动态）</font>')
                else:
                    buf.append(text)
            buf.append("")  # 条目间空行
        pieces.append("\n".join(buf).strip())

    # 抬头（pieces[0]）与引言/首个章节合并，避免出现「只有抬头」的孤消息
    if len(pieces) > 1:
        pieces[0] = pieces[0] + "\n\n" + pieces[1]
        del pieces[1]

    return _pack_by_bytes(pieces, WECOM_BYTE_LIMIT)


def _pack_by_bytes(pieces: list[str], limit: int) -> list[str]:
    """把片段按 UTF-8 字节数装箱；单个片段超限时按行二次切分。"""
    def blen(s: str) -> int:
        return len(s.encode("utf-8"))

    messages: list[str] = []
    box: list[str] = []

    def flush():
        if box:
            messages.append("\n\n".join(box).strip())
            box.clear()

    for piece in pieces:
        if blen(piece) > limit:  # 单片段超限：按行硬切
            flush()
            lines = piece.split("\n")
            part: list[str] = []
            for ln in lines:
                if blen("\n".join(part + [ln])) > limit and part:
                    messages.append("\n".join(part))
                    part = [ln]
                else:
                    part.append(ln)
            if part:
                messages.append("\n".join(part))
            continue
        if blen("\n\n".join(box + [piece])) > limit:
            flush()
        box.append(piece)
    flush()
    return [m for m in messages if m.strip()]


# --------------------------------------------------------------------------- #
# 二、公众号卡片风 HTML（inline style，品牌色）
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return _html.escape(text or "", quote=False)


def _inline_html(text: str, *, link_color: str = INK) -> str:
    """内联 Markdown → HTML：**加粗**、[链接](url)。"""
    out = _esc(text)

    def _link(m: "re.Match[str]") -> str:
        return f'<a href="{m.group(2)}" style="color:{link_color};text-decoration:none;border-bottom:1px solid {ORANGE};">{m.group(1)}</a>'

    out = _MD_LINK_RE.sub(_link, out)
    out = _BOLD_RE.sub(r"<strong>\1</strong>", out)
    return out


def render_wechat_card_html(md: str, title: str = "", max_bytes: int | None = 30000) -> str:
    """渲染为公众号卡片风 HTML 片段（可直接内嵌，无 <html> 外壳）。

    max_bytes：超过时从末尾丢弃整张卡片并追加「部分内容省略」提示，
    保证 HTML 标签不被截断（PushPlus / 邮件正文有长度限制）。
    """
    doc_title, intro_quotes, sections = parse_report_md(md, title)
    date_str = _report_date(doc_title)

    p: list[str] = []

    # 顶部品牌横幅（橙底 + 蓝条）
    p.append(f"""
<div style="background:{ORANGE};border-radius:12px 12px 0 0;padding:32px 20px 28px;text-align:center;">
  <div style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:10px;text-indent:10px;">晨 析</div>
  <div style="font-size:11px;color:rgba(255,255,255,.88);letter-spacing:4px;margin-top:10px;text-indent:4px;">MORNING INSIGHT</div>
</div>
<div style="background:{BLUE};height:4px;"></div>
<div style="text-align:center;padding:18px 16px 4px;font-size:13px;color:{GRAY};">{_esc(date_str)} · 行业分析晨报</div>""")

    # 引言（素材版的「未启用 AI」等提示）
    for q in intro_quotes[:3]:
        p.append(f"""
<div style="margin:14px 16px 0;background:{ORANGE_BG};border:1px dashed {ORANGE};border-radius:10px;padding:12px 14px;font-size:13px;color:#9a7b2f;line-height:1.75;">{_inline_html(q)}</div>""")

    index = 0
    for sec in sections:
        # 栏目头：橙色竖条 + 加粗标题
        head = (
            f'<span style="display:inline-block;width:5px;height:18px;background:{ORANGE};'
            f'border-radius:2px;margin-right:8px;vertical-align:-3px;"></span>'
            f'<span style="font-size:17px;font-weight:700;color:#1f2b38;">{_esc(sec.title)}</span>'
        ) if sec.title else ""
        p.append(f'<div style="margin:26px 16px 12px;">{head}</div>')

        for q in sec.quotes[:2]:
            p.append(f"""
<div style="margin:0 16px 12px;background:{ORANGE_BG};border-left:3px solid {ORANGE};border-radius:0 10px 10px 0;padding:10px 14px;font-size:13px;color:#9a7b2f;line-height:1.75;">{_inline_html(q)}</div>""")

        pending = []
        for kind, payload in sec.blocks:
            index += 1
            if kind == "item":
                it: Item = payload
                if it.url:
                    num_html = (
                        f'<span style="color:{ORANGE_DARK};font-size:13px;font-weight:700;margin-right:6px;">{int(it.num or index):02d}</span>'
                        if (it.num or "").isdigit() else
                        f'<span style="color:{ORANGE_DARK};font-size:13px;font-weight:700;margin-right:6px;">{index:02d}</span>'
                    )
                    body = (
                        f'<div style="font-size:15px;font-weight:700;line-height:1.55;color:{INK};">'
                        f'{num_html}<a href="{_esc(it.url)}" style="color:{INK};text-decoration:none;">{_inline_html(it.text, link_color=INK)}</a></div>'
                    )
                    if it.source:
                        body += (
                            f'<div style="margin-top:8px;"><span style="display:inline-block;background:{BLUE};color:#ffffff;'
                            f'font-size:11px;line-height:19px;padding:0 9px;border-radius:10px;">{_esc(it.source)}</span></div>'
                        )
                    if it.summary:
                        body += (
                            f'<div style="margin-top:8px;font-size:13px;color:{GRAY};line-height:1.75;">{_inline_html(it.summary)}</div>'
                        )
                    pending.append(
                        f'<div style="margin:0 0 10px;background:#ffffff;border:1px solid {CARD_BORDER};'
                        f'border-radius:10px;padding:13px 15px;">{body}</div>'
                    )
                else:
                    num_html = (
                        f'<span style="color:{ORANGE_DARK};font-weight:700;margin-right:6px;">{int(it.num)}.</span>'
                        if (it.num or "").isdigit() else
                        f'<span style="color:{BLUE};font-weight:700;margin-right:6px;">◆</span>'
                    )
                    pending.append(
                        f'<div style="margin:0 16px 10px;background:#F6FAFD;border-radius:10px;padding:11px 14px;'
                        f'font-size:14px;line-height:1.8;color:#31404f;">{num_html}{_inline_html(it.text)}</div>'
                    )
            else:
                text = str(payload)
                if text in ("（无新动态）", "(无新动态)"):
                    pending.append(
                        f'<div style="margin:0 16px 12px;font-size:13px;color:#b6c0cc;">（无新动态）</div>'
                    )
                else:
                    # 独立加粗行（AI 版的角色小节头）→ 蓝色 ◆ 小标题
                    pending.append(
                        f'<div style="margin:16px 16px 10px;font-size:15px;font-weight:700;color:{BLUE};">'
                        f'<span style="margin-right:6px;">◆</span>{_inline_html(text, link_color=BLUE)}</div>'
                    )
        p.extend(pending)

    p.append(f"""
<div style="margin:32px 16px 22px;padding-top:14px;border-top:1px dashed {CARD_BORDER};text-align:center;font-size:12px;color:#c3cbd4;line-height:1.9;">
  晨析 Morning Insight · 每日自动生成<br>点击右上角「···」可分享给同事
</div>""")

    doc = (
        f'<div style="max-width:677px;margin:0 auto;background:{CARD_BG};'
        f"font-family:-apple-system,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;"
        f'padding-bottom:8px;">' + "".join(p) + "</div>"
    )

    # 超长时从末尾整卡片丢弃，避免截断标签
    if max_bytes and len(doc.encode("utf-8")) > max_bytes:
        while len(doc.encode("utf-8")) > max_bytes and "</div>" in doc:
            cut = doc.rfind('<div style="margin:0 0 10px;background:#ffffff;')
            alt = doc.rfind('<div style="margin:0 16px 10px;')
            cut = max(cut, alt)
            if cut < len(doc) // 2:
                break
            doc = doc[:cut] + "</div>"
        doc = doc.replace(
            "点击右上角「···」可分享给同事",
            "篇幅所限，部分内容已省略 · 完整晨报请查看系统",
        )
    return doc


__all__ = ["format_wecom", "render_wechat_card_html", "parse_report_md"]
