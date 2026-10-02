"""后端多语言（轻量 gettext 替代）。

前端界面多语言由 react-i18next 负责；后端这里覆盖三类场景：
1. API 返回的用户可读消息
2. 晨报提示语（AI Prompt 内的语言名映射）
3. 推送消息里的固定文案

采用字典式词条而非 .po/.mo，避免引入编译步骤，自托管部署更简单；
`t()` 的调用签名与 gettext 的 `_()` 一致，后续若换成 gettext 只需替换实现。
"""
from ._i18n_data import MESSAGES, SUPPORTED_LANGUAGES

DEFAULT_LANG = "zh"


def normalize_lang(lang: str | None) -> str:
    lang = (lang or DEFAULT_LANG).strip().lower()
    for key in SUPPORTED_LANGUAGES:
        if lang == key or lang.startswith(key):
            return key
    return DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """取词条；缺失时回退中文，再回退 key 本身。"""
    lang = normalize_lang(lang)
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def language_name(lang: str) -> str:
    return t(f"lang.{normalize_lang(lang)}", lang)
