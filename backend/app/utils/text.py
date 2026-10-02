"""文本处理工具：归一化、哈希、相似度、Markdown 处理、切片。

去重依赖这里的三个能力：标题归一化哈希、正文归一化哈希、内容相似度。
无需第三方依赖，纯标准库实现，保证在任意自托管环境可用。
"""
import hashlib
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_MD_NOISE_RE = re.compile(r"[#*`>\-\[\]\(\)!_~|]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def strip_html(text: str) -> str:
    """去除 HTML 标签与多余空白。"""
    if not text:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return _WS_RE.sub(" ", text).strip()


def normalize(text: str) -> str:
    """归一化：全角转半角、去标点与空白、统一小写。用于去重比较。"""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _MD_NOISE_RE.sub("", text)
    text = _WS_RE.sub("", text)
    return text


def digest(text: str, length: int = 40) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def title_hash(title: str) -> str:
    return digest(normalize(title))


def content_hash(content: str) -> str:
    return digest(normalize(content)[:2000])


def _shingles(text: str, size: int = 3) -> set[str]:
    tokens = _WORD_RE.findall(text.lower())
    if CJK := _CJK_RE.findall(text):
        # 中文以字为单位滑动窗口；英文以词为单位
        joined = "".join(CJK)
        grams = {joined[i : i + size] for i in range(max(len(joined) - size + 1, 1))}
        grams |= {t for t in tokens if len(t) > 1}
        return grams
    return {" ".join(tokens[i : i + size]) for i in range(max(len(tokens) - size + 1, 1))}


def similarity(a: str, b: str) -> float:
    """内容相似度（Jaccard + 长度惩罚），返回 0~1。"""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    sa, sb = _shingles(na), _shingles(nb)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    jaccard = inter / union if union else 0.0
    # 短文本包含关系加分（标题被截断的常见情况）
    if len(na) >= 6 and (na in nb or nb in na):
        jaccard = max(jaccard, 0.9)
    return round(jaccard, 4)


def is_duplicate(a: str, b: str, threshold: float = 0.82) -> bool:
    return similarity(a, b) >= threshold


def detect_language(text: str) -> str:
    """按 CJK 字符占比判断文本语言：中文占比高返回 "zh"，否则视为 "en"。

    抓取到的文章 language 字段可能为空，翻译入口用它做兜底判断。
    """
    text = text or ""
    if not text.strip():
        return ""
    cjk = len(_CJK_RE.findall(text))
    letters = len(re.findall(r"[a-zA-Z]", text))
    if cjk == 0 and letters == 0:
        return ""
    return "zh" if cjk * 3 >= letters + cjk else "en"


def truncate(text: str, limit: int, suffix: str = "…") -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - len(suffix)] + suffix


def md_to_plain(md: str) -> str:
    """把 Markdown 粗略转成纯文本（用于语音播报、纯文本邮件等场景）。"""
    if not md:
        return ""
    text = re.sub(r"```.*?```", " ", md, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "· ", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = text.replace("**", "").replace("__", "").replace("`", "").replace("> ", "")
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def estimate_duration_sec(text: str) -> float:
    """按中文约 4.5 字/秒估算朗读时长。"""
    plain = md_to_plain(text)
    return round(len(plain) / 4.5, 1)


def split_text(text: str, size: int = 700, overlap: int = 120) -> list[str]:
    """按段落边界切片，尽量不切断句子。"""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(buffer) + len(para) + 2 <= size:
            buffer = f"{buffer}\n\n{para}".strip()
            continue
        if buffer:
            chunks.append(buffer)
        if len(para) <= size:
            buffer = para
        else:  # 超长段落硬切
            start = 0
            while start < len(para):
                chunks.append(para[start : start + size])
                start += size - overlap
            buffer = ""
    if buffer:
        chunks.append(buffer)
    # 相邻块加重叠，保留上下文
    if overlap > 0 and len(chunks) > 1:
        merged = [chunks[0]]
        for prev, cur in zip(chunks, chunks[1:]):
            merged.append((prev[-overlap:] + "\n" + cur).strip())
        chunks = merged
    return chunks


def tokenize_for_search(text: str) -> list[str]:
    """用于关键词匹配的简易分词：英文按词，中文按 2-gram。"""
    text = text or ""
    tokens: list[str] = [t.lower() for t in _WORD_RE.findall(text)]
    cjk = "".join(_CJK_RE.findall(text))
    tokens += [cjk[i : i + 2] for i in range(max(len(cjk) - 1, 0))]
    return tokens
