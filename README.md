# 晨析 Morning Insight

<div align="center">  
  <img src="frontend/public/logo.svg" width="72" alt="晨析 Morning Insight" />  
  <p><b>每天清晨，一份懂你的行业分析晨报</b></p>  
  <p>开源 · 自托管 · AI 驱动 · 多用户</p>  
  <p>  
    <a href="#快速开始">快速开始</a> ·  
    <a href="#功能一览">功能一览</a> ·  
    <a href="#目录结构">目录结构</a> ·  
    <a href="#配置说明">配置说明</a> ·  
    <a href="docs/api.md">API 文档</a> ·  
    <a href="docs/plugin-dev.md">插件开发</a>  
  </p>  
</div>

---

## 项目简介

晨析（Morning Insight）是一个**开源自托管的行业分析晨报平台**。

它按你设定的行业、关注点、角色与信息源，定时抓取中英文情报素材，交由 AI 生成一份结构化晨报，  
并通过邮件 / 企业微信 / 钉钉 / 飞书 / Telegram / Slack / Discord 等渠道推送；历史晨报自动入库，  
支持语义检索与自然语言问答，另提供动态追踪、关键词预警、周报月报、语音晨报与插件系统。

- **数据自主**：所有数据存在你自己的服务器上，不经过第三方平台中转。
- **模型可换**：任意 OpenAI 兼容接口（OpenAI / DeepSeek / Kimi / 智谱 / 通义千问 / 硅基流动 / Ollama 本地…）。
- **无 Key 也能跑**：未配置模型时输出「素材版」晨报，知识库使用内置离线检索。
- **多用户隔离**：每个用户拥有独立的配置、晨报、知识库、追踪对象、预警规则与定时任务。

## 功能一览

### 1. 配置体系

| 配置项    | 说明                                                                                        |
| ------ | ----------------------------------------------------------------------------------------- |
| 行业与关键词 | 22 个行业预设多选 + 自定义；关键词可一键生成关键词类信息源                                                          |
| 关注点    | 8 个内置：融资事件、政策监管、技术突破、动态追踪、人才流动、市场数据、竞争格局、供应链。支持「勾选即用 → 改内置定义 → 完全自定义」三层用法，**勾选哪个就出现哪个板块** |
| 角色     | 7 个内置模板：分析师、创业者、产品经理、融资顾问、销售、投资人、市场；System Prompt 可见可编辑，支持自定义与一人多角色                       |
| 信息源    | 默认启用 84 个实测可抓取源（RSS / API / 网页），完整目录 140 个。支持单条添加、全部添加、搜索引擎索引建源                           |
| 推送渠道   | 13 个渠道默认展示，勾选后展开配置，每个渠道均有「测试推送」                                                           |
| 调度     | 每天 / 工作日 / 每周指定日 / 自定义 cron；周报、月报独立定时                                                     |
| 语言     | 界面 简体中文 / English；晨报 中文 / 英文 / 双语，可开启外文源自动翻译                                              |
| 篇幅     | 简报（3-5 分钟）/ 详细（10-15 分钟）                                                                  |
| 模型     | 8 个服务商预设 + 任意 OpenAI 兼容接口，支持自定义附加 Prompt                                                  |

### 2. 数据抓取

- 抓取优先级：**RSS → API → 网页解析 → 浏览器渲染兜底**（需 Playwright，可选依赖）。
- 不按地域设源，按内容相关性筛选（关键词源 + AI 自动分类）。
- 四级去重：URL 精确 → 标题指纹 → 内容指纹 → 内容相似度（Jaccard + 长度惩罚）。
- 时间窗默认 24 小时可配；每源条数可配。
- 发布日期解析覆盖数字时间戳、中文日期、无年份日期、相对时间（`3分钟前`）、链接内嵌日期    
  （如 `/20260929/`、`t20260731_xxx.html`）等中文站点常见写法。
