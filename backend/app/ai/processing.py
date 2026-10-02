"""AI 处理能力：摘要 / 分类 / 晨报 / 周月报 / 趋势 / 追踪识别 / 预警判定 / 问答 / 语音文稿。"""
import logging

from . import llm as llm_mod
from . import prompts
from .catalog import BUILTIN_FOCUS_POINTS, template_by_id

logger = logging.getLogger("morning_insight.ai.processing")

CLASSIFY_BATCH = 12


def _ai_cfg(cfg: dict) -> dict:
    """兼容两种入参：完整配置载荷（含 ai_config 子键）或直接的 ai_config 字典。

    流水线传下来的是 config_payload() 的结果（base_url / api_key 在 ai_config 子键里），
    而单条摘要等函数收到的是裸的 ai_config。这里统一取到真正的模型配置，
    否则会出现「已配置模型却仍退回素材版」的问题。
    """
    if not isinstance(cfg, dict):
        return {}
    inner = cfg.get("ai_config")
    return inner if isinstance(inner, dict) else cfg


# --------------------------------------------------------------------------- #
# 晨报
# --------------------------------------------------------------------------- #
def generate_report(cfg: dict, articles: list[dict], *, db=None, user_id=None, extra_instruction: str = "") -> str:
    """生成晨报 Markdown。"""
    system, user = prompts.report_prompt(cfg, articles, extra_instruction=extra_instruction)
    return llm_mod.chat(
        system, user, _ai_cfg(cfg), scene="report", db=db, user_id=user_id, temperature=0.45
    )


def generate_periodical(
    cfg: dict, period_type: str, period_label: str,
    reports: list[dict], articles: list[dict], *, db=None, user_id=None,
) -> str:
    reports_text = "\n\n".join(
        f"## {r.get('report_date', '')} {r.get('title', '')}\n{r.get('content_md', '')[:3000]}"
        for r in reports[:30]
    ) or "（本周期没有晨报存档）"
    articles_text = prompts.build_material(articles, limit=60)
    system, user = prompts.periodical_prompt(cfg, period_type, period_label, reports_text, articles_text)
    return llm_mod.chat(
        system, user, _ai_cfg(cfg), scene="periodical", db=db, user_id=user_id, temperature=0.4
    )


# --------------------------------------------------------------------------- #
# 单条摘要
# --------------------------------------------------------------------------- #
def summarize_article(title: str, body: str, cfg: dict, *, db=None, user_id=None) -> str:
    return llm_mod.chat(
        prompts.SUMMARY_SYSTEM, prompts.summary_user(title, body), _ai_cfg(cfg),
        scene="summary", db=db, user_id=user_id, temperature=0.2, use_cache=True,
    ).strip()


def summarize_articles(articles: list[dict], cfg: dict, *, db=None, user_id=None, limit: int = 20) -> list[dict]:
    """批量为素材补充 AI 摘要（写入 item["ai_summary"]）。"""
    out: list[dict] = []
    for item in articles[:limit]:
        enriched = dict(item)
        try:
            enriched["ai_summary"] = summarize_article(
                item.get("title", ""), item.get("raw_content") or item.get("summary") or "", cfg,
                db=db, user_id=user_id,
            )
        except Exception as exc:
            logger.warning("单条摘要失败：%s", exc)
            enriched["ai_summary"] = ""
        out.append(enriched)
    return out


