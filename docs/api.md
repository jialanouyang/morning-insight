# 晨析 REST API

基础地址：`http://localhost:8000`，全部接口以 `/api` 开头。
除 `/api/health`、`/api/features`、`/api/meta`、`/api/auth/*` 外，均需携带：

```
Authorization: Bearer <token>
```

`<token>` 来自 `/api/auth/login` 或 `/api/auth/register` 的 `token` 字段。

---

## 系统

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 存活检查 |
| GET | `/api/features` | 能力自检：可选依赖（playwright / webpush / edge_tts）状态 |
| GET | `/api/meta` | 一次性返回全部内置目录（关注点 / 角色 / 模板 / 行业 / 模型预设 / 渠道 / 源清单 / 插件类型与权限） |

---

## 认证 `/api/auth`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/auth/status` | 是否已有用户、是否开放注册（登录页使用） |
| POST | `/api/auth/register` | 注册；首个用户自动成为管理员 |
| POST | `/api/auth/login` | 登录，返回 `{ token, user }` |
| GET | `/api/auth/me` | 当前用户 |
| PUT | `/api/auth/me` | 修改昵称 |
| POST | `/api/auth/password` | 修改密码 `{ old_password, new_password }` |

---

## 配置 `/api/config`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/config` | 读取全部用户配置（密钥字段以 `***` 掩码返回） |
| PUT | `/api/config` | 局部更新（只传要改的字段；`***` 表示保持原值） |
| POST | `/api/config/reset?section=` | 重置配置段：`sources` / `focus_points` / `roles` / `ai_config` / `all` |
| POST | `/api/config/sources/test` | 测试单个信息源，返回样例条目 |
| POST | `/api/config/sources/from-keywords` | 按关键词批量生成 Google News 关键词源 |
| POST | `/api/config/sources/ai-selectors` | 让 AI 推断网页源的 CSS 选择器 |
| POST | `/api/config/channels/test` | 测试推送渠道（`***` 掩码自动回填真实值） |
| POST | `/api/config/webpush/keys` | 生成并保存 VAPID 密钥对 |
| POST | `/api/config/webpush/subscribe` | 保存浏览器推送订阅 |
| GET | `/api/config/webpush/key` | 读取公钥与可用性 |
| POST | `/api/config/ai/test` | 用已保存配置实调一次模型，验证连通性 |
| GET | `/api/config/usage?days=30` | 当前用户的大模型调用量与成本 |

---

## 晨报 `/api/reports`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/reports?q=&date_from=&date_to=&limit=&offset=` | 列表（标题/正文搜索 + 日期区间） |
| GET | `/api/reports/{id}` | 详情（含 Markdown、HTML、引用来源、meta） |
| POST | `/api/reports/{id}/translate` | 一键翻译 `{ target_lang: "zh" \| "en" }`：整篇晨报翻译为界面语言，保留 Markdown 结构；译文按（晨报 × 目标语言）落库缓存 |
| GET | `/api/reports/{id}/preview` | 独立 HTML 预览 |
| POST | `/api/reports/generate` | 立即执行完整链路 `{ push, use_ai, tracking, alerts, tts }` |
| POST | `/api/reports/{id}/push` | 立即推送 `{ channels: [...] }`（不传则推送到全部已启用渠道） |
| GET | `/api/reports/{id}/export?fmt=` | 导出 `md` / `html` / `pdf` / `image` |
| POST | `/api/reports/{id}/tts` | 生成或重新生成语音晨报 `{ provider, voice, fmt, push }` |
| GET | `/api/reports/{id}/tts` | 该晨报的全部语音资产 |
| GET | `/api/reports/tts/assets` | 全部语音资产 |
| GET | `/api/reports/tts/audio/{asset_id}` | 音频文件流 |
| DELETE | `/api/reports/{id}` | 删除晨报 |

---

## 知识库 `/api/knowledge`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/knowledge/ask` | 自然语言问答 `{ question, top_k, date_from, date_to, industry, history }`，返回 `{ answer, sources }` |
| POST | `/api/knowledge/search` | 只检索片段（不调用大模型） |
| GET | `/api/knowledge/stats` | 切片数、按来源类型分布、使用的向量化方式、最近入库时间 |
| POST | `/api/knowledge/ingest?limit=30` | 把尚未入库的晨报 / 周月报补进知识库 |
| POST | `/api/knowledge/reindex?limit=200` | 全量重建索引（切换 Embedding 后需要） |
| DELETE | `/api/knowledge` | 清空当前用户知识库 |