- 失效源独立容错，不影响其他源；支持多线程并发抓取。

### 3. AI 处理

- 单条摘要、自动分类（板块 / 关注点 / 语言 / 地区 / 重要度评分）。
- 角色化建议与多角色视角（Prompt 集中管理，全部可编辑）。
- 趋势判断、动态追踪识别、关键词预警判定。
- 成本控制：进程内结果缓存、按场景分级调用、Token 与成本落库统计。

### 4. 晨报生成与翻译

- **首页聚焦今日晨报**：今日晨报以大标题 + 完整正文作为页面视觉中心，卡片内提供翻译 / 预览 / 查看晨报操作；下方保留「最近晨报」列表，便于进入近期历史晨报（首页不再展示统计数字）。
- **6 套模板**：简报版、杂志版、数据版、卡片版、终端版、打印版，每套有独立版式、配色与写作风格。
- 高级用户可直接写自定义 HTML / CSS 模板（占位符 `{{title}}`、`{{content}}`、`{{accent}}`、`{{css}}`）。
- 导出 **Markdown / HTML / PDF / 图片**；历史晨报可检索（标题 + 正文 + 日期区间）。
- **一键翻译（译文保留原文结构与排版）**：
  - 入口：首页「今日晨报」卡片、「最近晨报」列表、「晨报预览」弹窗，以及晨报详情页操作栏。
  - 交互：翻译中 → 失败可重试 → 成功后「显示原文 / 显示译文」随时切换；译文生效时带「译文」标签。
  - 条件：**仅当晨报语言与当前界面语言不一致时**才出现翻译按钮（例：中文界面看英文晨报）。
  - 缓存：译文按「晨报 × 目标语言」落库，重复查看不再调用模型。

### 5. 推送

| 分组    | 渠道                                                        |
| ----- | --------------------------------------------------------- |
| 通用    | 邮件 SMTP、Web Push（VAPID）、通用 Webhook（自定义方法 / 鉴权头 / JSON 模板） |
| 国内 IM | 企业微信机器人、钉钉机器人（加签）、飞书机器人（加签 + 卡片）                          |
| 海外 IM | Telegram Bot（支持语音条）、Slack、Discord                         |
| 微信中转  | Server 酱、PushPlus                                         |
| 移动端   | Bark（iOS）                                                 |

渠道失败相互隔离：任一渠道异常不影响其他渠道，全部落库可在管理后台追溯。

### 6. 知识库 RAG

- 历史晨报与周月报自动入库：切片 → Embedding → 向量存储。
- 自然语言问答，回答带引用来源（可回溯到原报告），支持时间 / 行业过滤。
- 纯检索模式（不调用大模型，快速定位片段）。
- Embedding 可选（5 种：自动 / OpenAI / 智谱 / BGE / 内置离线）。
- 向量库可选 4 种：内置（SQLite + 余弦检索）/ Chroma / Qdrant / pgvector。

### 7. 动态追踪与关键词预警

- **动态追踪**：关注公司或产品，自动识别新闻 / 公告 / 融资 / 产品更新 / 高管变动等事件，    
  晨报中单独成板块，每个对象有事件时间线，支持多对象并列对比。
- **关键词预警**：精确 / 模糊匹配，出现即推 / 达频次才推 / 重要来源才推，支持冷却时间与渠道指定，    
  完整预警历史留痕。

### 8. 周报 / 月报 · 语音晨报 · 插件

- **周报 / 月报**：每周一 / 每月 1 号自动生成，也可手动指定周期；含周期概览、分板块汇总、趋势变化与上期对比。
- **语音晨报**：Edge TTS（免费，多音色）/ OpenAI TTS，输出 MP3 或 OGG（Telegram 语音条），可随晨报一并推送。
- **插件系统**：三类插件（数据源 / 推送 / AI 处理），`plugin.yaml` 声明元信息、权限与配置 schema，    
  支持安装 / 启用 / 禁用 / 卸载与市场收录，仓库自带 3 个示例插件。

