"""内置目录：关注点、角色模板、晨报模板、行业、AI 服务商、嵌入模型、TTS 音色。

对应产品需求文档 5.1「配置」/ 5.4「晨报生成」/ 5.12「语音晨报」：

- 关注点三层设计：内置（勾选即用）→ 改内置定义 → 完全自定义
- 角色：7 个内置模板，Prompt 可见可编辑；高级用户可完全自定义 System Prompt
- 晨报模板：6 套内置 + 自定义 HTML/CSS
"""

# --------------------------------------------------------------------------- #
# 一、关注点（决定晨报的板块结构：勾了什么就出现什么板块）
# --------------------------------------------------------------------------- #
BUILTIN_FOCUS_POINTS: list[dict] = [
    {"id": "funding", "name": "融资事件", "description": "投融资、并购、IPO、退出",
     "ai_hint": "关注金额、轮次、投资方、估值、用途；标注是否首次披露", "builtin": True, "enabled": True},
    {"id": "policy", "name": "政策监管", "description": "政策发布、监管处罚、合规要求",
     "ai_hint": "区分中央/地方、部门、生效时间与影响范围；标注对行业是利好还是利空", "builtin": True, "enabled": True},
    {"id": "tech", "name": "技术突破", "description": "技术进展、论文、专利、开源",
     "ai_hint": "说明突破了什么指标、与现有方案对比、距离落地还有多远", "builtin": True, "enabled": True},
    {"id": "tracking", "name": "动态追踪", "description": "关注的公司/产品最新动作",
     "ai_hint": "只输出用户关注列表中对象的动作；有重大变化时标注「重点」", "builtin": True, "enabled": True},
    {"id": "talent", "name": "人才流动", "description": "高管变动、团队组建、招聘动向",
     "ai_hint": "注明原任职与去向，评估对相关公司的影响", "builtin": True, "enabled": False},
    {"id": "market", "name": "市场数据", "description": "市场规模、价格、份额、财务数据",
     "ai_hint": "保留具体数字与同比/环比，注明数据来源与统计口径", "builtin": True, "enabled": False},
    {"id": "competition", "name": "竞争格局", "description": "竞争对手动作、份额变化、战略调整",
     "ai_hint": "指出谁在进攻谁在防守，以及对用户的影响", "builtin": True, "enabled": False},
    {"id": "supply", "name": "供应链", "description": "上下游、原材料、产能、物流",
     "ai_hint": "关注涨价/缺货/扩产/替代，标注传导链条", "builtin": True, "enabled": False},
]

FOCUS_POINT_IDS = {f["id"] for f in BUILTIN_FOCUS_POINTS}


