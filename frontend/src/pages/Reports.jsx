import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import api, { getToken } from "../api";
import Markdown from "../components/Markdown";
import { TranslateButton, TranslateErrorBar, useReportTranslate } from "../components/ReportTranslate";
import { useToast } from "../components/Toast";
import {
  AlertBar,
  Card,
  Empty,
  Field,
  Input,
  Loading,
  Modal,
  PageHead,
  Switch,
  Tag,
  useConfirm,
} from "../components/ui";
import { useMeta } from "../store";

const EXPORT_FORMATS = ["md", "html", "pdf", "image"];

/** 音频播放器：<audio> 无法携带 Authorization 头，这里用 fetch + blob 取回再播放。 */
function AudioAsset({ id }) {
  const [src, setSrc] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let url = "";
    fetch(`/api/reports/tts/audio/${id}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error("音频不可用"))))
      .then((b) => {
        url = URL.createObjectURL(b);
        setSrc(url);
      })
      .catch(() => setFailed(true));
    return () => url && URL.revokeObjectURL(url);
  }, [id]);

  if (failed) return <span className="text-3 fs-12">音频文件缺失</span>;
  if (!src) return <span className="spinner" />;
  return <audio controls preload="none" style={{ height: 34 }} src={src} />;
}

export default function Reports() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirm = useConfirm();
  const meta = useMeta();
  const [params, setParams] = useSearchParams();

  const [filters, setFilters] = useState({ q: "", date_from: "", date_to: "" });
  const [list, setList] = useState(null);
  const [current, setCurrent] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState(null);
  const [ttsAssets, setTtsAssets] = useState([]);
  const [ttsBusy, setTtsBusy] = useState(false);
  const [exporting, setExporting] = useState("");
  const [showPush, setShowPush] = useState(false);
  const [pushChannels, setPushChannels] = useState([]);
  const [showTts, setShowTts] = useState(false);
  const [ttsForm, setTtsForm] = useState({ provider: "", voice: "", fmt: "", push: false });
  const detailRef = useRef(null);
  const tr = useReportTranslate(current);

  const selectedId = Number(params.get("id") || 0);

  const loadList = useCallback(async () => {
    try {
      setList(await api.reports({ ...filters, limit: 60 }));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
      setList([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.q, filters.date_from, filters.date_to]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const openReport = useCallback(
    async (id) => {
      setLoadingDetail(true);
      setPushResult(null);
      try {
        const data = await api.report(id);
        setCurrent(data);
        const assets = await api.reportTts(id).catch(() => []);
        setTtsAssets(assets);
      } catch (e) {
        toast.err(t("common.failed"), e.message);
        setCurrent(null);
      } finally {
        setLoadingDetail(false);
      }
    },
    [t, toast]
  );

  useEffect(() => {
    if (selectedId) {
      openReport(selectedId);
      setTimeout(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    } else {
      setCurrent(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const select = (id) => {
    const next = new URLSearchParams(params);
    next.set("id", String(id));
    setParams(next);
  };

  const doExport = async (fmt) => {
    setExporting(fmt);
    try {
      await api.exportReport(current.id, fmt);
      toast.ok(t("common.success"), `report.${fmt === "image" ? "png" : fmt}`);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setExporting("");
    }
  };

  const doPush = async () => {
    setPushing(true);
    try {
      const res = await api.pushReport(current.id, pushChannels.length ? pushChannels : null);
      setPushResult(res);
      const okCount = (res.results || []).filter((r) => r.ok).length;
      if (res.ok) toast.ok(t("common.success"), `${okCount}/${(res.results || []).length}`);
      else toast.err(t("common.failed"), (res.results || []).map((r) => `${r.channel}: ${r.detail}`).join("\n"));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setPushing(false);
      setShowPush(false);
    }
  };

  const doTts = async () => {
    setTtsBusy(true);
    try {
      const res = await api.generateTts(current.id, ttsForm);
      toast.ok(t("common.success"), `${res.voice} · ${Math.round(res.duration_sec || 0)}s`);
      setTtsAssets(await api.reportTts(current.id).catch(() => []));
      setShowTts(false);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setTtsBusy(false);
    }
  };

  const remove = async (id) => {
    if (!(await confirm({ message: t("common.deleteConfirm"), danger: true, confirmText: t("common.delete") }))) return;
    try {
      await api.deleteReport(id);
      toast.ok(t("common.success"));
      if (selectedId === id) {
        const next = new URLSearchParams(params);
        next.delete("id");
        setParams(next);
      }
      loadList();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  return (
    <>
      <PageHead title={t("reports.title")} subtitle={t("reports.subtitle")} />

      <Card tight>
        <div className="inline-form">
          <Input
            placeholder={t("reports.searchPlaceholder")}
            value={filters.q}
            onChange={(v) => setFilters({ ...filters, q: v })}
          />
          <Field className="mb-0" label={t("reports.dateFrom")}>
            <Input
              type="date"
              value={filters.date_from}
              onChange={(v) => setFilters({ ...filters, date_from: v })}
            />
          </Field>
          <Field className="mb-0" label={t("reports.dateTo")}>
            <Input
              type="date"
              value={filters.date_to}
              onChange={(v) => setFilters({ ...filters, date_to: v })}
            />
          </Field>
          <button className="btn" onClick={loadList} style={{ marginTop: 22 }}>
            {t("common.search")}
          </button>
          <button
            className="btn btn-ghost"
            style={{ marginTop: 22 }}
            onClick={() => setFilters({ q: "", date_from: "", date_to: "" })}
          >
            {t("common.cancel")}
          </button>
        </div>
      </Card>

      {current && (
        <div ref={detailRef}>
          <Card
            title={tr.view("title") || current.title}
            subtitle={`${current.report_date} · ${t("reports.sourceCount", { count: (current.sources_used || []).length })}`}
            actions={
              <>
                <TranslateButton tr={tr} primary />
                <button className="btn btn-sm" onClick={() => setShowPush(true)} disabled={pushing}>
                  {pushing && <span className="spinner" />}
                  {t("reports.pushNow")}
                </button>
                <button className="btn btn-sm" onClick={() => setShowTts(true)}>
                  {ttsAssets.length ? t("reports.ttsRegenerate") : t("reports.ttsGenerate")}
                </button>
                {EXPORT_FORMATS.map((fmt) => (
                  <button
                    key={fmt}
                    className="btn btn-sm"
                    onClick={() => doExport(fmt)}
                    disabled={exporting === fmt}
                  >
                    {exporting === fmt && <span className="spinner" />}
                    {fmt === "image" ? t("reports.exportImage") : `导出 ${fmt.toUpperCase()}`}
                  </button>
                ))}
                <button className="btn btn-sm btn-danger" onClick={() => remove(current.id)}>
                  {t("common.delete")}
                </button>
              </>
            }
          >
            <div className="row mb-14">
              <Tag kind="accent">{current.template}</Tag>
              {current.industry && <Tag>{current.industry}</Tag>}
              {current.meta?.model && <Tag>{current.meta.model}</Tag>}
              {current.meta?.ai ? <Tag kind="ok">AI</Tag> : <Tag kind="warn">素材版</Tag>}
              {tr.showingTranslated && <Tag kind="brand">{t("translate.tag")}</Tag>}
              <button
                className="btn btn-sm btn-ghost"
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.delete("id");
                  setParams(next);
                }}
              >
                {t("common.close")}
              </button>
            </div>
            {tr.needsTranslate && !tr.hasResult && !tr.loading && !tr.error && (
              <AlertBar kind="info" action={<TranslateButton tr={tr} />}>
                {t("translate.hint")}
              </AlertBar>
            )}
            <TranslateErrorBar tr={tr} />
            <Markdown>{tr.view("content_md") || current.content_md}</Markdown>
          </Card>

          {ttsAssets.length > 0 && (
            <Card title={t("settings.tabTts")} tight>
              {ttsAssets.map((a) => (
                <div className="list-row" key={a.id}>
                  <div className="list-row-main">
                    <div className="list-row-title">
                      {a.voice} <Tag>{a.fmt}</Tag>
                    </div>
                    <div className="list-row-meta">
                      <span>{Math.round(a.duration_sec || 0)}s</span>
                      <span>{((a.size_bytes || 0) / 1024).toFixed(0)} KB</span>
                      <span>{a.created_at?.slice(0, 19).replace("T", " ")}</span>
                    </div>
                  </div>
                  <AudioAsset id={a.id} />
                </div>
              ))}
            </Card>
          )}

          {pushResult && (
            <AlertBar kind={pushResult.ok ? "ok" : "danger"} onClose={() => setPushResult(null)}>
              <b>{t("reports.pushResult")}</b>
              <div className="mt-8">
                {(pushResult.results || []).map((r) => (
                  <div key={r.channel} className="row" style={{ gap: 6 }}>
                    <span className={`dot ${r.ok ? "dot-ok" : "dot-err"}`} />
                    <b>{r.channel}</b>
                    <span className="text-3 fs-12">{r.detail || "OK"}</span>
                  </div>
                ))}
              </div>
            </AlertBar>
          )}
        </div>
      )}

      <Card title={t("reports.title")} subtitle={list ? t("common.total", { count: list.length }) : ""}>
        {list === null ? (
          <Loading />
        ) : loadingDetail ? (
          <Loading />
        ) : list.length === 0 ? (
          <Empty icon="▤" title={t("common.empty")} desc={t("reports.subtitle")} />
        ) : (
          list.map((r) => (
            <div className="list-row" key={r.id}>
              <div className="list-row-main">
                <div className="list-row-title">
                  <a
                    href={`/reports?id=${r.id}`}
                    onClick={(e) => {
                      e.preventDefault();
                      select(r.id);
                    }}
                  >
                    {r.title}
                  </a>
                </div>
                <div className="list-row-meta">
                  <span>{r.report_date}</span>
                  <Tag>{r.template}</Tag>
                  <span>{t("reports.sourceCount", { count: r.source_count })}</span>
                </div>
                <div className="list-row-text clamp-2">{r.excerpt}</div>
              </div>
              <div className="list-row-actions">
                <button className="btn btn-sm" onClick={() => select(r.id)}>
                  {t("common.preview")}
                </button>
                <button className="btn btn-sm btn-danger" onClick={() => remove(r.id)}>
                  {t("common.delete")}
                </button>
              </div>
            </div>
          ))
        )}
      </Card>

      {showPush && current && (
        <Modal
          title={t("reports.pushNow")}
          size="sm"
          onClose={() => setShowPush(false)}
          footer={
            <>
              <button className="btn" onClick={() => setShowPush(false)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" onClick={doPush} disabled={pushing}>
                {pushing && <span className="spinner" />}
                {t("common.push")}
              </button>
            </>
          }
        >
          <AlertBar kind="info">{t("alerts.channelsHint")}</AlertBar>
          <div className="opt-grid">
            {(meta?.channels || []).map((c) => (
              <label className={`opt${pushChannels.includes(c.id) ? " on" : ""}`} key={c.id}>
                <input
                  type="checkbox"
                  checked={pushChannels.includes(c.id)}
                  onChange={(e) =>
                    setPushChannels((prev) =>
                      e.target.checked ? [...prev, c.id] : prev.filter((x) => x !== c.id)
                    )
                  }
                />
                <span className="opt-body">
                  <span className="opt-name">{c.name}</span>
                </span>
              </label>
            ))}
          </div>
        </Modal>
      )}

      {showTts && current && (
        <Modal
          title={t("reports.ttsGenerate")}
          size="sm"
          onClose={() => setShowTts(false)}
          footer={
            <>
              <button className="btn" onClick={() => setShowTts(false)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" onClick={doTts} disabled={ttsBusy}>
                {ttsBusy && <span className="spinner" />}
                {t("common.generate")}
              </button>
            </>
          }
        >
          <Field label={t("settings.ttsProvider")} hint="留空则使用「设置 → 语音晨报」中的默认值">
            <Input value={ttsForm.provider} onChange={(v) => setTtsForm({ ...ttsForm, provider: v })} />
          </Field>
          <Field label={t("settings.ttsVoice")}>
            <Input value={ttsForm.voice} onChange={(v) => setTtsForm({ ...ttsForm, voice: v })} />
          </Field>
          <Field label={t("settings.ttsFormat")}>
            <Input value={ttsForm.fmt} onChange={(v) => setTtsForm({ ...ttsForm, fmt: v })} />
          </Field>
          <Switch
            checked={ttsForm.push}
            onChange={(v) => setTtsForm({ ...ttsForm, push: v })}
            label={t("settings.ttsPush")}
          />
        </Modal>
      )}
    </>
  );
}
