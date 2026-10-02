# 晨析插件开发指南

晨析的插件系统覆盖三类扩展点，均为**本地 Python 包**形式：

| 类型 | 作用 | 必须实现的函数 |
|---|---|---|
| `source` | 数据源：从任意来源拉取素材 | `fetch(config, since_hours, limit) -> list[dict]` |
| `push` | 推送：把晨报送到任意通道 | `send(config, msg) -> dict \| bool \| None` |
| `ai` | AI 处理：对文本做自定义加工 | `process(prompt, text, config) -> str` |

> ⚠️ **安全提示**：插件是本机 Python 代码，安装即代表允许其在本服务进程内执行。
> `permissions` 是**声明式**标记，用于安装前提示，不做运行期沙箱限制。
> 请只安装你信任来源的插件。可通过环境变量 `PLUGIN_INSTALL_ENABLED=false` 关闭安装入口。

---

## 一、目录结构

```
plugins/
└── my-source-plugin/
    ├── plugin.yaml       # 清单元信息（必需）
    └── plugin.py         # 入口文件（默认名，可在 entry_point 改）
```

`plugin.yaml` 示例：

```yaml
name: my-source-plugin          # 唯一名称，也是市场 slug
type: source                    # source | push | ai
version: 0.1.0
author: your-name
description: 从 XXX 抓取行业动态
entry_point: plugin.py          # 相对目录的入口文件
permissions: [network]          # 可选：network / filesystem / secrets / llm / subprocess
config_schema:                  # 可选：给界面展示的配置说明（现状为只读 JSON）
  api_key:
    type: string
    label: API Key
```

---

## 二、数据源插件

```python
# plugins/my-source-plugin/plugin.py
import httpx

DEFAULT_FIELDS = {
    "title": "title",
    "url": "url",
    "summary": "description",
    "published_at": "published_at",
    "source": "site_name",
}

def fetch(config: dict, since_hours: int = 24, limit: int = 50) -> list[dict]:
    """返回素材列表。每条至少包含 title 与 url。"""
    base = config.get("base_url") or "https://api.example.com/posts"
    params = {"limit": min(limit, 100)}
    if config.get("api_key"):
        params["key"] = config["api_key"]

    resp = httpx.get(base, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    items = []
    for row in (data.get("items") or [])[:limit]:
        items.append({
            "title": row.get("title", "").strip(),
            "url": row.get("url", ""),
            "summary": row.get("summary", ""),
            "published_at": row.get("created_at", ""),   # ISO 8601 或 RFC 2822 均可
            "source": row.get("author") or "My Source",
            "language": "zh",
            "region": "中国",
        })
    return items
```

**入参说明**

- `config`：该插件在「插件 → 配置」里保存的 JSON。
- `since_hours`：时间窗（小时），插件应尽量据此过滤。
- `limit`：单次最多返回条数。

**返回要求**

- 返回 `list[dict]`，每条建议包含：`title`（必需）、`url`（必需）、`summary`、`published_at`、`source`、`language`、`region`。
- 时间字段可交给晨析统一解析（支持 ISO 8601、RFC 2822、`YYYY-MM-DD HH:MM` 等）。
- 去重由晨析统一处理（URL → 标题指纹 → 内容指纹 → 内容相似度），插件无需去重。

**启用后如何生效**

在「设置 → 信息源 → 添加信息源」中选择类型 `plugin`，或直接在抓取流程中由晨析自动合并已启用的 source 插件结果。

---

## 三、推送插件

```python
# plugins/my-push-plugin/plugin.py
import httpx

def send(config: dict, msg) -> dict:
    """msg 是 PushMessage 对象，见下表。"""
    url = config.get("url")
    if not url:
        return {"ok": False, "detail": "缺少 url"}

    body = {
        "title": msg.title,
        "text": msg.plain(),       # Markdown 转成的纯文本
        "html": msg.html(),        # 渲染后的 HTML
        "kind": msg.kind,          # report / periodical / alert / test
    }
    resp = httpx.post(url, json=body, timeout=20,
                      headers={"Authorization": config.get("token", "")})
    ok = resp.status_code < 400
    return {"ok": ok, "detail": f"HTTP {resp.status_code}"}
```