# --------------------------------------------------------------------------- #
# 二、角色模板（决定建议的视角；Prompt 可见可编辑）
# --------------------------------------------------------------------------- #
ROLE_TEMPLATES: list[dict] = [
    {
        "id": "fa", "name": "融资顾问", "description": "服务于企业侧，关注融资机会与估值逻辑",
        "system_prompt": (
            "你是一位资深融资顾问（FA）。从企业融资视角解读情报：判断融资窗口是否打开、"
            "当前估值水平的锚点在哪、哪些机构正在积极出手、给出可执行的对接建议（如准备什么材料、"
            "锁定哪类投资人）。避免空泛判断，每条建议都要能落地。"
        ),
        "builtin": True, "enabled": False,
    },
    {
        "id": "investor", "name": "投资人", "description": "关注赛道机会、标的筛选与风险",
        "system_prompt": (
            "你是一位一级市场投资人。从投资视角解读情报：识别赛道拐点与主题轮动、"
            "评估标的的差异化与壁垒、指出风险与反共识观点、给出尽调清单要点。"
            "对每个机会给出「值得进一步接触 / 观察 / 放弃」的倾向性判断并说明理由。"
        ),
        "builtin": True, "enabled": True,
    },
    {
        "id": "pm", "name": "产品经理", "description": "关注用户需求、竞品功能与落地路径",
        "system_prompt": (
            "你是一位资深产品经理。从产品视角解读情报：拆解竞品功能与背后的用户需求、"
            "判断哪些变化会形成新的产品机会、给出可落地的功能优先级建议（P0/P1/P2）。"
            "关注实现成本与收益的对比，避免只看技术炫技。"
        ),
        "builtin": True, "enabled": False,
    },
    {
        "id": "founder", "name": "创业者", "description": "关注战略选择、资源与生存空间",
        "system_prompt": (
            "你是一位连续创业者。从创业者视角解读情报：判断大厂动作是威胁还是机会、"
            "指出可切入的差异化缝隙、提醒现金流与节奏风险、给出资源聚焦建议。"
            "语气直接务实，不回避坏消息。"
        ),
        "builtin": True, "enabled": False,
    },
    {
        "id": "analyst", "name": "研究员", "description": "关注逻辑链、数据与不确定性",
        "system_prompt": (
            "你是一位行业研究员。从研究视角解读情报：梳理因果逻辑链、标注数据来源与口径、"
            "区分事实与推测、指出当前认知中的盲区与待验证假设、给出后续跟踪指标。"
            "对不确定的地方明确说明不确定性来源。"
        ),
        "builtin": True, "enabled": False,
    },
    {
        "id": "sales", "name": "销售", "description": "关注客户信号与商机线索",
        "system_prompt": (
            "你是一位 B2B 销售负责人。从销售视角解读情报：识别客户预算与采购信号、"
            "判断哪些信息可以直接用于开场话题、提示竞品在客户侧的动向、"
            "给出具体的目标客户触达建议与话术要点。"
        ),
        "builtin": True, "enabled": False,
    },
    {
        "id": "marketing", "name": "市场", "description": "关注传播机会、品牌与增长",
        "system_prompt": (
            "你是一位市场负责人。从市场视角解读情报：识别可借势的传播节点与话题窗口、"
            "判断目标受众在关心什么、给出内容与投放方向建议、提示舆情风险。"
            "给出可直接执行的动作，而不只是方向。"
        ),
        "builtin": True, "enabled": False,
    },
]

ROLE_IDS = {r["id"] for r in ROLE_TEMPLATES}


# --------------------------------------------------------------------------- #
# 三、晨报模板（6 套内置 + 自定义）
# --------------------------------------------------------------------------- #
REPORT_TEMPLATES: list[dict] = [
    {
        "id": "brief", "name": "简报版", "description": "条目式速读，适合每天早上 3 分钟扫完",
        "layout": "compact",
        "llm_style": "以「板块 → 条目」的两级结构输出，每条 1-2 行，直接给结论与来源链接；"
                     "不写过渡段，不写抒情句。",
        "accent": "#F6A821", "builtin": True,
    },
    {
        "id": "magazine", "name": "杂志版", "description": "有导语与深度点评，适合慢慢读",
        "layout": "magazine",
        "llm_style": "开头写一段 80 字以内的「今日导语」概括主线；每个板块先给一段 2-3 句的整体判断，"
                     "再列具体条目；重点条目展开 3-5 句点评。",
        "accent": "#2B9CD8", "builtin": True,
    },
    {
        "id": "data", "name": "数据版", "description": "突出数字、表格与变化",
        "layout": "data",
        "llm_style": "尽量保留原文中的具体数字（金额、百分比、数量、时间）。"
                     "能用 Markdown 表格表达的一律用表格，例如「公司 | 事件 | 金额 | 时间」。"
                     "每个板块末尾用一句话给出数据层面的结论。",
        "accent": "#3BA776", "builtin": True,
    },
    {
        "id": "card", "name": "卡片版", "description": "每条一张小卡，适合手机阅读与转发",
        "layout": "card",
        "llm_style": "每个板块用三级标题作为卡片标题，卡片内用短句 + 要点符号，"
                     "每条控制在 40 字以内，避免长段落。",
        "accent": "#8B6CF0", "builtin": True,
    },
    {
        "id": "terminal", "name": "终端版", "description": "纯文本、无装饰，适合脚本与终端查看",
        "layout": "terminal",
        "llm_style": "只使用纯文本与简单符号（如 -、=、[ ]），不要使用 Markdown 加粗/斜体/表格，"
                     "不要使用 emoji，保持等宽可读。",
        "accent": "#5B6B7C", "builtin": True,
    },
    {
        "id": "print", "name": "打印版", "description": "A4 排版，适合打印或转 PDF 传阅",
        "layout": "print",
        "llm_style": "结构规整、层级清晰，避免大段密集文字；每个板块条目控制在 5 条以内，"
                     "重要信息前置，便于打印后标注。",
        "accent": "#C0552F", "builtin": True,
    },
]

