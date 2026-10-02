"""LLM 客户端：任意 OpenAI 兼容接口（/chat/completions、/embeddings）。

能力：
- `chat()` / `chat_messages()`   文本生成（含重试、JSON 模式、进程内缓存）
- `complete_fn()`                生成可直接注入其它模块的补全函数
- `embed_texts()`                向量化（API 优先，无 Key 时降级为内置离线算法）
- `cosine()`                     余弦相似度（纯 Python，可选 numpy 加速）
- 用量写入 `llm_usage` 表（成本控制）
"""
import hashlib
import json
import logging
import math
import re
from collections import OrderedDict

import httpx

logger = logging.getLogger("morning_insight.ai")

DEFAULT_TIMEOUT = 180.0
CACHE_SIZE = 128
JSON_MODE_HINT = "\n\n只输出合法 JSON，不要输出任何解释文字、不要使用 Markdown 代码块。"

# 参考单价（元 / 千 token），仅用于粗略成本统计；未知模型记 0
PRICE_PER_1K = {
    "gpt-4o-mini": (0.0011, 0.0043),
    "gpt-4o": (0.018, 0.072),
    "deepseek-chat": (0.001, 0.002),
    "deepseek-reasoner": (0.004, 0.016),
    "glm-4-flash": (0.0001, 0.0001),
    "qwen-turbo": (0.0003, 0.0006),
}

_cache: "OrderedDict[str, str]" = OrderedDict()


class LLMError(RuntimeError):
    pass


def _cache_key(payload: dict) -> str:
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    return None


def _cache_put(key: str, value: str) -> None:
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)


def _normalize_cfg(cfg: dict | None) -> dict:
    cfg = cfg or {}
    base_url = (cfg.get("base_url") or "").strip().rstrip("/")
    api_key = (cfg.get("api_key") or "").strip()
    model = (cfg.get("model") or "").strip() or "gpt-4o-mini"
    if not base_url:
        raise LLMError("AI 配置不完整：请先在「设置 → AI 模型」填写 API 地址（base_url）")
    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url and "11434" not in base_url:
        raise LLMError("AI 配置不完整：请先在「设置 → AI 模型」填写 API Key")
    return {"base_url": base_url, "api_key": api_key or "not-needed", "model": model, "raw": cfg}


def _record_usage(db, user_id, scene, model, base_url, usage: dict, cached: bool) -> None:
    if db is None or user_id is None:
        return
    try:
        from ..models import LLMUsage

        prompt_tokens = int((usage or {}).get("prompt_tokens") or 0)
        completion_tokens = int((usage or {}).get("completion_tokens") or 0)
        total = int((usage or {}).get("total_tokens") or (prompt_tokens + completion_tokens))
        price_in, price_out = PRICE_PER_1K.get(model, (0.0, 0.0))
        cost = prompt_tokens / 1000 * price_in + completion_tokens / 1000 * price_out
        db.add(LLMUsage(
            user_id=user_id, scene=scene, provider=base_url, model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=total, cached=cached, cost=round(cost, 6),
        ))
        db.commit()
    except Exception as exc:  # 统计失败不应影响主流程
        logger.debug("记录 LLM 用量失败：%s", exc)