---

## 动态追踪 `/api/competitors`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/competitors` | 关注对象列表 |
| POST | `/api/competitors` | 新建 `{ name, type, keywords, level, notes, enabled }` |
| PUT | `/api/competitors/{id}` | 修改 |
| DELETE | `/api/competitors/{id}` | 删除 |
| GET | `/api/competitors/compare?days=30` | 多对象并列对比（事件数、重点数、按类型分布、最新 3 条） |
| GET | `/api/competitors/{id}/timeline?limit=100` | 单个对象的事件时间线 |
| POST | `/api/competitors/scan?limit=200&use_ai=true` | 对已入库文章立即跑一次追踪识别 |

事件类型：`news` / `announcement` / `funding` / `product` / `executive` / `other`。

---

## 关键词预警 `/api/alerts`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/alerts` | 规则列表 |
| POST | `/api/alerts` | 新建 `{ keyword, match_type, condition, condition_value, channels, cooldown_minutes, enabled }` |
| PUT | `/api/alerts/{id}` | 修改 |
| DELETE | `/api/alerts/{id}` | 删除 |
| GET | `/api/alerts/history?limit=100` | 预警历史 |
| POST | `/api/alerts/scan?limit=200&use_ai=true` | 对已有素材立即检查一次 |

- `match_type`：`exact`（精确）/ `fuzzy`（模糊）
- `condition`：`always`（出现即推）/ `frequency`（达到频次）/ `source`（重要来源才推）

---

## 周报 / 月报 `/api/periodicals`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/periodicals?period_type=&limit=` | 列表 |
| GET | `/api/periodicals/{id}` | 详情 |
| GET | `/api/periodicals/{id}/preview` | HTML 预览 |
| POST | `/api/periodicals/generate` | 生成 `{ period_type, start, end, push }` |
| POST | `/api/periodicals/{id}/push` | 推送 |
| GET | `/api/periodicals/{id}/export?fmt=` | 导出 |
| DELETE | `/api/periodicals/{id}` | 删除 |

---

## 插件 `/api/plugins`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/plugins?type=` | 登录用户 | 已安装插件列表（含校验结果） |
| POST | `/api/plugins/sync` | 管理员 | 扫描插件目录并登记 |
| POST | `/api/plugins/install` | 管理员 | `{ source }`，目录名或绝对路径 |
| POST | `/api/plugins/{id}/enable` | 管理员 | `{ enabled }` |
| PUT | `/api/plugins/{id}/config` | 管理员 | `{ config }` |
| DELETE | `/api/plugins/{id}?remove_files=false` | 管理员 | 卸载 |
| POST | `/api/plugins/{id}/test` | 管理员 | 测试插件（推送类会真发一条） |
| GET | `/api/plugins/marketplace/catalog` | 登录用户 | 插件市场 |
| POST | `/api/plugins/marketplace/{slug}/install` | 管理员 | 从市场安装 |

详见 [plugin-dev.md](./plugin-dev.md)。

---

## 管理后台 `/api/admin`（均需管理员）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/users` | 用户列表（含各自晨报数） |
| PUT | `/api/admin/users/{id}` | `{ role, is_active, display_name }` |
| DELETE | `/api/admin/users/{id}` | 删除用户并级联清理其业务数据 |
| GET | `/api/admin/stats` | 全站统计（用户/晨报/素材/切片/推送成功失败/模型用量） |
| GET | `/api/admin/push-logs?limit=&status=` | 推送记录 |
| GET | `/api/admin/jobs` | 已注册的定时任务与下次执行时间 |
| POST | `/api/admin/jobs/sync` | 手动同步定时任务 |
| GET | `/api/admin/usage?days=30` | 按模型、按用户的用量与成本 |

---

## 错误约定

| 状态码 | 含义 |
|---|---|
| 400 | 参数错误或前置条件不满足（如未配置 AI） |
| 401 | 未登录或令牌失效 |
| 403 | 权限不足（需管理员）、账号被停用、注册已关闭 |
| 404 | 资源不存在或不属于当前用户 |
| 502 | 上游调用失败（大模型、抓取源、推送接口） |

错误响应体统一为 `{ "detail": "人类可读的原因" }`。
