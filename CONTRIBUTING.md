# 贡献指南

感谢你对「晨析 Morning Insight」的关注！欢迎提交 Issue 与 Pull Request。

## 开发环境

**后端**（Python 3.10+，推荐 3.12）：

```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                            # 记得修改 SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

可选增强依赖（不装也能跑，代码会检测并优雅降级）：

```bash
pip install -r requirements-optional.txt
playwright install chromium   # 仅当需要 JS 渲染 / 导出图片
```

**前端**（Node 18+）：

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 自动代理到 127.0.0.1:8000
npm run build      # 产出 dist/
npm run preview    # 预览构建产物（同样代理 /api）
```

> 若后端不在默认端口，用 `API_TARGET=http://127.0.0.1:9000 npm run dev` 覆盖代理目标。

## 测试

```bash
cd backend && pytest -v
```

74 项测试（test_api.py 42 项 + test_fetcher.py 32 项）覆盖认证与权限、配置掩码与往返、完整生成链路（AI 由内置 Mock 服务提供，**无需真实密钥、不依赖外网**）、知识库、动态追踪、关键词预警、周月报、插件系统、管理后台、多用户隔离，以及抓取层的时间窗过滤 / 失效源容错 / 四级去重。

提交 PR 前请确保：

1. `cd backend && pytest -v` 全部通过
2. `cd frontend && npm run build` 构建成功
3. 新增接口请在 `backend/tests/test_api.py` 中补充测试（尽量不依赖外网）

## 代码约定

### 分层

```
routers/   HTTP 层：参数校验 + 编排，不写业务逻辑
services/  业务层：pipeline / scheduler / knowledge / competitor / alert / periodical / tts
fetcher/   抓取层：rss / api_source / web_source / browser / dedup / catalog
ai/        AI 层：catalog（内置目录）/ llm（模型适配）/ prompts（Prompt 工厂）/ processing
report/    生成层：render（模板与主题）/ export（md·html·pdf·png）
push/      推送层：base（渠道注册表）/ dispatcher / channels/
plugins/   插件层：base（清单）/ loader / registry
```

### 数据与命名

- 用户配置字段：`industry` `industries` `keywords` `focus_points` `roles` `sources` `ai_config` `push_config` `schedule` `template` `template_config` `ui_language` `report_language` `tts_config` `knowledge_config` `fetch_config`
- 晨报字段：`report_date` `title` `content_md` `content_html` `sources_used` `meta`
- 改动字段名前请全局检索，避免前后端不一致。

### 安全

- **密钥**：任何密钥字段在 API 响应中必须掩码为 `***`，且收到 `***` 时表示「保持原值」。
- **AI 配置入参**：`ai/processing.py` 中的函数既可能收到 `config_payload()` 的完整载荷，也可能收到裸的 `ai_config`；统一走 `_ai_cfg(cfg)` 取真正的模型配置，不要直接 `cfg.get("base_url")`。
- **插件**：插件是本机 Python 代码，`permissions` 只是声明式提示，不做运行期沙箱。任何涉及插件执行的改动都要在 UI 上保留安全提示。

### 前端

- 品牌色用 CSS 变量（`--brand` 橙 `#F6A821` / `--accent` 蓝 `#2B9CD8`），不要硬编码色值。
- 页面放 `src/pages/`，通用组件放 `src/components/ui.jsx`（表单、空态、模态、折叠等）。
- 所有文案走 i18n：在 `src/i18n/locales/zh.json` 与 `en.json` **两份同步新增**（可用下述一行命令自查）。
- 不要在 `<button>` 里嵌套 `<Switch>` / `<input>` 等交互控件（会触发 HTML 嵌套错误与点击穿透），折叠面板用 `Accordion` 组件。

**词条一致性自查**：

```bash
cd frontend/src/i18n/locales && node -e "
const fs=require('fs');
const flat=(o,p='')=>Object.entries(o).flatMap(([k,v])=>typeof v==='object'&&v?flat(v,p+k+'.'):[p+k]);
const zk=new Set(flat(JSON.parse(fs.readFileSync('zh.json','utf8'))));
for(const l of ['en']){
  const dk=new Set(flat(JSON.parse(fs.readFileSync(l+'.json','utf8'))));
  console.log(l,'缺',[...zk].filter(k=>!dk.has(k)).join(',')||'无');
}"
```

### 提交信息

使用 Conventional Commits：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`。

## 扩展点

### 新增推送渠道（最简单）

在 `backend/app/push/channels/` 下新建模块，写一个 `send(config, msg) -> PushResult`，然后注册：

```python
from ..base import ChannelSpec, PushResult, register

def send(config, msg):
    ...
    return PushResult("mychannel", True, "OK")

register(ChannelSpec(
    id="mychannel",
    name="我的渠道",
    doc="如何获取参数……",          # 会显示在设置页，指导用户配置
    fields=[                        # UI 会按此自动生成配置表单
        {"key": "token", "label": "Token", "type": "password", "required": True, "secret": True},
        {"key": "enabled", "label": "启用", "type": "boolean"},
    ],
    group="扩展",                   # 首发 / 扩展
    send=send,
))
```

再在 `push/channels/__init__.py` 中 import 该模块即生效。**不需要改前端**——设置页会依据 `fields` 自动渲染表单并生成「测试推送」按钮。

### 新增信息源类型

在 `backend/app/fetcher/` 下新增抓取函数（返回 `make_item()` 归一化后的 dict 列表），在 `service.py::fetch_source_items` 按 `type` 分发，并在 `catalog.py::source_templates()` 补上表单字段说明。

### 新增晨报模板

在 `backend/app/ai/catalog.py::REPORT_TEMPLATES` 追加一条（含 `layout` / `llm_style` / `accent`），并在 `report/render.py::THEME_CSS` 中为该 `layout` 提供样式。

### 新增外部插件

见 [docs/plugin-dev.md](docs/plugin-dev.md)。仓库内 `plugins/` 下有三个可运行的示例。

## 路线图

见 [README](README.md#-roadmap)。想认领某个方向，欢迎先在 Issue 中讨论实现方案。
