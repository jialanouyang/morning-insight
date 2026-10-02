import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Markdown from "../components/Markdown";
import { TranslateButton, TranslateErrorBar, useReportTranslate } from "../components/ReportTranslate";
import { useToast } from "../components/Toast";
import {
  AlertBar,
  Card,
  Empty,
  Loading,
  Modal,
  PageHead,
  Switch,
  Tag,
} from "../components/ui";
import { useConfig, useMe } from "../store";

const DEFAULT_OPTS = { push: true, use_ai: true, tracking: true, alerts: true, tts: false };

/** 今日晨报主卡片：首页视觉焦点 —— 突出标题与完整正文，语言不一致时可一键翻译并原文 ⇄ 译文切换。 */
function TodayReportCard({ report, onPreview, onOpen }) {
  const { t } = useTranslation();
  const tr = useReportTranslate(report);
  const content = tr.view("content_md") || report.content_md || report.excerpt || "";

  return (
    <Card className="today-card">
      <div className="today-tags">
        <Tag kind="ok">{report.report_date}</Tag>{" "}
        <Tag kind="accent">{report.template}</Tag>{" "}
        {report.meta?.model && <Tag>{report.meta.model}</Tag>}
        {tr.showingTranslated && <Tag kind="brand">{t("translate.tag")}</Tag>}
      </div>

      <h2 className="today-title">{tr.view("title") || report.title}</h2>
      <div className="today-meta">
        {t("dashboard.todayReport")} · {t("reports.sourceCount", { count: report.source_count })}
      </div>

      <div className="today-actions">
        <TranslateButton tr={tr} primary />
        <button className="btn btn-sm" onClick={() => onPreview(report.id)}>
          {t("common.preview")}
        </button>
        <button className="btn btn-sm btn-primary" onClick={() => onOpen(report.id)}>
          {t("dashboard.viewReport")}
        </button>
      </div>

      {tr.needsTranslate && !tr.hasResult && !tr.loading && !tr.error && (
        <AlertBar kind="info" action={<TranslateButton tr={tr} primary />}>
          {t("translate.hint")}
        </AlertBar>
      )}
      <TranslateErrorBar tr={tr} />

      <div className="today-content">
        <Markdown>{content}</Markdown>
      </div>

      {tr.hasResult && (
        <div className="row mt-14" style={{ gap: 8 }}>
          <TranslateButton tr={tr} primary />
          {tr.showingTranslated && <Tag kind="brand">{t("translate.tag")}</Tag>}
        </div>
      )}
    </Card>
  );
}

