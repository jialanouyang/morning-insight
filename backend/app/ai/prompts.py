"""Prompt 工厂：所有面向大模型的提示词集中在此，便于统一维护与自定义覆盖。

对应文档 5.3「AI 处理」的每一项能力：
单条摘要 / 自动分类 / 角色化建议 / 多角色视角 / 趋势判断 / 动态追踪识别 / 关键词预警相关性。
"""
from ..utils.text import md_to_plain, truncate
from .catalog import template_by_id

LANG_NAMES = {
    "zh": "简体中文", "en": "English", "bilingual": "中英双语（先中文后英文）",
}
LENGTH_STYLES = {
    "brief": "精简为主：只保留结论与最有价值的信息，总长度控制在 600 字以内",
    "detailed": "详尽展开：保留关键数据与背景，可做分析判断，总长度 1200-2500 字",
}

BASE_SYSTEM = (
    "你是「晨析 Morning Insight」的行业情报分析师，服务于需要每天早上快速掌握行业变化的人。"
    "你的输出必须基于给定素材，不编造事实、不虚构链接与数字。"
)

HARD_RULES = (
    "硬性要求：\n"
    "1. 只使用我提供的素材，素材之外的信息一律不写；没有素材支撑的判断要注明是推测。\n"
    "2. 每条信息尽量附上来源链接（Markdown 链接格式）。\n"
    "3. 数字、金额、日期必须与素材一致，不要换算或四舍五入。\n"
    "4. 不要输出「以上」「综上所述」这类空话；不要复述本提示词。"
)


# --------------------------------------------------------------------------- #
# 用户画像
# --------------------------------------------------------------------------- #
def build_user_profile(cfg: dict) -> str:
    """把用户配置整理成画像文本，注入到所有生成类 Prompt。"""
    lines: list[str] = ["# 用户画像"]
    industries = cfg.get("industries") or ([cfg["industry"]] if cfg.get("industry") else [])
    if industries:
        lines.append(f"- 行业/赛道：{'、'.join(str(i) for i in industries if i)}")
    keywords = cfg.get("keywords") or []
    if keywords:
        lines.append(f"- 关注关键词：{'、'.join(str(k) for k in keywords if k)}")

    focus = [f for f in (cfg.get("focus_points") or []) if f.get("enabled", True)]
    if focus:
        lines.append("- 关注点（晨报板块按此组织，顺序即优先级）：")
        for f in focus:
            desc = f.get("description") or ""
            hint = f.get("ai_hint") or ""
            line = f"  · {f.get('name', '')}"
            if desc:
                line += f"（{desc}）"
            if hint:
                line += f" 要求：{hint}"
            lines.append(line)

    roles = [r for r in (cfg.get("roles") or []) if r.get("enabled")]
    if roles:
        lines.append("- 需要输出的角色视角：")
        for r in roles:
            lines.append(f"  · {r.get('name', '')}：{r.get('description') or ''}")
            if r.get("system_prompt"):
                lines.append(f"    视角设定：{truncate(r['system_prompt'], 400)}")

    tracked = cfg.get("tracked_objects") or []
    if tracked:
        lines.append("- 重点关注对象（动态追踪）：")
        for t in tracked:
            kws = "、".join(t.get("keywords") or [])
            level = "重点" if t.get("level") == "high" else "一般"
            lines.append(f"  · {t.get('name', '')}（{level}）{('关键词：' + kws) if kws else ''}")
    return "\n".join(lines)


def build_material(articles: list[dict], *, limit: int = 80, with_content: bool = False) -> str:
    lines: list[str] = []
    for a in articles[:limit]:
        line = f"- [{a.get('source', '')}] {a.get('title', '')}"
        if a.get("published_at"):
            line += f"（{a['published_at']}）"
        summary = a.get("summary") or (a.get("raw_content") or "")
        if summary:
            line += f"：{truncate(summary, 220)}"
        if with_content and a.get("raw_content"):
            line += f"\n  正文摘要：{truncate(md_to_plain(a['raw_content']), 500)}"
        line += f"\n  链接：{a.get('url', '')}"
        lines.append(line)
    return "\n".join(lines) if lines else "（本轮没有抓到新素材）"