### 9. 用户与权限

- 邮箱注册 / 登录（PBKDF2 密码哈希 + JWT），支持关闭自助注册。
- 多用户数据完全隔离；角色分管理员 / 普通用户。
- 管理后台：用户管理、系统统计、推送记录、定时任务、模型用量。

## 界面预览

| 登录 | 首页                                                                    |
| -- | --------------------------------------------------------------------- |
| 登录 | 一、整批重新截取项目截图：确保每张截图完整展示对应界面内容，整批截图风格统一（相同的主题、窗口尺寸、分辨率和界面状态），避免新旧版本混用。 |

| 晨报历史 | 知识库问答 |
| ---- | ----- |
| 晨报历史 | 知识库问答 |

| 动态追踪 | 关键词预警 |
| ---- | ----- |
| 动态追踪 | 关键词预警 |

| 插件 | 设置 |
| -- | -- |
| 插件 | 设置 |

> 周报月报、管理后台、关于与自检的截图见 [`docs/screenshots/`](docs/screenshots/)；>   
> 截图均使用演示数据，不含任何真实账号或密钥。

## 环境要求

| 组件               | 版本                     | 说明                   |
| ---------------- | ---------------------- | -------------------- |
| Python           | 3.10+（推荐 3.12）         | 后端运行环境               |
| Node.js          | 18+（推荐 20）             | 前端构建与开发服务            |
| Docker / Compose | 可选                     | 一键部署方式               |
| 数据库              | SQLite（默认）/ PostgreSQL | 通过 `DATABASE_URL` 切换 |

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
git clone <你的仓库地址> morning-insight
cd morning-insight

# （可选）复制部署配置；生产环境务必修改 SECRET_KEY
cp backend/.env.example backend/.env
# python -c "import secrets;print(secrets.token_urlsafe(48))"

docker compose up -d
```

打开 `http://localhost:8080`，注册账号（**首个用户自动成为管理员**），随后：

1. **设置 → AI 模型**：填 API 地址 / 密钥 / 模型名，点「测试连接」。
2. **设置 → 行业与关键词 / 关注点 / 角色 / 信息源**：按需调整（默认配置已可直接运行）。
3. **设置 → 推送渠道**：勾选渠道、填参数、点「测试推送」。
4. 回到**首页**，点「立即生成晨报」。
5. 想让它自动跑：**设置 → 调度** 打开开关，选择频率与时间。

### 方式二：手动部署 / 本地开发

**后端**：

```bash
cd backend
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                            # 记得修改 SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

可选增强依赖（不装也能跑，代码会自动检测并降级）：

```bash
pip install -r requirements-optional.txt
playwright install chromium   # 仅在需要 JS 渲染抓取 / 导出图片时
```

**前端**：

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173，已配置 /api 代理到 127.0.0.1:8000
npm run build    # 产出 frontend/dist
```

> 开发环境代理默认指向 `127.0.0.1:8000`。如需改端口，设置环境变量 `API_TARGET`。

**演示数据（可选）**：写入演示账号 `demo@example.com / demo1234` 与一份示例晨报。

```bash
cd backend
python scripts/seed_demo.py
```

## 目录结构

