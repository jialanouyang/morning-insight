import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import api from "../api";
import { useToast } from "../components/Toast";
import Logo from "../components/Logo";
import { AlertBar, Card, Loading, PageHead, Stat, Tag } from "../components/ui";
import { useMe, useMeta } from "../store";

const FEATURE_GROUPS = [
  {
    title: "配置",
    items: [
      "行业 / 赛道多选 + 自定义关键词",
      "8 个内置关注点：勾选即出现对应板块，可改定义、可完全自定义",
      "7 个内置角色模板，Prompt 可见可编辑，支持一人多角色",
      "信息源默认启用 + 完整清单（中英文媒体 / 政府机构 / 行业数据库 / 社交社区 / 行业协会）",
      "支持 RSS、API、网页源（CSS 选择器 / AI 解析）与插件源",
      "推送渠道默认全部展示，勾选后展开配置，逐个可测试",
      "调度：每天 / 工作日 / 每周指定日 / 自定义 cron",
      "界面语言 中文 / English；晨报语言 中文 / 英文 / 双语（外文源可自动翻译）",
      "多模型可选 + 自定义附加 Prompt",
    ],
  },
  {
    title: "数据抓取",
    items: [
      "中英文对等，政府与机构报告收录完整",
      "四级优先级：RSS → API → 网页解析 → 浏览器渲染兜底（Playwright，可选依赖）",
      "不按地域设源，按内容相关性筛选（关键词源 + AI 分类）",
      "去重：URL → 标题指纹 → 内容指纹 → 内容相似度（Jaccard）",
      "时间窗默认 24 小时可配，每个源条数可配",
    ],
  },
  {
    title: "AI 处理",
    items: [
      "单条摘要、自动分类（板块 / 关注点 / 语言 / 地区 / 评分）",
      "角色化建议：多角色分别输出视角与行动建议",
      "趋势判断、动态追踪识别、关键词预警",
      "Prompt 可自定义；适配任意 OpenAI 兼容接口（LiteLLM 式）",
      "成本控制：结果缓存、按场景分级调用、内置离线 Embedding 兜底",
    ],
  },
  {
    title: "晨报生成",
    items: [
      "6 套模板：简报版 / 杂志版 / 数据版 / 卡片版 / 终端版 / 打印版",
      "板块级自定义；高级用户可直接写 HTML / CSS 模板",
      "导出 Markdown / HTML / PDF / 图片",
      "历史存档可检索（标题 + 正文 + 日期区间）",
    ],
  },
  {
    title: "推送",
    items: [
      "首发 7 个：邮件 SMTP / 企业微信 / 钉钉 / 飞书 / Telegram / Slack / Discord，外加 Web Push",
      "扩展插件式：Bark / Server 酱 / PushPlus / LINE / 通用 Webhook",
      "微信推送通过 Server 酱 / PushPlus 中转",
      "任一渠道失败不影响其它渠道，全部落库可追溯",
    ],
  },
  {
    title: "知识库 RAG",
    items: [
      "历史晨报与周月报自动入库，切片 → Embedding → 向量存储",
      "语义检索 + 自然语言问答，回答带引用来源",
      "支持时间 / 行业过滤；可切换 Chroma / Qdrant / pgvector",
      "Embedding 可选 OpenAI / 智谱 / BGE，无 Key 时用内置离线算法",
    ],
  },
  {
    title: "动态追踪 / 预警 / 周月报",
    items: [
      "关注公司或产品，增删改；重点 / 一般两级",
      "自动追踪新闻 / 公告 / 融资 / 产品更新 / 高管变动",
      "晨报单独板块，重点变化高亮，多对象并列对比",
      "关键词预警：精确 / 模糊匹配，出现即推 / 达到频次 / 重要来源，含冷却时间与历史",
      "周报每周一、月报每月 1 号，含周期概览、分板块汇总、趋势变化、与上期对比",
    ],
  },
  {
    title: "插件与多用户",
    items: [
      "三类插件：数据源 fetch() / 推送 send() / AI 处理 process()",
      "plugin.yaml + 入口文件，安装 / 启用 / 禁用 / 卸载全生命周期",
      "权限声明、版本管理、插件市场",
      "注册登录、多用户数据隔离、管理员与普通用户角色",
    ],
  },
];