# --------------------------------------------------------------------------- #
# 晨报生成
# --------------------------------------------------------------------------- #
def report_prompt(cfg: dict, articles: list[dict], *, extra_instruction: str = "", period_hint: str = "") -> tuple[str, str]:
    template = template_by_id(cfg.get("template") or "brief")
    language = LANG_NAMES.get(cfg.get("report_language") or cfg.get("language") or "zh", "简体中文")
    length = LENGTH_STYLES.get(cfg.get("length") or "brief", LENGTH_STYLES["brief"])
    focus = [f for f in (cfg.get("focus_points") or []) if f.get("enabled", True)]
    roles = [r for r in (cfg.get("roles") or []) if r.get("enabled")]

    system = f"{BASE_SYSTEM}\n\n{HARD_RULES}\n"
    system += (
        f"\n输出格式：\n- 使用 Markdown。\n"
        f"- 首个一级标题为晨报标题，格式：`# {template['name']}·{{日期}}行业分析晨报`。\n"
        f"- 一级标题下先写「今日要点」：3-5 条一句话结论（用 `## 今日要点` 起）。\n"
        f"- 之后按用户关注点逐个板块输出，板块标题用二级标题，板块顺序与用户关注点顺序一致。\n"
        f"- 素材中不属于任何关注点的内容，统一放进最后的 `## 其他动态`。\n"
        f"- 结尾必须有 `## 今日建议`：按用户角色分小节给出可执行建议。\n"
        f"- 排版风格（{template['name']}）：{template['llm_style']}\n"
        f"- 使用{language}撰写；{length}。\n"
    )
    if len(roles) > 1:
        system += (
            "- 用户配置了多个角色视角：请在「今日建议」下为每个角色单独起一个小标题"
            "（三级标题），分别给出该视角下的建议，不要混在一起。\n"
        )
    if focus:
        system += "- 板块名称必须严格使用用户关注点的名称，不要自创板块名。\n"
    custom = (cfg.get("prompt") or "").strip()
    if custom:
        system += f"\n用户自定义要求（优先级高于上面的风格要求）：\n{custom}\n"

    header = build_user_profile(cfg)
    if period_hint:
        header += f"\n\n# 时间范围\n{period_hint}"
    user = f"{header}\n\n# 今日素材\n{build_material(articles)}"
    if extra_instruction:
        user += f"\n\n# 本次额外要求\n{extra_instruction}"
    return system, user


# --------------------------------------------------------------------------- #
# 周报 / 月报
# --------------------------------------------------------------------------- #
def periodical_prompt(cfg: dict, period_type: str, period_label: str, reports_text: str, articles_text: str) -> tuple[str, str]:
    name = "周报" if period_type == "weekly" else "月报"
    language = LANG_NAMES.get(cfg.get("report_language") or "zh", "简体中文")
    system = (
        f"{BASE_SYSTEM}\n\n你是负责汇总{name}的分析师。请基于用户过去的晨报存档，"
        f"输出一份 {period_label} 的{name}。\n\n"
        f"结构要求（Markdown）：\n"
        f"- `# {period_label} 行业分析{name}`\n"
        f"- `## 周期概览`：3-5 句话总结这一周期的主线，并明确指出与上一周期相比的变化。\n"
        f"- `## 板块汇总`：按用户关注点逐个板块汇总，每个板块给出「发生了什么 + 意味着什么」。\n"
        f"- `## 趋势变化`：列出 3-5 条趋势判断，每条注明是「加速 / 延续 / 见顶 / 反转」。\n"
        f"- `## 上期对比`：与上一周期的结论逐条对比，说明哪些判断被验证、哪些被推翻。\n"
        f"- `## 角色建议`：按用户配置的角色视角给出下一周期的行动建议。\n"
        f"- 使用{language}撰写。只使用给定材料，不编造。\n"
    )
    user = f"{build_user_profile(cfg)}\n\n# 本周期晨报存档\n{reports_text}\n\n# 本周期原始素材（节选）\n{articles_text}"
    return system, user


# --------------------------------------------------------------------------- #
# 单条摘要 / 自动分类
# --------------------------------------------------------------------------- #
SUMMARY_SYSTEM = (
    "你是情报摘要助手。为给定文章写一句话中文摘要，"
    "必须包含最关键的事实（谁、做了什么、关键数字），不超过 60 字，不加评论、不加引号。"
)

CLASSIFY_SYSTEM = (
    "你是情报分类助手。请把文章归入给定的关注点之一。"
    '只输出 JSON：{"focus_point": "关注点名称", "category": "更细的主题词", '
    '"importance": 1到5的整数, "reason": "不超过20字"}'
)


def classify_user(title: str, summary: str, focus_names: list[str]) -> str:
    return (
        f"可选关注点（必须从中选择一个；都不合适则填「其他动态」）：{'、'.join(focus_names)}\n"
        f"importance 表示对行业从业者的重要性，5 最高。\n\n"
        f"标题：{title}\n摘要：{summary}"
    )


