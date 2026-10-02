"""晨报导出：Markdown / HTML / PDF / 图片。

- Markdown：直接返回原文
- HTML：完整独立文档（浏览器打开、打印均可）
- PDF：基于 ReportLab，内置中文 CID 字体 STSong-Light，无需额外字体文件
- 图片：需要 Playwright，未安装时返回明确提示
"""
import html as html_mod
import logging
import os
import re
from pathlib import Path

from ..settings import DATA_DIR

logger = logging.getLogger("morning_insight.report.export")

EXPORT_DIR = Path(DATA_DIR).resolve().parent / "data" / "exports" if not Path(DATA_DIR).is_absolute() else Path(DATA_DIR) / "exports"


def export_dir() -> Path:
    path = Path(EXPORT_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str, ext: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "_", (name or "report").strip())[:80]
    return f"{cleaned or 'report'}.{ext}"


def to_markdown(content_md: str, path: str | None = None) -> str:
    if path:
        Path(path).write_text(content_md or "", encoding="utf-8")
    return content_md or ""


def to_html(content_html: str, path: str | None = None) -> str:
    if path:
        Path(path).write_text(content_html or "", encoding="utf-8")
    return content_html or ""


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
# PDF 内联样式：只做「去标记」，不切换字体。
# 原因：ReportLab 的 CID 中文字体没有注册字族，一旦使用 <b>/<i>/<font face="Courier">
# 包裹中文，字体会回退到 Helvetica，导致中文显示为方块。这里统一保留纯文本最稳妥。
_INLINE_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*", re.S), r"\1"),
    (re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)"), r"\1"),
    (re.compile(r"`([^`]+?)`"), r"\1"),
    (re.compile(r"~~(.+?)~~"), r"\1"),
    (re.compile(r"\[([^\]]+?)\]\((https?://[^)\s]+)\)"), r"\1（\2）"),
    (re.compile(r"!\[[^\]]*?\]\([^)]*?\)"), ""),
]


def _inline(text: str) -> str:
    text = html_mod.escape(text, quote=False)
    for pattern, repl in _INLINE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    for name in ("STSong-Light",):
        try:
            pdfmetrics.getFont(name)
        except KeyError:
            try:
                pdfmetrics.registerFont(UnicodeCIDFont(name))
            except Exception as exc:  # pragma: no cover
                logger.warning("注册中文字体失败 %s: %s", name, exc)
    return "STSong-Light"


def _build_styles(font: str):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm

    accent = colors.HexColor("#C0552F")
    return {
        "body": ParagraphStyle("body", fontName=font, fontSize=10.5, leading=17,
                               spaceBefore=3, spaceAfter=3, textColor=colors.HexColor("#25313f")),
        "h1": ParagraphStyle("h1", fontName=font, fontSize=19, leading=26, spaceAfter=10,
                             textColor=colors.HexColor("#1a2430")),
        "h2": ParagraphStyle("h2", fontName=font, fontSize=13.5, leading=20, spaceBefore=14,
                             spaceAfter=6, textColor=colors.HexColor("#1a2430")),
        "h3": ParagraphStyle("h3", fontName=font, fontSize=11.5, leading=17, spaceBefore=9,
                             spaceAfter=4, textColor=colors.HexColor("#2b3a4a")),
        "bullet": ParagraphStyle("bullet", fontName=font, fontSize=10.5, leading=16.5,
                                 leftIndent=14, bulletIndent=4, spaceAfter=2),
        "quote": ParagraphStyle("quote", fontName=font, fontSize=10, leading=16, leftIndent=14,
                                textColor=colors.HexColor("#5b6b7c"), spaceBefore=6, spaceAfter=6),
        "meta": ParagraphStyle("meta", fontName=font, fontSize=8.5, leading=12,
                               textColor=colors.HexColor("#8b98a8"), spaceAfter=10),
        "cell": ParagraphStyle("cell", fontName=font, fontSize=9, leading=13),
        "cellh": ParagraphStyle("cellh", fontName=font, fontSize=9, leading=13,
                                textColor=colors.HexColor("#31404f")),
        "accent": accent,
    }


