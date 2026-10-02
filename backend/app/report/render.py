"""晨报渲染：把 Markdown 渲染为带品牌主题的 HTML（预览 / 邮件 / 导出 / 打印共用）。

6 套内置模板对应 6 种版式主题；用户也可提供自定义 HTML/CSS 模板
（模板字符串中用 `{{content}}` 占位正文 HTML、`{{title}}` 占位标题）。
"""
import markdown as md_lib

from ..ai.catalog import template_by_id

BASE_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f6f7f9;color:#25313f;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:820px;margin:0 auto;padding:32px 28px 56px;background:#fff;min-height:100vh}
.brand{display:flex;align-items:center;gap:12px;margin-bottom:6px}
.brand-bar{width:5px;height:38px;border-radius:3px;background:var(--accent)}
h1{font-size:26px;line-height:1.35;margin:6px 0 4px;color:#1a2430}
.meta{font-size:12px;color:#8b98a8;margin-bottom:26px}
h2{font-size:19px;margin:34px 0 12px;padding-left:12px;border-left:4px solid var(--accent);color:#1a2430}
h3{font-size:16px;margin:22px 0 8px;color:#2b3a4a}
p{line-height:1.85;margin:10px 0;font-size:15px}
ul,ol{line-height:1.85;padding-left:22px;font-size:15px}
li{margin:6px 0}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(0,0,0,.08)}
a:hover{border-bottom-color:var(--accent)}
code{background:#f1f4f8;padding:2px 6px;border-radius:4px;font-size:13px;
  font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
pre{background:#f7f9fc;border:1px solid #e8ecf1;border-radius:10px;padding:14px 16px;overflow:auto}
pre code{background:none;padding:0}
blockquote{margin:14px 0;padding:10px 16px;background:#fbfcfe;border-left:3px solid #d7dee7;color:#5b6b7c}
hr{border:none;border-top:1px solid #e8ecf1;margin:26px 0}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px}
th,td{border:1px solid #e6ebf1;padding:9px 12px;text-align:left}
th{background:#f7f9fc;font-weight:600}
tbody tr:nth-child(even){background:#fcfdff}
.footer{margin-top:44px;padding-top:16px;border-top:1px solid #e8ecf1;font-size:12px;color:#8b98a8;
  display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.stat{display:inline-block;padding:2px 10px;border-radius:20px;background:#f1f4f8;color:#5b6b7c;
  font-size:12px;margin-right:8px}
"""

THEME_CSS = {
    "compact": """
h2{margin:26px 0 8px;font-size:18px}
p{margin:8px 0}
li{margin:3px 0}
""",
    "magazine": """
.wrap{max-width:760px;padding:44px 46px 64px}
h1{font-size:32px;letter-spacing:-.5px}
h2{font-size:21px;margin:40px 0 14px}
p{font-size:16px;line-height:1.95;color:#31404f}
h1+blockquote,.meta+blockquote{font-size:17px;color:#4a5a6b;background:#fbfaf6}
""",
    "data": """
table{font-size:13.5px}
th{background:#f4faf7}
code{background:#f0f7f3;color:#1f6b4d}
.hl{font-variant-numeric:tabular-nums}
""",
    "card": """
.wrap{max-width:620px;background:#f6f7f9;padding:22px}
h2{background:#fff;border-radius:14px;border-left:none;padding:14px 18px;
  box-shadow:0 1px 2px rgba(20,40,70,.06);margin:22px 0 10px}
h2+ul,h2+p,h2+ol{background:#fff;border-radius:14px;padding:14px 18px 14px 34px;
  margin:0 0 6px;box-shadow:0 1px 2px rgba(20,40,70,.06)}
h1{background:#fff;border-radius:16px;padding:18px 20px;box-shadow:0 1px 2px rgba(20,40,70,.06)}
""",
    "terminal": """
body{background:#0f1419;color:#d6dee7}
.wrap{background:#0f1419}
h1,h2,h3{color:#e9f0f7}
h2{border-left-color:var(--accent);color:#e9f0f7}
a{color:#6cc7ff;border-bottom:none}
code,pre{background:#1a222b;color:#c9e2f5;border-color:#232c36}
blockquote{background:#151c24;border-left-color:#2b3641;color:#9aa8b6}
th{background:#161e26}td,th{border-color:#232c36}
tbody tr:nth-child(even){background:#131a21}
.footer{border-top-color:#232c36;color:#7e8b99}
*{font-family:ui-monospace,SFMono-Regular,Consolas,'Courier New',monospace}
""",
    "print": """
@page{size:A4;margin:18mm 16mm}
body{background:#fff}
.wrap{max-width:none;padding:0;box-shadow:none}
h1{font-size:22pt}h2{font-size:14pt;page-break-after:avoid}
p,li{font-size:11pt;line-height:1.7}
h2{page-break-after:avoid}table{page-break-inside:avoid}
a{color:#25313f;border-bottom:none}
.footer{margin-top:24px}
""",
}


def md_to_html(content_md: str) -> str:
    return md_lib.markdown(
        content_md or "",
        extensions=["extra", "tables", "sane_lists", "toc", "nl2br"],
    )


def render_report_html(
    content_md: str,
    *,
    title: str = "",
    template: str = "brief",
    meta: dict | None = None,
    custom_template: str = "",
    custom_css: str = "",
    standalone: bool = True,
) -> str:
    """渲染晨报 HTML。standalone=True 返回完整文档（可直接打开 / 转 PDF）。"""
    tpl = template_by_id(template)
    accent = (meta or {}).get("accent") or tpl.get("accent") or "#F6A821"
    body = md_to_html(content_md)

    if custom_template:
        return (
            custom_template.replace("{{content}}", body)
            .replace("{{title}}", title or "")
            .replace("{{accent}}", accent)
            .replace("{{css}}", custom_css or "")
        )

    meta = meta or {}
    stats_html = ""
    stat_bits = []
    if meta.get("source_count"):
        stat_bits.append(f'<span class="stat">引用 {meta["source_count"]} 条</span>')
    if meta.get("model"):
        stat_bits.append(f'<span class="stat">{meta["model"]}</span>')
    if meta.get("generated_at"):
        stat_bits.append(f'<span class="stat">生成于 {meta["generated_at"]}</span>')
    if stat_bits:
        stats_html = "<div style='margin-bottom:8px'>" + "".join(stat_bits) + "</div>"

    inner = f"""<div class="wrap">
  <div class="brand"><div class="brand-bar"></div>
    <div><div style="font-size:12px;color:#8b98a8;letter-spacing:1px">晨析 MORNING INSIGHT</div></div>
  </div>
  <div class="meta">{docs_meta(meta)}</div>
  {stats_html}
  {body}
  <div class="footer">
    <span>本报告由开源项目 晨析 Morning Insight 自动生成</span>
    <span>{meta.get('footer_note','') or ''}</span>
  </div>
</div>"""

    if not standalone:
        return inner

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title or '晨析晨报'}</title>
<style>:root{{--accent:{accent};}}{BASE_CSS}{THEME_CSS.get(tpl.get('layout','compact'), '')}</style>
</head><body>{inner}</body></html>"""


def docs_meta(meta: dict) -> str:
    parts = []
    if meta.get("industry"):
        parts.append(str(meta["industry"]))
    if meta.get("report_date"):
        parts.append(str(meta["report_date"]))
    return " · ".join(parts) or "行业分析晨报"