```
morning-insight/
├── backend/
│   ├── app/
│   │   ├── main.py                 # 应用入口：CORS、自动迁移、调度器、能力自检
│   │   ├── settings.py             # 环境变量配置（含默认值）
│   │   ├── database.py             # 引擎 / 会话 / Base
│   │   ├── models.py               # 16 张数据表
│   │   ├── migrate.py              # 轻量自动迁移（ALTER TABLE ADD COLUMN）
│   │   ├── security.py             # PBKDF2 密码哈希 + JWT + 角色校验
│   │   ├── ai/                     # catalog（关注点/角色/模板/行业/服务商）、llm、prompts、processing
│   │   ├── fetcher/                # rss、api_source、web_source、browser、dedup、catalog、service
│   │   ├── report/                 # render（6 套主题）、export（md / html / pdf / 图片）
│   │   ├── push/                   # base（渠道注册表）、dispatcher、wechat_style、channels/（13 个渠道）
│   │   ├── plugins/                # base（清单校验）、loader（动态加载）、registry（生命周期）
│   │   ├── routers/                # 10 个路由模块（auth / config / report / knowledge / …）
│   │   ├── services/               # pipeline、scheduler、knowledge、competitor、alert、
│   │   │                           # periodical、tts、translation、i18n
│   │   └── utils/text.py           # 清洗、指纹、相似度、语言检测、时长估算
│   ├── tests/                      # test_api.py、test_fetcher.py（共 74 项，不依赖外网）
│   ├── scripts/seed_demo.py        # 演示账号 + 示例晨报（直连数据库）
│   ├── requirements.txt            # 主依赖
│   ├── requirements-optional.txt   # playwright / pywebpush / chromadb 等可选增强
│   ├── requirements-dev.txt        # 测试依赖
│   ├── .env.example                # 部署级配置示例
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                  # Login、Dashboard、Reports、Knowledge、Competitors、
│   │   │                           # Alerts、Periodicals、Plugins、Settings、Admin、About
│   │   ├── components/             # ui.jsx（基础组件）、Toast、Markdown、ReportTranslate、Logo
│   │   ├── i18n/                   # react-i18next + zh / en 词条（本地词条，无需联网）
│   │   ├── api.js                  # 全部后端端点封装（自动带 Token、401 跳登录）
│   │   ├── store.js                # 元信息 / 当前用户 / 配置的共享状态
│   │   ├── App.jsx                 # 路由与整体布局
│   │   └── styles.css              # 设计系统（主色橙 #F6A821 / 蓝 #2B9CD8）
│   ├── public/                     # logo.svg、sw.js（Web Push）
│   ├── Dockerfile + nginx.conf     # 生产镜像与反向代理配置
│   └── package.json
├── plugins/                        # 3 个示例插件：source-example / push-example / ai-example
├── scripts/
│   ├── seed_demo.py                # 演示数据（走 HTTP API，含追踪对象与预警规则）
│   └── shot.cjs                    # 界面截图脚本（Chrome DevTools Protocol）
├── docs/
│   ├── api.md                      # REST API 一览
│   ├── plugin-dev.md               # 插件开发指南
│   └── screenshots/                # 界面截图
├── config.example.yaml             # 全部配置项的中文注释说明
├── docker-compose.yml
├── .github/workflows/ci.yml        # CI：后端测试 + 前端构建
├── CONTRIBUTING.md
├── LICENSE                         # Apache License 2.0
└── README.md
```

### 架构概览

```
┌───────────────────────────────────────────────────────────────┐
│  前端 React 18 + Vite  ── /api ──▶  FastAPI + SQLAlchemy 2.0   │
├───────────────────────────────────────────────────────────────┤
│  抓取层  fetcher/   RSS · API · 网页 · 插件源 · 浏览器兜底       │
│  去重层  dedup.py   URL → 标题指纹 → 内容指纹 → 相似度           │
│  AI 层   ai/        Prompt 工厂 · LLM 适配 · Embedding · 缓存    │
│  生成层  report/    6 套模板 · Markdown→HTML · PDF / 图片导出    │
│  推送层  push/      13 个渠道 · 注册表驱动 · 失败隔离            │
│  服务层  services/  pipeline · scheduler · knowledge ·          │
│                     competitor · alert · periodical · tts ·     │
│                     translation                                 │
│  插件层  plugins/   清单解析 · 动态加载 · 生命周期 · 市场        │
│  调度层  APScheduler（每用户独立任务 + 周月报任务）              │
│  存储层  SQLite（可换 PostgreSQL）· 内置向量检索                 │
└───────────────────────────────────────────────────────────────┘
```

