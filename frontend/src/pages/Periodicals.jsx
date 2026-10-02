import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import api from "../api";
import Markdown from "../components/Markdown";
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
  Seg,
  Tag,
  useConfirm,
} from "../components/ui";

const FORMATS = ["md", "html", "pdf"];

export default function Periodicals() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirm = useConfirm();

  const [filter, setFilter] = useState("");
  const [items, setItems] = useState(null);
  const [current, setCurrent] = useState(null);
  const [generating, setGenerating] = useState("");
  const [showGen, setShowGen] = useState(null);
  const [range, setRange] = useState({ start: "", end: "" });
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await api.periodicals({ period_type: filter, limit: 40 }));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
      setItems([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const open = async (id) => {
    setPushResult(null);
    try {
      setCurrent(await api.periodical(id));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const generate = async (type) => {
    setGenerating(type);
    try {
      const res = await api.generatePeriodical({
        period_type: type,
        start: range.start,
        end: range.end,
        push: false,
      });
      toast.ok(t("common.success"), res.title);
      setShowGen(null);
      setRange({ start: "", end: "" });
      await load();
      open(res.id);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setGenerating("");
    }
  };

  const push = async () => {
    setPushing(true);
    try {
      const res = await api.pushPeriodical(current.id);
      setPushResult(res);
      if (res.ok) toast.ok(t("common.success"));
      else toast.err(t("common.failed"), (res.results || []).map((r) => `${r.channel}: ${r.detail}`).join("\n"));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setPushing(false);
    }
  };

  const doExport = async (fmt) => {
    setBusy(true);
    try {
      await api.exportPeriodical(current.id, fmt);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (item) => {
    if (!(await confirm({ message: t("common.deleteConfirm"), danger: true, confirmText: t("common.delete") }))) return;
    try {
      await api.deletePeriodical(item.id);
      if (current?.id === item.id) setCurrent(null);
      toast.ok(t("common.success"));
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  return (
    <>
      <PageHead title={t("periodicals.title")} subtitle={t("periodicals.subtitle")}>
        <Seg
          value={filter}
          onChange={setFilter}
          items={[
            { value: "", label: t("common.all") },
            { value: "weekly", label: t("periodicals.periodWeekly") },
            { value: "monthly", label: t("periodicals.periodMonthly") },
          ]}
        />
        <button className="btn" onClick={() => setShowGen("weekly")} disabled={!!generating}>
          {generating === "weekly" && <span className="spinner" />}
          {t("periodicals.generateWeekly")}
        </button>
        <button className="btn btn-primary" onClick={() => setShowGen("monthly")} disabled={!!generating}>
          {generating === "monthly" && <span className="spinner" />}
          {t("periodicals.generateMonthly")}
        </button>
      </PageHead>

      {current && (
        <Card
          title={current.title}
          subtitle={`${current.period_start} ~ ${current.period_end}`}
          actions={
            <>
              <button className="btn btn-sm" onClick={push} disabled={pushing}>
                {pushing && <span className="spinner" />}
                {t("common.push")}
              </button>
              {FORMATS.map((f) => (
                <button key={f} className="btn btn-sm" onClick={() => doExport(f)} disabled={busy}>
                  {f.toUpperCase()}
                </button>
              ))}
              <button className="btn btn-sm btn-danger" onClick={() => remove(current)}>
                {t("common.delete")}
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => setCurrent(null)}>
                {t("common.close")}
              </button>
            </>
          }
        >
          {current.stats?.reports !== undefined && (
            <div className="row mb-14">
              <Tag kind="accent">
                {t("periodicals.reports")} {current.stats.reports}
              </Tag>
              <Tag kind="brand">
                {t("periodicals.articles")} {current.stats.articles ?? "—"}
              </Tag>
              {current.stats?.days && <Tag>{current.stats.days} 天</Tag>}
            </div>
          )}
          <Markdown>{current.content_md}</Markdown>
        </Card>
      )}

      {pushResult && (
        <AlertBar kind={pushResult.ok ? "ok" : "danger"} onClose={() => setPushResult(null)}>
          {(pushResult.results || []).map((r) => (
            <div key={r.channel} className="row" style={{ gap: 6 }}>
              <span className={`dot ${r.ok ? "dot-ok" : "dot-err"}`} />
              <b>{r.channel}</b>
              <span className="text-3 fs-12">{r.detail || "OK"}</span>
            </div>
          ))}
        </AlertBar>
      )}

      <Card title={t("periodicals.title")}>
        {items === null ? (
          <Loading />
        ) : items.length === 0 ? (
          <Empty
            icon="◷"
            title={t("periodicals.empty")}
            desc={t("periodicals.subtitle")}
            action={
              <button className="btn btn-primary" onClick={() => setShowGen("weekly")}>
                {t("periodicals.generateWeekly")}
              </button>
            }
          />
        ) : (
          items.map((item) => (
            <div className="list-row" key={item.id}>
              <div className="list-row-main">
                <div className="list-row-title">
                  <a
                    href={`/periodicals?id=${item.id}`}
                    onClick={(e) => {
                      e.preventDefault();
                      open(item.id);
                    }}
                  >
                    {item.title}
                  </a>
                </div>
                <div className="list-row-meta">
                  <Tag kind={item.period_type === "monthly" ? "brand" : "accent"}>
                    {item.period_type === "monthly"
                      ? t("periodicals.periodMonthly")
                      : t("periodicals.periodWeekly")}
                  </Tag>
                  <span>
                    {item.period_start} ~ {item.period_end}
                  </span>
                  {item.stats?.reports !== undefined && (
                    <span>
                      {t("periodicals.reports")} {item.stats.reports}
                    </span>
                  )}
                </div>
              </div>
              <div className="list-row-actions">
                <button className="btn btn-sm" onClick={() => open(item.id)}>
                  {t("common.preview")}
                </button>
                <button className="btn btn-sm btn-danger" onClick={() => remove(item)}>
                  {t("common.delete")}
                </button>
              </div>
            </div>
          ))
        )}
      </Card>

      {showGen && (
        <Modal
          title={showGen === "weekly" ? t("periodicals.generateWeekly") : t("periodicals.generateMonthly")}
          size="sm"
          onClose={() => setShowGen(null)}
          footer={
            <>
              <button className="btn" onClick={() => setShowGen(null)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" onClick={() => generate(showGen)} disabled={!!generating}>
                {generating && <span className="spinner" />}
                {t("common.generate")}
              </button>
            </>
          }
        >
          <AlertBar kind="info">{t("periodicals.subtitle")}</AlertBar>
          <div className="grid grid-2">
            <Field label={t("reports.dateFrom")} tip={t("common.optional")}>
              <Input type="date" value={range.start} onChange={(v) => setRange({ ...range, start: v })} />
            </Field>
            <Field label={t("reports.dateTo")} tip={t("common.optional")}>
              <Input type="date" value={range.end} onChange={(v) => setRange({ ...range, end: v })} />
            </Field>
          </div>
          <div className="field-hint">留空 = 自动取上一个完整周期</div>
        </Modal>
      )}

      {generating && <div className="alert-bar alert-info">{t("periodicals.generating")}</div>}
    </>
  );
}
