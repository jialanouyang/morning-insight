"""晨报一键翻译：把整篇晨报（Markdown）翻译为界面语言，保留原文结构与排版。

- 译文按（report_id × target_lang）落库缓存，重复点击不重复调用大模型；
- 使用用户配置的任意 OpenAI 兼容模型（设置 → AI 模型）；
- 语言检测基于标题 + 正文（中文 CJK 占比），与界面语言（zh / en）对齐。
"""
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.llm import LLMError, chat, parse_json
from ..models import Report, ReportTranslation, UserConfig
from ..utils.text import detect_language, truncate

logger = logging.getLogger("morning_insight.translation")

# 翻译支持的目标语言（与界面语言保持一致：中 / 英）
TARGET_LANGS = {"zh": "简体中文", "en": "English"}
# 送入模型的正文上限：超长晨报截断翻译，控制时延与成本
TRANSLATE_CONTENT_LIMIT = 16000

TRANSLATE_SYSTEM_PROMPT = """你是一名专业的科技与财经新闻翻译引擎。用户会给出一段 JSON 格式的晨报内容，\
请把其中的 title / content 全部翻译为{target_name}，并严格满足：
1. 保留原文结构与排版：Markdown 的标题层级、列表、引用、粗体、链接、表格、换行与段落必须与原文一一对应，\
不得合并、拆分或删除任何段落；
2. 忠实翻译，不增译、不漏译、不总结、不解释、不加任何注释；
3. 专有名词首次出现时可保留原文，数字、日期、URL、代码与产品名保持原样；
4. 只返回 JSON：{{"title": "…", "content": "…"}}，两个键与输入一一对应，不要输出其它任何内容。"""


class TranslationError(ValueError):
    """业务校验失败（原文语言一致 / 未配置模型），由路由层映射为 400。"""


def detect_report_lang(report: Report) -> str:
    """识别晨报语言：优先标题 + 正文前段，避免整篇扫描。"""
    return detect_language(f"{report.title}\n{(report.content_md or '')[:2000]}")


def _payload(row: ReportTranslation, cached: bool) -> dict:
    return {
        "ok": True,
        "cached": cached,
        "report_id": row.report_id,
        "source_lang": row.source_lang,
        "target_lang": row.target_lang,
        "title": row.title,
        "content_md": row.content_md,
        "model": row.model,
    }


def get_translation(db: Session, report_id: int, target_lang: str) -> ReportTranslation | None:
    return db.scalar(
        select(ReportTranslation).where(
            ReportTranslation.report_id == report_id,
            ReportTranslation.target_lang == target_lang,
        )
    )


def translate_report(db: Session, cfg: UserConfig, report: Report, target_lang: str) -> dict:
    """把一份晨报翻译为目标语言（界面语言），返回可直接给前端的译文字典。

    抛出 TranslationError 表示前置条件不满足（400）；LLM 调用失败抛 LLMError（502）。
    """
    target = (target_lang or "").strip().lower()
    if target not in TARGET_LANGS:
        raise TranslationError(f"不支持的目标语言：{target or '（空）'}")

    source_lang = detect_report_lang(report)
    if source_lang == target:
        raise TranslationError("该晨报与界面语言一致，无需翻译")

    # 1) 命中缓存直接返回
    cached_row = get_translation(db, report.id, target)
    if cached_row:
        return _payload(cached_row, cached=True)

    # 2) 校验模型配置
    ai = cfg.ai_config or {}
    if not (ai.get("base_url") or "").strip():
        raise TranslationError("翻译需要先在「设置 → AI 模型」配置 API 地址与密钥")

    # 3) 组装请求：正文超长时截断，控制时延与成本
    content = report.content_md or ""
    truncated = len(content) > TRANSLATE_CONTENT_LIMIT
    user_payload = (
        '{"title": ' + _json_str(report.title or "") + ', "content": '
        + _json_str(truncate(content, TRANSLATE_CONTENT_LIMIT, suffix="")) + "}"
    )

    try:
        raw = chat(
            TRANSLATE_SYSTEM_PROMPT.format(target_name=TARGET_LANGS[target]),
            user_payload,
            ai,
            scene="translate",
            db=db,
            user_id=report.user_id,
            temperature=0.2,
            json_mode=True,
        )
    except LLMError:
        raise

    result = parse_json(raw)
    if not isinstance(result, dict) or not (result.get("title") or result.get("content")):
        raise LLMError("模型返回格式异常，请重试")

    row = ReportTranslation(
        report_id=report.id,
        target_lang=target,
        source_lang=source_lang,
        title=truncate(str(result.get("title") or ""), 500, suffix=""),
        content_md=str(result.get("content") or "") + ("…" if truncated else ""),
        model=str(ai.get("model") or ""),
    )
    db.add(row)
    db.commit()
    return _payload(row, cached=False)


def _json_str(value: str) -> str:
    """构造 JSON 字符串字面量（确保中文等非 ASCII 字符原样保留）。"""
    return json.dumps(value, ensure_ascii=False)