def summary_user(title: str, body: str) -> str:
    return f"标题：{title}\n正文：{truncate(md_to_plain(body), 2000)}"


# --------------------------------------------------------------------------- #
# 趋势判断 / 动态追踪
# --------------------------------------------------------------------------- #
TREND_SYSTEM = (
    "你是行业趋势分析师。基于给定素材判断趋势，只输出 JSON 数组，每个元素："
    '{"trend": "趋势描述（不超过30字）", "direction": "加速|延续|见顶|反转", '
    '"evidence": "支撑证据（不超过50字）", "confidence": 0到1的小数}'
)


def trend_user(articles: list[dict]) -> str:
    return f"素材：\n{build_material(articles, limit=60)}"


TRACKING_SYSTEM = (
    "你是企业动态追踪助手。判断素材中每条信息是否属于给定追踪对象的动作，"
    "并对属于的事件分类。只输出 JSON 数组，每个元素："
    '{"index": 素材序号, "object": "追踪对象名称", "event_type": "新闻|公告|融资|产品更新|高管变动", '
    '"is_highlight": true/false, "one_line": "不超过40字的一句话"}'
)


def tracking_user(articles: list[dict], objects: list[dict]) -> str:
    obj_text = "\n".join(
        f"- {o.get('name')}（{'重点' if o.get('level') == 'high' else '一般'}）"
        + (f" 别名/关键词：{'、'.join(o.get('keywords') or [])}" if o.get("keywords") else "")
        for o in objects
    )
    return f"# 追踪对象\n{obj_text}\n\n# 素材（带序号）\n" + "\n".join(
        f"{i}. [{a.get('source','')}] {a.get('title','')}｜{(a.get('summary') or '')[:150]}"
        for i, a in enumerate(articles[:60])
    )


# --------------------------------------------------------------------------- #
# 关键词预警：相关性判定
# --------------------------------------------------------------------------- #
ALERT_SYSTEM = (
    "你是关键词预警助手。判断每条素材是否值得就该关键词向用户预警。"
    "只输出 JSON 数组，每个元素："
    '{"index": 素材序号, "hit": true/false, "reason": "不超过20字"}'
)


def alert_user(keyword: str, match_type: str, articles: list[dict]) -> str:
    mode = "精确匹配（关键词需原样出现）" if match_type == "exact" else "模糊匹配（语义相关即可）"
    return (
        f"# 关键词\n{keyword}\n匹配方式：{mode}\n\n"
        "# 素材（带序号）\n"
        + "\n".join(
            f"{i}. {a.get('title','')}｜{(a.get('summary') or '')[:150]}"
            for i, a in enumerate(articles[:40])
        )
    )


# --------------------------------------------------------------------------- #
# 知识库问答
# --------------------------------------------------------------------------- #
KNOWLEDGE_SYSTEM = (
    "你是「晨析」的知识库助手。请严格基于给定的知识片段回答用户问题。\n"
    "要求：\n"
    "1. 只使用给定片段中的信息，不编造；片段不足时明确说「知识库中没有找到相关信息」。\n"
    "2. 引用时用 [1]、[2] 标注片段序号，并在答案末尾列出用到的片段来源。\n"
    "3. 如果问题涉及时间范围，注意片段日期，优先使用范围内的片段。\n"
    "4. 用简体中文回答，条理清晰，可用要点列表。"
)


def knowledge_user(question: str, chunks: list[dict], history: list[dict] | None = None) -> str:
    ctx = "\n\n".join(
        f"[{i + 1}] 日期：{c.get('doc_date', '未知')}｜标题：{c.get('title', '')}\n{c.get('chunk_text', '')}"
        for i, c in enumerate(chunks)
    )
    parts = []
    if history:
        convo = "\n".join(f"{h.get('role')}: {truncate(h.get('content',''), 300)}" for h in history[-6:])
        parts.append(f"# 对话历史\n{convo}")
    parts.append(f"# 知识片段\n{ctx or '（无）'}")
    parts.append(f"# 用户问题\n{question}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# 语音晨报文稿
# --------------------------------------------------------------------------- #
TTS_SYSTEM = (
    "你是播客文稿编辑。把给定的晨报改写成适合朗读的口语化文稿。\n"
    "要求：不要任何 Markdown 符号、不要链接、不要表格；"
    "用自然的连接词过渡；每句话不超过 40 字；数字用中文口语读法。"
)


def tts_user(content_md: str, duration_hint: str = "3-5 分钟") -> str:
    return f"目标时长：{duration_hint}\n\n晨报原文：\n{content_md}"