TEMPLATE_IDS = {t["id"] for t in REPORT_TEMPLATES}


# --------------------------------------------------------------------------- #
# 四、行业 / 赛道
# --------------------------------------------------------------------------- #
INDUSTRY_PRESETS: list[str] = [
    "人工智能", "大模型与AIGC", "半导体与集成电路", "新能源", "智能汽车与出行",
    "生物医药", "企业服务与SaaS", "金融科技", "消费与零售", "智能制造与机器人",
    "游戏与文娱", "跨境电商", "低空经济", "航天与卫星", "新材料", "能源与电力",
    "通信与网络", "网络安全", "教育与培训", "医疗健康服务", "农业科技", "物流与供应链",
]


# --------------------------------------------------------------------------- #
# 五、AI 服务商预设（任意 OpenAI 兼容接口均可）
# --------------------------------------------------------------------------- #
AI_PROVIDERS: list[dict] = [
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1",
     "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "o4-mini"],
     "embedding_models": ["text-embedding-3-small", "text-embedding-3-large"],
     "doc": "在 platform.openai.com 创建 API Key"},
    {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1",
     "models": ["deepseek-chat", "deepseek-reasoner"], "embedding_models": [],
     "doc": "在 platform.deepseek.com 创建 API Key，价格低、中文好"},
    {"id": "moonshot", "name": "月之暗面 Kimi", "base_url": "https://api.moonshot.cn/v1",
     "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k", "kimi-k2-0711-preview"],
     "embedding_models": [], "doc": "在 platform.moonshot.cn 创建 API Key，长文本友好"},
    {"id": "zhipu", "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
     "models": ["glm-4-plus", "glm-4-air", "glm-4-flash"],
     "embedding_models": ["embedding-3"], "doc": "在 open.bigmodel.cn 创建 API Key"},
    {"id": "dashscope", "name": "阿里通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-long"],
     "embedding_models": ["text-embedding-v3"], "doc": "在阿里云百炼控制台创建 API Key"},
    {"id": "siliconflow", "name": "硅基流动", "base_url": "https://api.siliconflow.cn/v1",
     "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"],
     "embedding_models": ["BAAI/bge-m3", "BAAI/bge-large-zh-v1.5"],
     "doc": "在 siliconflow.cn 创建 API Key，聚合多模型"},
    {"id": "ollama", "name": "本地 Ollama", "base_url": "http://host.docker.internal:11434/v1",
     "models": ["qwen2.5:7b", "llama3.1:8b", "gemma2:9b"],
     "embedding_models": ["bge-m3", "nomic-embed-text"],
     "doc": "本地部署零成本；Docker 内用 host.docker.internal 访问宿主机"},
    {"id": "custom", "name": "自定义（任意 OpenAI 兼容接口）", "base_url": "",
     "models": [], "embedding_models": [], "doc": "填写形如 https://your-host/v1 的地址"},
]


# --------------------------------------------------------------------------- #
# 六、嵌入模型（知识库 RAG）
# --------------------------------------------------------------------------- #
EMBEDDING_PROVIDERS: list[dict] = [
    {"id": "auto", "name": "自动（优先用 API，无 Key 时用内置离线算法）", "dim": 0},
    {"id": "openai", "name": "OpenAI text-embedding-3-small", "dim": 1536},
    {"id": "zhipu", "name": "智谱 embedding-3", "dim": 2048},
    {"id": "bge", "name": "BGE（本地 / 硅基流动 bge-m3）", "dim": 1024},
    {"id": "local", "name": "内置离线算法（零依赖，无需 Key）", "dim": 512},
]

VECTOR_STORES: list[dict] = [
    {"id": "builtin", "name": "内置（SQLite 存向量 + 余弦检索，零额外依赖）"},
    {"id": "chroma", "name": "Chroma（需 pip install chromadb）"},
    {"id": "qdrant", "name": "Qdrant（需提供地址与 Key）"},
    {"id": "pgvector", "name": "pgvector（需 PostgreSQL）"},
]