def _md_to_flowables(md: str, styles: dict) -> list:
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, Preformatted, Spacer, Table, TableStyle

    flow = []
    lines = (md or "").split("\n")
    i = 0
    bullets: list[str] = []
    ordered: list[str] = []

    def flush_lists():
        nonlocal bullets, ordered
        if bullets:
            flow.append(ListFlowable(
                [ListItem(Paragraph(_inline(b), styles["bullet"]), leftIndent=16) for b in bullets],
                bulletType="bullet", bulletFontName=styles["body"].fontName, start="•",
                bulletColor=styles["accent"], leftIndent=10,
            ))
            bullets = []
        if ordered:
            flow.append(ListFlowable(
                [ListItem(Paragraph(_inline(o), styles["bullet"]), leftIndent=16) for o in ordered],
                bulletType="1", bulletFontName=styles["body"].fontName,
                bulletColor=styles["accent"], leftIndent=10,
            ))
            ordered = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            block, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            flush_lists()
            flow.append(Preformatted("\n".join(block), styles["body"]))
            continue

        if not stripped:
            flush_lists()
            flow.append(Spacer(1, 5))
            i += 1
            continue

        if re.match(r"^#{1,6}\s", stripped):
            flush_lists()
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            flow.append(Paragraph(_inline(text), styles["h1" if level == 1 else ("h2" if level == 2 else "h3")]))
            i += 1
            continue

        if re.match(r"^([-*_]\s*){3,}$", stripped):
            flush_lists()
            flow.append(Spacer(1, 4))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#e0e6ed")))
            flow.append(Spacer(1, 4))
            i += 1
            continue

        if stripped.startswith(">"):
            flush_lists()
            flow.append(Paragraph(_inline(stripped.lstrip("> ")), styles["quote"]))
            i += 1
            continue

        if stripped.startswith(("- ", "* ", "+ ")):
            bullets.append(stripped[2:].strip())
            i += 1
            continue

        if re.match(r"^\d+[.)]\s", stripped):
            ordered.append(re.sub(r"^\d+[.)]\s", "", stripped))
            i += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_lists()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip()
                if re.match(r"^\|[\s:|-]+\|$", raw):  # 分隔行
                    i += 1
                    continue
                rows.append([c.strip() for c in raw.strip("|").split("|")])
                i += 1
            if rows:
                data = [[Paragraph(_inline(c), styles["cellh"]) for c in rows[0]]]
                for row in rows[1:]:
                    row = (row + [""] * len(rows[0]))[: len(rows[0])]
                    data.append([Paragraph(_inline(c), styles["cell"]) for c in row])
                table = Table(data, hAlign="LEFT", repeatRows=1)
                table.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e6ebf1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f9fc")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                flow.append(table)
                flow.append(Spacer(1, 6))
            continue

        # 普通段落：把连续非空行合并
        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|>|\-|\*|\+|\d+[.)]\s|\||```)", lines[i].strip()
        ):
            para.append(lines[i].strip())
            i += 1
        style = styles["meta"] if re.match(r"^生成于|^\d{4}-\d{2}-\d{2}", para[0]) else styles["body"]
        flow.append(Paragraph(_inline(" ".join(para)), style))

    flush_lists()
    return flow


def to_pdf(content_md: str, path: str, *, title: str = "") -> str:
    """生成 PDF。使用 ReportLab 内置中文字体，无需系统字体。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

    font = _register_fonts()
    styles = _build_styles(font)
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=title or "晨析晨报", author="晨析 Morning Insight",
    )

    flow = []
    if title:
        flow.append(_para(title, styles["h1"]))
        flow.append(_para("由 晨析 Morning Insight 自动生成", styles["meta"]))
        flow.append(Spacer(1, 6))
    flow.extend(_md_to_flowables(content_md, styles))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.setFillColorRGB(0.55, 0.6, 0.66)
        canvas.drawString(18 * mm, 10 * mm, "晨析 Morning Insight")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"第 {doc_.page} 页")
        canvas.restoreState()

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return path


def _para(text: str, style):
    from reportlab.platypus import Paragraph

    return Paragraph(_inline(text), style)


# --------------------------------------------------------------------------- #
# 图片
# --------------------------------------------------------------------------- #
def to_image(content_html: str, path: str) -> str:
    """把 HTML 截图成 PNG（需要 Playwright）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("图片导出需要 Playwright：pip install playwright && playwright install chromium") from exc

    tmp_html = Path(path).with_suffix(".html")
    tmp_html.write_text(content_html, encoding="utf-8")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=2)
                page.goto(tmp_html.resolve().as_uri(), wait_until="load")
                page.wait_for_timeout(400)
                page.screenshot(path=path, full_page=True)
            finally:
                browser.close()
    except Exception as exc:
        raise RuntimeError(f"图片导出失败：{exc}") from exc
    finally:
        try:
            tmp_html.unlink()
        except OSError:
            pass
    return path


def export_all_formats(
    content_md: str, content_html: str, base_name: str, fmt: str = "md",
) -> str:
    """按格式导出，**返回生成文件的绝对路径**（供 FileResponse 下载）。fmt: md / html / pdf / image"""
    fmt = (fmt or "md").lower()
    target_dir = export_dir()
    if fmt == "md":
        path = target_dir / safe_filename(base_name, "md")
        to_markdown(content_md, str(path))
        return str(path)
    if fmt in ("html", "htm"):
        path = target_dir / safe_filename(base_name, "html")
        to_html(content_html, str(path))
        return str(path)
    if fmt == "pdf":
        return to_pdf(content_md, str(target_dir / safe_filename(base_name, "pdf")), title=base_name)
    if fmt in ("image", "png", "jpg", "jpeg"):
        return to_image(content_html, str(target_dir / safe_filename(base_name, "png")))
    raise ValueError(f"不支持的导出格式：{fmt}")