## 配置说明

### 部署级配置（环境变量）

复制 `backend/.env.example` 为 `backend/.env` 后按需修改：

| 变量                       | 默认值                                   | 说明                                   |
| ------------------------ | ------------------------------------- | ------------------------------------ |
| `SECRET_KEY`             | `dev-secret-do-not-use-in-production` | JWT 签名密钥，**生产环境必须改为随机长字符串**          |
| `DATABASE_URL`           | `sqlite:///./data/morning_insight.db` | 任意 SQLAlchemy 连接串，可换 PostgreSQL      |
| `TOKEN_EXPIRE_HOURS`     | `72`                                  | 登录令牌有效期                              |
| `TIMEZONE`               | `Asia/Shanghai`                       | 调度器时区                                |
| `DATA_DIR`               | `./data`                              | 数据库、语音音频、导出文件目录                      |
| `ALLOW_REGISTRATION`     | `true`                                | 是否开放自助注册（首个用户始终可注册并成为管理员）            |
| `PLUGIN_INSTALL_ENABLED` | `true`                                | 是否允许在界面安装插件；插件为本机 Python 代码，公网部署建议关闭 |
| `PLUGIN_DIR`             | `<repo>/plugins`                      | 插件目录                                 |

前端开发环境变量：

| 变量           | 默认值                     | 说明             |
| ------------ | ----------------------- | -------------- |
| `API_TARGET` | `http://127.0.0.1:8000` | Vite 开发代理的后端地址 |


### 用户级配置（界面内「设置」页面）

AI 模型、信息源、推送渠道、语音、知识库、抓取参数等均为**用户级配置**：  
多用户各用各的，密钥只写入本地数据库，不进入部署配置，也不会出现在代码仓库中。  
完整字段说明见 [`config.example.yaml`](config.example.yaml)。

### AI 服务商（任意 OpenAI 兼容接口）

| 服务商        | API 地址                                              | 模型示例                       |
| ---------- | --------------------------------------------------- | -------------------------- |
| OpenAI     | `https://api.openai.com/v1`                         | `gpt-4o-mini`              |
| DeepSeek   | `https://api.deepseek.com/v1`                       | `deepseek-chat`            |
| 月之暗面 Kimi  | `https://api.moonshot.cn/v1`                        | `moonshot-v1-8k`           |
| 智谱 GLM     | `https://open.bigmodel.cn/api/paas/v4`              | `glm-4-air`                |
| 通义千问       | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`                |
| 硅基流动       | `https://api.siliconflow.cn/v1`                     | `Qwen/Qwen2.5-7B-Instruct` |
| Ollama（本地） | `http://host.docker.internal:11434/v1`              | `qwen2.5:7b`               |

## 数据与隐私

- **本地数据目录不入库**：`DATA_DIR`（默认 `backend/data/`）内含 SQLite 数据库、语音音频与导出文件，    
  已在 `.gitignore` 中排除。首次启动会自动创建该目录。
- **密钥不落代码**：用户的 AI 密钥、推送 Token 等只保存在本地数据库的 `user_configs` 中，    
  接口返回时按需掩码；仓库内所有示例均为占位值（如 `you@example.com`、`change-me-to-a-random-secret-string`）。
- **部署前检查**：修改 `SECRET_KEY`；公网环境建议设置 `ALLOW_REGISTRATION=false` 与    
  `PLUGIN_INSTALL_ENABLED=false`；数据库与备份注意访问权限。
- **截图与文档**：仓库内截图使用演示数据，不含真实账号、邮箱或密钥。

## 测试

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

**74 项测试**（`test_api.py` 42 项 + `test_fetcher.py` 32 项），全部不依赖外网与真实密钥：