**`msg`（PushMessage）字段**

| 字段 | 说明 |
|---|---|
| `title` | 标题 |
| `content_md` | Markdown 正文 |
| `content_html` | 已渲染 HTML（可能为空） |
| `url` | 跳转链接（可能为空） |
| `attachments` | `[{"path": ..., "name": ...}]`，语音晨报会带音频 |
| `kind` | `report` / `periodical` / `alert` / `test` |
| `msg.plain()` | 转纯文本 |
| `msg.html()` | 转 HTML（自动兜底渲染） |

**返回**

可以返回 `dict`（推荐，含 `ok` 与 `detail`）、`bool`，或 `None`（视为成功）。
抛出的异常会被捕获并记录到「管理后台 → 推送记录」，不会中断其它渠道。

---

## 四、AI 处理插件

```python
# plugins/my-ai-plugin/plugin.py
import re

KEYWORDS = ("融资", "收购", "IPO", "政策", "监管")

def process(prompt: str, text: str, config: dict) -> str:
    """prompt 为调用方给的指令，text 为待处理文本，返回处理后的字符串。"""
    hits = [k for k in KEYWORDS if k in text]
    prefix = config.get("prefix") or "AI 插件处理结果"
    head = text.strip().split("\n")[0][:120]
    lines = [f"**{prefix}**", "", f"- 命中关键词：{'、'.join(hits) or '无'}", f"- 首行：{head}"]
    return "\n".join(lines)
```

- `prompt`：晨析传入的指令（例如「请给这条资讯写一句摘要」）。
- `text`：待处理的素材文本。
- `config`：插件配置 JSON。
- 返回字符串会被当作处理结果使用；当晨析未配置大模型时，AI 插件可作为**规则兜底**。

---

## 五、安装与管理

**方式一：界面**

1. 把插件目录放入仓库根目录的 `plugins/`。
2. 管理员进入「插件 → 扫描插件目录」，晨析会读取 `plugin.yaml` 并登记。
3. 点击「安装」→「启用」。推送类插件可点「测试推送」。

**方式二：市场**

「插件 → 插件市场」列出内置收录的插件条目，点击「安装」按 slug 从 `plugins/<slug>` 安装。

**方式三：API**

```bash
# 安装（source 为 plugins/ 下的目录名，或绝对路径）
curl -X POST http://localhost:8000/api/plugins/install \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"source": "my-source-plugin"}'

# 启用 / 禁用
curl -X POST http://localhost:8000/api/plugins/1/enable \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# 写入配置
curl -X PUT http://localhost:8000/api/plugins/1/config \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"config": {"api_key": "xxx"}}'
```

**卸载**

`DELETE /api/plugins/{id}?remove_files=false`，`remove_files=true` 会同时删除 `plugins/` 下的文件。

---

## 六、调试建议

- 插件导入失败时，错误会显示在「插件」卡片的 `invalid` 徽标与错误文案里；后端日志也会记录 `跳过插件目录 ...`。
- 用 `POST /api/plugins/{id}/test` 触发一次推送插件测试。
- 数据源插件可直接用「设置 → 信息源 → 添加信息源」的 `测试` 按钮验证抓取结果。
- 开发期可关闭安装限制：`PLUGIN_INSTALL_ENABLED=false` 只影响界面安装，不影响已安装插件的执行。

---

## 七、参考实现

仓库内的三个示例插件可直接对照：

```
plugins/source-example/   # Hacker News Algolia API → 素材
plugins/push-example/     # 自定义签名 Header + 自定义 JSON 到任意 HTTP 接口
plugins/ai-example/       # 无大模型时用规则输出摘要 + 关键词
```
