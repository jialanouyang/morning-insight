"""示例 AI 插件。

接口约定：
    process(prompt: str, text: str, config: dict) -> str

- prompt 为调用方传入的任务说明
- text 为待处理文本
- 配置了 base_url / api_key 时走 OpenAI 兼容接口；否则用内置规则兜底（保证插件总能返回结果）
"""
import re

import httpx

STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is", "are", "was", "were",
             "的", "了", "和", "是", "在", "与", "及", "或", "对", "为", "将", "被", "把", "从", "到"}


def _rule_based(text: str) -> str:
    """无模型时的兜底：给出前两句摘要 + 高频词。"""
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s*", text or "") if s.strip()]
    summary = " ".join(sentences[:2])[:200] or (text or "")[:200]

    tokens = re.findall(r"[A-Za-z][A-Za-z\-]{2,}|[\u4e00-\u9fff]{2,4}", text or "")
    counts: dict[str, int] = {}
    for token in tokens:
        low = token.lower()
        if low in STOPWORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    keywords = [w for w, _ in sorted(counts.items(), key=lambda x: -x[1])[:5]]
    return f"摘要：{summary}\n关键词：{'、'.join(keywords)}"


def process(prompt: str, text: str, config: dict) -> str:
    base_url = (config.get("base_url") or "").rstrip("/")
    api_key = (config.get("api_key") or "").strip()

    if not base_url:
        return _rule_based(text)

    instruction = config.get("instruction") or "用一句话总结这段内容，并列出 3 个关键词。"
    headers = {"Authorization": f"Bearer {api_key or 'not-needed'}", "Content-Type": "application/json"}
    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": config.get("model") or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"{instruction}\n调用方补充说明：{prompt}"},
                    {"role": "user", "content": text[:8000]},
                ],
                "temperature": 0.3,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        # 模型不可用时不让整条链路失败
        return _rule_based(text)