# --------------------------------------------------------------------------- #
# 七、TTS 音色
# --------------------------------------------------------------------------- #
TTS_PROVIDERS: list[dict] = [
    {"id": "edge", "name": "Edge TTS（免费，无需 Key）",
     "voices": [
         {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓（女声·通用）", "lang": "zh"},
         {"id": "zh-CN-XiaoyiNeural", "name": "晓伊（女声·活泼）", "lang": "zh"},
         {"id": "zh-CN-YunxiNeural", "name": "云希（男声·年轻）", "lang": "zh"},
         {"id": "zh-CN-YunyangNeural", "name": "云扬（男声·新闻）", "lang": "zh"},
         {"id": "zh-CN-YunjianNeural", "name": "云健（男声·沉稳）", "lang": "zh"},
         {"id": "en-US-AriaNeural", "name": "Aria（女声·美音）", "lang": "en"},
         {"id": "en-US-GuyNeural", "name": "Guy（男声·美音）", "lang": "en"},
     ]},
    {"id": "openai", "name": "OpenAI TTS（需 API Key）",
     "voices": [
         {"id": "alloy", "name": "Alloy", "lang": "en"},
         {"id": "echo", "name": "Echo", "lang": "en"},
         {"id": "fable", "name": "Fable", "lang": "en"},
         {"id": "onyx", "name": "Onyx", "lang": "en"},
         {"id": "nova", "name": "Nova", "lang": "en"},
         {"id": "shimmer", "name": "Shimmer", "lang": "en"},
     ]},
]

TTS_FORMATS = [{"id": "mp3", "name": "MP3（通用）"}, {"id": "ogg", "name": "OGG（Telegram 语音条）"}]


# --------------------------------------------------------------------------- #
# 八、语言
# --------------------------------------------------------------------------- #
UI_LANGUAGES = [
    {"id": "zh", "name": "简体中文"}, {"id": "en", "name": "English"},
]

REPORT_LANGUAGES = [
    {"id": "zh", "name": "中文"}, {"id": "en", "name": "英文"}, {"id": "bilingual", "name": "中英双语"},
]

REPORT_LENGTHS = [
    {"id": "brief", "name": "简报（3-5 分钟读完）"},
    {"id": "detailed", "name": "详细（10-15 分钟读完）"},
]


def default_focus_points() -> list[dict]:
    return [dict(f) for f in BUILTIN_FOCUS_POINTS]


def merge_focus_points(stored: list | None) -> list[dict]:
    """把缺失的内置关注点补回用户配置。

    背景：关注点在「设置」保存时会整体覆盖入库。老配置如果是在内置清单
    扩充之前保存的，就只剩当时那几项，内置的新关注点（如技术突破、
    人才流动）不会再出现 —— 读取配置时调用本函数自动补齐。

    规则：
    - 存储项按 id（无 id 时按名称）匹配内置项，命中则升级为完整内置定义
      （保留用户改过的 enabled / ai_hint / description）
    - 未命中的按自定义项保留
    - 缺失的内置项按内置顺序追加到末尾
    """
    if not stored:
        return default_focus_points()
    out: list[dict] = []
    seen: set[str] = set()
    for item in stored:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        matched = next(
            (b for b in BUILTIN_FOCUS_POINTS
             if (fid and b["id"] == fid) or (name and b["name"] == name)),
            None,
        )
        if matched is not None:
            if matched["id"] in seen:
                continue  # 去重
            seen.add(matched["id"])
            merged = dict(matched)
            merged["enabled"] = bool(item.get("enabled", matched.get("enabled", True)))
            if item.get("ai_hint"):
                merged["ai_hint"] = item["ai_hint"]
            if item.get("description"):
                merged["description"] = item["description"]
            out.append(merged)
        else:
            kept = dict(item)
            kept.setdefault("builtin", False)
            kept.setdefault("enabled", True)
            out.append(kept)
    for b in BUILTIN_FOCUS_POINTS:
        if b["id"] not in seen:
            out.append(dict(b))
    return out


def default_roles() -> list[dict]:
    return [dict(r) for r in ROLE_TEMPLATES]


def template_by_id(template_id: str) -> dict:
    for t in REPORT_TEMPLATES:
        if t["id"] == template_id:
            return t
    return REPORT_TEMPLATES[0]