def chat_messages(
    messages: list[dict],
    cfg: dict | None,
    *,
    scene: str = "report",
    db=None,
    user_id=None,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    json_mode: bool = False,
    use_cache: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    conf = _normalize_cfg(cfg)
    payload = {
        "model": conf["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    key = _cache_key(payload)
    if use_cache:
        hit = _cache_get(key)
        if hit is not None:
            _record_usage(db, user_id, scene, conf["model"], conf["base_url"], {}, cached=True)
            return hit

    headers = {"Authorization": f"Bearer {conf['api_key']}", "Content-Type": "application/json"}
    headers.update({k: v for k, v in (conf["raw"].get("extra_headers") or {}).items() if v})

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = httpx.post(
                f"{conf['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code >= 400:
                # 兼容部分服务不支持 response_format
                if payload.pop("response_format", None) is not None and resp.status_code in (400, 422):
                    continue
                raise LLMError(f"模型接口返回 {resp.status_code}：{resp.text[:300]}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            _record_usage(db, user_id, scene, conf["model"], conf["base_url"], data.get("usage") or {}, cached=False)
            if use_cache:
                _cache_put(key, content)
            return content
        except LLMError:
            raise
        except Exception as exc:  # 网络抖动重试
            last_error = exc
            logger.warning("LLM 调用失败（第 %d 次）：%s", attempt + 1, exc)
    raise LLMError(f"模型调用失败：{last_error}")


def chat(
    system: str,
    user: str,
    cfg: dict | None,
    *,
    scene: str = "report",
    db=None,
    user_id=None,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    json_mode: bool = False,
    use_cache: bool = False,
) -> str:
    if json_mode:
        system = system + JSON_MODE_HINT
    return chat_messages(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        cfg, scene=scene, db=db, user_id=user_id, temperature=temperature,
        max_tokens=max_tokens, json_mode=json_mode, use_cache=use_cache,
    )


def complete_fn(cfg: dict | None, *, scene: str = "misc", db=None, user_id=None):
    """返回 (system, user) -> str 的补全函数，便于注入抓取层等模块。"""

    def _fn(system: str, user: str) -> str:
        return chat(system, user, cfg, scene=scene, db=db, user_id=user_id, temperature=0.1)

    return _fn


def parse_json(text: str, default=None):
    """从模型输出中稳健地提取 JSON。"""
    if text is None:
        return default
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
    return default


# --------------------------------------------------------------------------- #
# 向量化
# --------------------------------------------------------------------------- #
LOCAL_DIM = 512


def local_embed(text: str, dim: int = LOCAL_DIM) -> list[float]:
    """内置离线嵌入：字符 n-gram 哈希到固定维度，L2 归一化。

    零依赖、确定性、无需 API Key，足够支撑中小规模知识库的语义近似检索。
    生产环境建议在设置里选用真实 Embedding 模型。
    """
    from ..utils.text import normalize

    vec = [0.0] * dim
    norm = normalize(text or "")
    if not norm:
        return vec
    for n in (1, 2, 3):
        for i in range(max(len(norm) - n + 1, 1)):
            gram = norm[i : i + n]
            h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16)
            vec[h % dim] += 1.0 / n
    norm_l2 = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm_l2, 6) for v in vec]


def embed_texts(texts: list[str], cfg: dict | None, *, db=None, user_id=None) -> tuple[list[list[float]], str]:
    """向量化文本，返回 (向量列表, 实际使用的提供方标识)。

    优先使用配置的 Embedding API；未配置或调用失败时降级为内置离线算法。
    """
    cfg = cfg or {}
    model = (cfg.get("embedding_model") or "").strip()
    provider = (cfg.get("embedding_provider") or "auto").strip() or "auto"
    base_url = (cfg.get("base_url") or "").strip().rstrip("/")
    api_key = (cfg.get("api_key") or "").strip()

    if model and base_url and provider not in ("local", "builtin") and provider != "auto_disabled":
        try:
            headers = {"Authorization": f"Bearer {api_key or 'not-needed'}", "Content-Type": "application/json"}
            resp = httpx.post(
                f"{base_url}/embeddings",
                headers=headers,
                json={"model": model, "input": texts},
                timeout=90.0,
            )
            resp.raise_for_status()
            data = resp.json()
            vectors = [row["embedding"] for row in data["data"]]
            return vectors, f"api:{model}"
        except Exception as exc:
            logger.warning("Embedding 接口调用失败，降级为内置离线算法：%s", exc)

    return [local_embed(t) for t in texts], "local"


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):  # 维度不一致（换过模型）时按最小长度比较
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