export default function About() {
  const { t } = useTranslation();
  const toast = useToast();
  const meta = useMeta();
  const me = useMe();
  const [feat, setFeat] = useState(null);

  useEffect(() => {
    api
      .features()
      .then(setFeat)
      .catch((e) => toast.err(t("common.failed"), e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <PageHead title={t("about.title")} subtitle={t("about.subtitle")} />

      <Card>
        <div className="row" style={{ gap: 16, alignItems: "flex-start" }}>
          <Logo size={52} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 19, fontWeight: 750 }}>{t("app.full")}</div>
            <div className="text-3 fs-13 mt-8">{t("app.tagline")}</div>
            <div className="row mt-8" style={{ gap: 6 }}>
              <Tag kind="brand">v{feat?.version || meta?.app?.version || "—"}</Tag>
              {me && <Tag kind="accent">{me.role === "admin" ? t("admin.roleAdmin") : t("admin.roleUser")}</Tag>}
              <Tag kind="ok">Apache-2.0</Tag>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-4 mb-14">
        <Stat label={t("about.pushChannels")} value={feat?.capabilities?.push_channels ?? meta?.channels?.length ?? "—"} />
        <Stat label={t("about.templates")} value={feat?.capabilities?.templates ?? meta?.templates?.length ?? "—"} />
        <Stat label={t("about.sourceTypes")} value={feat?.capabilities?.source_types?.length ?? 4} />
        <Stat label={t("about.languages")} value={(feat?.capabilities?.languages || []).join(" / ") || "—"} />
      </div>

      <Card title={t("about.optionalDeps")} subtitle={t("about.installHint")}>
        {feat === null ? (
          <Loading />
        ) : (
          <div className="row" style={{ gap: 10 }}>
            {Object.entries(feat.optional || {}).map(([k, v]) => (
              <div className="src-chip" key={k}>
                <span className={`dot ${v ? "dot-ok" : "dot-warn"}`} />
                {k}: {v ? t("about.ready") : t("about.notReady")}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="导出格式与信息源">
        <div className="row mb-8" style={{ gap: 6 }}>
          {(feat?.capabilities?.report_formats || []).map((f) => (
            <Tag key={f} kind="accent">
              {f}
            </Tag>
          ))}
        </div>
        <div className="row" style={{ gap: 6 }}>
          {(feat?.capabilities?.source_types || []).map((f) => (
            <Tag key={f} kind="brand">
              {f}
            </Tag>
          ))}
          <Tag>{feat?.capabilities?.knowledge_vector_store}</Tag>
        </div>
      </Card>

      <Card title={t("about.capabilities")}>
        {FEATURE_GROUPS.map((g) => (
          <div key={g.title} className="mb-14">
            <div className="card-title mb-8">{g.title}</div>
            {g.items.map((it) => (
              <div className="row fs-13 text-2" key={it} style={{ gap: 8, alignItems: "flex-start" }}>
                <span className="text-ok">✓</span>
                <span style={{ flex: 1 }}>{it}</span>
              </div>
            ))}
          </div>
        ))}
      </Card>

      <Card title={t("about.docs")} subtitle={t("about.docsHint")}>
        <div className="kv">
          <div className="kv-key">README</div>
          <div className="kv-val">部署方式、Docker Compose、环境变量、验收清单</div>
          <div className="kv-key">docs/plugin-dev.md</div>
          <div className="kv-val">插件开发指南：三类插件的接口、权限与打包</div>
          <div className="kv-key">docs/api.md</div>
          <div className="kv-val">REST API 一览</div>
          <div className="kv-key">CONTRIBUTING.md</div>
          <div className="kv-val">贡献指南</div>
        </div>
      </Card>

      {((meta?.channels || []).length > 0) && (
        <Card title={t("about.pushChannels")}>
          <div className="row" style={{ gap: 6 }}>
            {(meta?.channels || []).map((c) => (
              <Tag key={c.id} kind={c.group === "扩展" ? "" : "brand"}>
                {c.name}
              </Tag>
            ))}
          </div>
        </Card>
      )}

      <AlertBar kind="info">
        全部功能为自托管部署，数据存放在你自己的服务器上；除 AI 与推送所需的第三方接口外不产生外部依赖。
      </AlertBar>
    </>
  );
}
