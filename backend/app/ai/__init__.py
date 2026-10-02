"""AI 层：模型客户端、内置目录（关注点/角色/模板/音色）、Prompt 工厂、处理能力。"""
from .catalog import (
    AI_PROVIDERS,
    BUILTIN_FOCUS_POINTS,
    EMBEDDING_PROVIDERS,
    INDUSTRY_PRESETS,
    REPORT_LANGUAGES,
    REPORT_LENGTHS,
    REPORT_TEMPLATES,
    ROLE_TEMPLATES,
    TTS_FORMATS,
    TTS_PROVIDERS,
    UI_LANGUAGES,
    VECTOR_STORES,
    default_focus_points,
    default_roles,
    merge_focus_points,
    template_by_id,
)
from .llm import LLMError, chat, chat_messages, complete_fn, cosine, embed_texts, local_embed, parse_json
from .processing import (
    answer_question,
    build_tts_script,
    classify_articles,
    generate_periodical,
    generate_report,
    judge_alerts,
    judge_trends,
    keyword_tracking_fallback,
    recognize_tracking,
    summarize_article,
    summarize_articles,
)
from .prompts import build_user_profile, build_material

__all__ = [
    "AI_PROVIDERS", "BUILTIN_FOCUS_POINTS", "EMBEDDING_PROVIDERS", "INDUSTRY_PRESETS",
    "REPORT_LANGUAGES", "REPORT_LENGTHS", "REPORT_TEMPLATES", "ROLE_TEMPLATES",
    "TTS_FORMATS", "TTS_PROVIDERS", "UI_LANGUAGES", "VECTOR_STORES",
    "default_focus_points", "default_roles", "template_by_id",
    "LLMError", "chat", "chat_messages", "complete_fn", "cosine", "embed_texts",
    "local_embed", "parse_json",
    "answer_question", "build_tts_script", "classify_articles", "generate_periodical",
    "generate_report", "judge_alerts", "judge_trends", "keyword_tracking_fallback",
    "recognize_tracking", "summarize_article", "summarize_articles",
    "build_user_profile", "build_material",
]