/** 最近晨报列表行：每条提供翻译按钮，标题 / 摘要支持原文 ⇄ 译文切换。 */
function RecentReportRow({ report, onPreview, onOpen }) {
  const { t } = useTranslation();
  const tr = useReportTranslate(report);

  return (
    <div className="list-row">
      <div className="list-row-main">
        <div className="list-row-title">
          <a
            href={`/reports?id=${report.id}`}
            onClick={(e) => {
              e.preventDefault();
              onOpen(report.id);
            }}
          >
            {tr.view("title") || report.title}
          </a>{" "}
          {tr.showingTranslated && <Tag kind="brand">{t("translate.tag")}</Tag>}
        </div>
        <div className="list-row-meta">
          <span>{report.report_date}</span>
          <Tag>{report.template}</Tag>
          <span>{t("reports.sourceCount", { count: report.source_count })}</span>
        </div>
        <div className="list-row-text clamp-2">{tr.view("excerpt") || report.excerpt}</div>
      </div>
      <div className="list-row-actions">
        <TranslateButton tr={tr} />
        <button className="btn btn-sm" onClick={() => onPreview(report.id)}>
          {t("common.preview")}
        </button>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const toast = useToast();
  const me = useMe();
  const { config, loading: cfgLoading } = useConfig();

  const [reports, setReports] = useState(null);
  const [opts, setOpts] = useState(DEFAULT_OPTS);
  const [showOpts, setShowOpts] = useState(false);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    try {
      setReports(await api.reports({ limit: 8 }));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  }, [t, toast]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const todayReport = (reports || []).find((r) => r.report_date === today);
  const aiReady = !!config?.ai_config?.base_url;

  // 拉取今日晨报详情，首页直接展示完整正文（列表接口只含摘要）
  const [todayDetail, setTodayDetail] = useState(null);
  useEffect(() => {
    setTodayDetail(null);
    if (!todayReport?.id) return undefined;
    let cancelled = false;
    api
      .report(todayReport.id)
      .then((detail) => {
        if (!cancelled) setTodayDetail(detail);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [todayReport?.id]);

  const todayFull = useMemo(
    () => (todayReport && todayDetail ? { ...todayReport, ...todayDetail } : todayReport),
    [todayReport, todayDetail]
  );

  const generate = async () => {
    setBusy(true);
    try {
      const res = await api.generateReport(opts);
      toast.ok(t("dashboard.generated"), res.title);
      setShowOpts(false);
      await load();
      navigate(`/reports?id=${res.report_id}`);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy(false);
    }
  };

  const openPreview = async (id) => {
    try {
      setPreview(await api.report(id));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  return (
    <>
      <PageHead
        title={`${t("dashboard.greeting")}${me?.display_name ? `，${me.display_name}` : ""}`}
        subtitle={t("app.tagline")}
      >
        <button className="btn" onClick={() => setShowOpts(true)} disabled={busy}>
          {t("dashboard.options")}
        </button>
        <button className="btn btn-primary" onClick={generate} disabled={busy}>
          {busy && <span className="spinner" />}
          {busy ? t("dashboard.generating") : t("dashboard.generateNow")}
        </button>
      </PageHead>

      {!cfgLoading && !aiReady && (
        <AlertBar
          kind="warn"
          action={
            <button className="btn btn-sm" onClick={() => navigate("/settings")}>
              {t("dashboard.goConfigure")}
            </button>
          }
        >
          {t("dashboard.configureFirst")}
        </AlertBar>
      )}

      {busy && <AlertBar kind="info">{t("dashboard.generating")}</AlertBar>}

      {todayFull ? (
        <TodayReportCard
          report={todayFull}
          onPreview={openPreview}
          onOpen={(id) => navigate(`/reports?id=${id}`)}
        />
      ) : reports === null ? (
        <Card>
          <Loading />
        </Card>
      ) : (
        <Card>
          <Empty
            icon="☀"
            title={t("dashboard.noReportToday")}
            desc={t("dashboard.generating")}
            action={
              <button className="btn btn-primary" onClick={generate} disabled={busy}>
                {t("dashboard.generateNow")}
              </button>
            }
          />
        </Card>
      )}

      <Card
        title={t("dashboard.recentReports")}
        actions={
          <button className="btn btn-sm btn-ghost" onClick={() => navigate("/reports")}>
            {t("nav.reports")} →
          </button>
        }
      >
        {reports === null ? (
          <Loading />
        ) : reports.length === 0 ? (
          <Empty title={t("common.empty")} />
        ) : (
          reports.map((r) => (
            <RecentReportRow
              key={r.id}
              report={r}
              onPreview={openPreview}
              onOpen={(id) => navigate(`/reports?id=${id}`)}
            />
          ))
        )}
      </Card>

      {showOpts && (
        <Modal
          title={t("dashboard.options")}
          size="sm"
          onClose={() => setShowOpts(false)}
          footer={
            <>
              <button className="btn" onClick={() => setShowOpts(false)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" onClick={generate} disabled={busy}>
                {busy && <span className="spinner" />}
                {t("dashboard.generateNow")}
              </button>
            </>
          }
        >
          <div className="col">
            <Switch
              checked={opts.use_ai}
              onChange={(v) => setOpts({ ...opts, use_ai: v })}
              label={t("dashboard.optAi")}
            />
            <Switch
              checked={opts.push}
              onChange={(v) => setOpts({ ...opts, push: v })}
              label={t("dashboard.optPush")}
            />
            <Switch
              checked={opts.tracking}
              onChange={(v) => setOpts({ ...opts, tracking: v })}
              label={t("dashboard.optTracking")}
            />
            <Switch
              checked={opts.alerts}
              onChange={(v) => setOpts({ ...opts, alerts: v })}
              label={t("dashboard.optAlerts")}
            />
            <Switch
              checked={opts.tts}
              onChange={(v) => setOpts({ ...opts, tts: v })}
              label={t("dashboard.optTts")}
            />
          </div>
        </Modal>
      )}

      {preview && <PreviewModal report={preview} onClose={() => setPreview(null)} onOpen={(id) => {
        navigate(`/reports?id=${id}`);
        setPreview(null);
      }} />}
    </>
  );
}

/** 晨报预览弹窗：与详情页一致的翻译能力（整篇 Markdown 译文，保留排版）。 */
function PreviewModal({ report, onClose, onOpen }) {
  const { t } = useTranslation();
  const tr = useReportTranslate(report);

  return (
    <Modal
      title={tr.view("title") || report.title}
      size="lg"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.close")}
          </button>
          <button className="btn btn-primary" onClick={() => onOpen(report.id)}>
            {t("common.edit")}
          </button>
        </>
      }
    >
      {tr.needsTranslate && !tr.hasResult && !tr.loading && !tr.error && (
        <AlertBar kind="info" action={<TranslateButton tr={tr} primary />}>
          {t("translate.hint")}
        </AlertBar>
      )}
      <TranslateErrorBar tr={tr} />
      <Markdown>{tr.view("content_md") || report.content_md}</Markdown>
      {tr.hasResult && (
        <div className="row mt-14" style={{ gap: 8 }}>
          <TranslateButton tr={tr} primary />
          {tr.showingTranslated && <Tag kind="brand">{t("translate.tag")}</Tag>}
        </div>
      )}
    </Modal>
  );
}