# --------------------------------------------------------------------------- #
# 自动分类
# --------------------------------------------------------------------------- #
def classify_articles(articles: list[dict], cfg: dict, *, db=None, user_id=None) -> list[dict]:
    """把素材归入关注点，返回 [{index, focus_point, category, importance, reason}]。"""
    focus_names = [f.get("name") for f in (cfg.get("focus_points") or BUILTIN_FOCUS_POINTS)]
    results: list[dict] = []
    for start in range(0, len(articles), CLASSIFY_BATCH):
        batch = articles[start : start + CLASSIFY_BATCH]
        lines = "\n".join(
            f"{i}. {a.get('title', '')}｜{(a.get('summary') or a.get('ai_summary') or '')[:160]}"
            for i, a in enumerate(batch)
        )
        user = (
            f"可选关注点：{'、'.join(str(n) for n in focus_names if n)}（都不合适用「其他动态」）\n\n"
            f"请为下面每条素材分类，输出 JSON 数组，每个元素："
            '{"index": 序号, "focus_point": "关注点名称", "category": "更细的主题词", '
            '"importance": 1到5的整数, "reason": "不超过20字"}\n\n'
            f"素材：\n{lines}"
        )
        try:
            raw = llm_mod.chat(
                prompts.CLASSIFY_SYSTEM, user, _ai_cfg(cfg),
                scene="classify", db=db, user_id=user_id, temperature=0.1, json_mode=True, use_cache=True,
            )
            data = llm_mod.parse_json(raw, default=[])
            if isinstance(data, dict):
                data = [data]
            for row in data or []:
                if not isinstance(row, dict):
                    continue
                idx = row.get("index")
                if isinstance(idx, str) and idx.isdigit():
                    idx = int(idx)
                if not isinstance(idx, int) or not (0 <= idx < len(batch)):
                    continue
                results.append({
                    "index": start + idx,
                    "focus_point": str(row.get("focus_point") or "其他动态"),
                    "category": str(row.get("category") or "")[:100],
                    "importance": int(row.get("importance") or 3) if str(row.get("importance", 3)).isdigit() else 3,
                    "reason": str(row.get("reason") or "")[:100],
                })
        except Exception as exc:
            logger.warning("自动分类失败（第 %d 批）：%s", start // CLASSIFY_BATCH + 1, exc)
    return results


# --------------------------------------------------------------------------- #
# 趋势判断
# --------------------------------------------------------------------------- #
def judge_trends(articles: list[dict], cfg: dict, *, db=None, user_id=None) -> list[dict]:
    try:
        raw = llm_mod.chat(
            prompts.TREND_SYSTEM, prompts.trend_user(articles), _ai_cfg(cfg),
            scene="trend", db=db, user_id=user_id, temperature=0.3, json_mode=True,
        )
        data = llm_mod.parse_json(raw, default=[])
        return [d for d in (data or []) if isinstance(d, dict)]
    except Exception as exc:
        logger.warning("趋势判断失败：%s", exc)
        return []


# --------------------------------------------------------------------------- #
# 动态追踪识别
# --------------------------------------------------------------------------- #
def recognize_tracking(articles: list[dict], objects: list[dict], cfg: dict, *, db=None, user_id=None) -> list[dict]:
    if not objects or not articles:
        return []
    try:
        raw = llm_mod.chat(
            prompts.TRACKING_SYSTEM, prompts.tracking_user(articles, objects), _ai_cfg(cfg),
            scene="tracking", db=db, user_id=user_id, temperature=0.2, json_mode=True,
        )
        data = llm_mod.parse_json(raw, default=[])
        out = []
        for row in data or []:
            if not isinstance(row, dict):
                continue
            try:
                idx = int(row.get("index"))
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(articles):
                row["index"] = idx
                out.append(row)
        return out
    except Exception as exc:
        logger.warning("动态追踪识别失败：%s", exc)
        return []


def keyword_tracking_fallback(articles: list[dict], objects: list[dict]) -> list[dict]:
    """无 AI 时的兜底：按名称/关键词做文本匹配。"""
    out: list[dict] = []
    for idx, a in enumerate(articles):
        haystack = f"{a.get('title', '')} {a.get('summary', '')}".lower()
        for obj in objects:
            names = [obj.get("name") or ""] + list(obj.get("keywords") or [])
            for n in names:
                if n and n.lower() in haystack:
                    out.append({
                        "index": idx, "object": obj.get("name"),
                        "event_type": "新闻", "is_highlight": obj.get("level") == "high",
                        "one_line": (a.get("title") or "")[:40],
                    })
                    break
    return out


# --------------------------------------------------------------------------- #
# 关键词预警判定
# --------------------------------------------------------------------------- #
def judge_alerts(keyword: str, match_type: str, articles: list[dict], cfg: dict, *, db=None, user_id=None) -> list[dict]:
    """AI 判定；失败时上层会退化为纯文本匹配。"""
    if not articles:
        return []
    try:
        raw = llm_mod.chat(
            prompts.ALERT_SYSTEM, prompts.alert_user(keyword, match_type, articles), _ai_cfg(cfg),
            scene="alert", db=db, user_id=user_id, temperature=0.1, json_mode=True,
        )
        data = llm_mod.parse_json(raw, default=[])
        out = []
        for row in data or []:
            if not isinstance(row, dict):
                continue
            try:
                idx = int(row.get("index"))
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(articles):
                row["index"] = idx
                out.append(row)
        return out
    except Exception as exc:
        logger.warning("预警判定失败：%s", exc)
        return []


# --------------------------------------------------------------------------- #
# 知识库问答
# --------------------------------------------------------------------------- #
def answer_question(question: str, chunks: list[dict], cfg: dict, *, history=None, db=None, user_id=None) -> str:
    return llm_mod.chat(
        prompts.KNOWLEDGE_SYSTEM, prompts.knowledge_user(question, chunks, history), _ai_cfg(cfg),
        scene="knowledge", db=db, user_id=user_id, temperature=0.3,
    )


# --------------------------------------------------------------------------- #
# 语音文稿
# --------------------------------------------------------------------------- #
def build_tts_script(content_md: str, cfg: dict, *, length: str = "brief", db=None, user_id=None) -> str:
    hint = "3-5 分钟" if length == "brief" else "10-15 分钟"
    try:
        return llm_mod.chat(
            prompts.TTS_SYSTEM, prompts.tts_user(content_md, hint), _ai_cfg(cfg),
            scene="tts", db=db, user_id=user_id, temperature=0.4,
        )
    except Exception as exc:
        # 无 AI 时退化为去 Markdown 的纯文本
        logger.warning("语音文稿生成失败，退回纯文本：%s", exc)
        from ..utils.text import md_to_plain

        return md_to_plain(content_md)


def template_meta(template_id: str) -> dict:
    return template_by_id(template_id)