- 认证与权限：首个用户即管理员、重复注册、弱密码、令牌校验、管理员端点 403、多用户数据隔离。
- 配置读写：密钥掩码与回传保持、各配置段往返、重置、渠道测试错误路径。
- 完整链路：抓取 → AI 生成 → 入库 → 列表 → 详情 → 导出（md / html / pdf），AI 由测试内置 Mock 提供。
- 知识库入库 / 检索 / 问答 / 重建索引；动态追踪、关键词预警、周报月报的增删改查与扫描。
- 插件发现、启用 / 禁用、市场；管理后台统计、定时任务、推送记录、模型用量。
- 抓取层：时间窗过滤、失效源容错、四级去重、源目录完整性。

前端构建校验：

```bash
cd frontend && npm run build
```

## 常见问题

**Q：找不到「翻译」按钮？**  
翻译入口只在**晨报语言与界面语言不一致**时出现。中文界面阅读中文晨报时不会显示；  
把界面语言切换为 English 后，中文晨报的翻译按钮会出现在首页三处（今日晨报卡片、最近晨报列表、预览弹窗）  
与晨报详情页操作栏。晨报历史**列表行不放入口**，需点开某份晨报。

**Q：没有模型密钥能用吗？**  
可以。未配置模型时输出结构化「素材版」晨报，知识库走内置离线检索；配置模型后自动升级为完整晨报。

**Q：抓不到某些源？**  
部分站点需要 JS 渲染，安装可选依赖后启用：`pip install -r requirements-optional.txt && playwright install chromium`。  
另可检查「设置 → 信息源」中该源是否启用，以及抓取时间窗是否过窄。

**Q：如何更换数据库？**  
修改 `DATABASE_URL` 后重新启动即可（表结构会自动创建 / 增量补齐）。

**Q：生产环境怎么部署？**  
`docker compose up -d` 后由 Nginx 反代前端并转发 `/api` 到后端；务必修改 `SECRET_KEY`  
并按需关闭自助注册与插件安装。

## 参与贡献

欢迎提交 Issue 与 Pull Request，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## Roadmap

- [x] 配置体系（关注点 / 角色 / 信息源 / 渠道 / 模型）
- [x] 抓取（RSS / API / 网页 / 插件源）+ 四级去重
- [x] AI 处理（摘要 / 分类 / 角色建议 / 趋势 / 追踪 / 预警）
- [x] 晨报生成（6 套模板 + 自定义 HTML/CSS，4 种导出）
- [x] 晨报一键翻译（译文保留结构与排版，按语言缓存）
- [x] 推送（13 个渠道，失败隔离，测试推送）
- [x] 知识库 RAG（自动入库 / 语义检索 / 自然语言问答 / 引用溯源）
- [x] 动态追踪、关键词预警、周报月报
- [x] 插件系统（含市场与 3 个示例插件）
- [x] 语音晨报（Edge TTS / OpenAI TTS）
- [x] 多用户与权限、管理后台
- [ ] 移动端适配增强
- [ ] 团队共享信息源与模板库

## License

[Apache License 2.0](LICENSE)

---

<div align="center">

**English**

**Morning Insight** is an open-source, self-hosted industry-intelligence briefing platform.

It fetches Chinese and English sources (RSS / API / web / plugin) on a configurable schedule, generates a  
structured briefing with any OpenAI-compatible LLM according to your focus points and analyst roles, and  
delivers it to email, WeCom, DingTalk, Feishu, Telegram, Slack, Discord, Web Push and more. Every issue is  
archived, indexed and searchable; a built-in RAG knowledge base answers questions with citations. One-click  
translation keeps the original layout while rendering a briefing in your UI language. Extras: competitor  
tracking, keyword alerts, weekly/monthly digests, TTS audio briefings, a plugin system and multi-user isolation.

Quick start: `docker compose up -d` → open `http://localhost:8080` → register (the first user becomes admin)  
→ configure AI & sources in Settings → generate your first briefing.

</div>
