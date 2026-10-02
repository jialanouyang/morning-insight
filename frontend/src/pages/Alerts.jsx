import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import api from "../api";
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
  Select,
  Stat,
  Switch,
  Tag,
  useConfirm,
} from "../components/ui";
import { useMeta } from "../store";

const EMPTY = {
  keyword: "",
  match_type: "exact",
  condition: "always",
  condition_value: 1,
  channels: [],
  cooldown_minutes: 180,
  enabled: true,
};

export default function Alerts() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirm = useConfirm();
  const meta = useMeta();

  const [rules, setRules] = useState(null);
  const [history, setHistory] = useState(null);
  const [view, setView] = useState("rules");
  const [form, setForm] = useState(null);
  const [editing, setEditing] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, h] = await Promise.all([api.alerts(), api.alertHistory(100)]);
      setRules(r);
      setHistory(h);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
      setRules([]);
      setHistory([]);
    }
  }, [t, toast]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async () => {
    if (!form.keyword.trim()) {
      toast.err(t("common.failed"), t("alerts.keywordPlaceholder"));
      return;
    }
    setBusy(true);
    try {
      if (editing) await api.updateAlert(editing, form);
      else await api.createAlert(form);
      toast.ok(t("common.saved"));
      setForm(null);
      setEditing(null);
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (rule) => {
    if (!(await confirm({ message: `${t("common.deleteConfirm")}\n${rule.keyword}`, danger: true, confirmText: t("common.delete") }))) return;
    try {
      await api.deleteAlert(rule.id);
      toast.ok(t("common.success"));
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const scan = async () => {
    setScanning(true);
    try {
      const res = await api.scanAlerts(200, true);
      toast.ok(t("alerts.fired", { count: res.fired?.length ?? 0 }));
      await load();
      setView("history");
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setScanning(false);
    }
  };

  const condLabel = (c) =>
    ({
      always: t("alerts.condAlways"),
      frequency: t("alerts.condFrequency"),
      source: t("alerts.condSource"),
    })[c] || c;

  const pushedCount = (history || []).filter((h) => h.pushed).length;

  return (
    <>
      <PageHead title={t("alerts.title")} subtitle={t("alerts.subtitle")}>
        <Seg
          value={view}
          onChange={setView}
          items={[
            { value: "rules", label: `${t("alerts.title")} (${rules?.length ?? 0})` },
            { value: "history", label: t("alerts.history") },
          ]}
        />
        <button className="btn" onClick={scan} disabled={scanning}>
          {scanning && <span className="spinner" />}
          {scanning ? t("competitors.scanning") : t("alerts.scan")}
        </button>
        <button
          className="btn btn-primary"
          onClick={() => {
            setEditing(null);
            setForm({ ...EMPTY });
          }}
        >
          {t("alerts.addRule")}
        </button>
      </PageHead>

      <div className="grid grid-3 mb-14">
        <Stat label={t("alerts.addRule")} value={rules?.length ?? "—"} />
        <Stat label={t("alerts.history")} value={history?.length ?? "—"} />
        <Stat label={t("alerts.pushed")} value={pushedCount} accent />
      </div>

      {view === "rules" ? (
        rules === null ? (
          <Loading />
        ) : rules.length === 0 ? (
          <Card>
            <Empty
              icon="⚑"
              title={t("alerts.addRule")}
              desc={t("alerts.subtitle")}
              action={
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setEditing(null);
                    setForm({ ...EMPTY });
                  }}
                >
                  {t("alerts.addRule")}
                </button>
              }
            />
          </Card>
        ) : (
          <Card>
            {rules.map((r) => (
              <div className="list-row" key={r.id}>
                <div className="list-row-main">
                  <div className="list-row-title">
                    {r.keyword}{" "}
                    <Tag kind={r.match_type === "exact" ? "accent" : ""}>
                      {r.match_type === "exact" ? t("alerts.matchExact") : t("alerts.matchFuzzy")}
                    </Tag>
                    {!r.enabled && <Tag kind="danger">{t("common.disabled")}</Tag>}
                  </div>
                  <div className="list-row-meta">
                    <span>{condLabel(r.condition)}</span>
                    {r.condition === "frequency" && <span>≥ {r.condition_value}</span>}
                    <span>
                      {t("alerts.cooldown")}: {r.cooldown_minutes}
                    </span>
                    <span>
                      {t("common.channels")}:{" "}
                      {r.channels?.length
                        ? r.channels
                            .map((c) => (meta?.channels || []).find((x) => x.id === c)?.name || c)
                            .join(", ")
                        : t("common.all")}
                    </span>
                  </div>
                  {r.last_fired_at && (
                    <div className="list-row-text fs-12">
                      {t("common.time")}: {r.last_fired_at.slice(0, 19).replace("T", " ")}
                    </div>
                  )}
                </div>
                <div className="list-row-actions">
                  <button
                    className="btn btn-sm"
                    onClick={() => {
                      setEditing(r.id);
                      setForm({
                        keyword: r.keyword,
                        match_type: r.match_type,
                        condition: r.condition,
                        condition_value: r.condition_value,
                        channels: r.channels || [],
                        cooldown_minutes: r.cooldown_minutes,
                        enabled: r.enabled,
                      });
                    }}
                  >
                    {t("common.edit")}
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => remove(r)}>
                    {t("common.delete")}
                  </button>
                </div>
              </div>
            ))}
          </Card>
        )
      ) : history === null ? (
        <Loading />
      ) : history.length === 0 ? (
        <Card>
          <Empty icon="⚑" title={t("alerts.noHistory")} desc={t("alerts.scan")} />
        </Card>
      ) : (
        <Card>
          {history.map((h) => (
            <div className="list-row" key={h.id}>
              <div className="list-row-main">
                <div className="list-row-title">
                  <Tag kind="brand">{h.keyword}</Tag> {h.title}
                </div>
                <div className="list-row-meta">
                  <Tag kind={h.pushed ? "ok" : "warn"}>
                    {h.pushed ? t("alerts.pushed") : t("alerts.notPushed")}
                  </Tag>
                  <span>{h.pushed_at?.slice(0, 19).replace("T", " ")}</span>
                  {h.detail && <span>{h.detail}</span>}
                </div>
              </div>
              {h.url && (
                <a className="btn btn-sm" href={h.url} target="_blank" rel="noreferrer">
                  {t("competitors.viewSource")}
                </a>
              )}
            </div>
          ))}
        </Card>
      )}

      {form && (
        <Modal
          title={editing ? t("common.edit") : t("alerts.addRule")}
          onClose={() => setForm(null)}
          footer={
            <>
              <button className="btn" onClick={() => setForm(null)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" onClick={submit} disabled={busy}>
                {busy && <span className="spinner" />}
                {t("common.save")}
              </button>
            </>
          }
        >
          <Field label={t("common.keyword")} required>
            <Input
              placeholder={t("alerts.keywordPlaceholder")}
              value={form.keyword}
              onChange={(v) => setForm({ ...form, keyword: v })}
            />
          </Field>
          <div className="grid grid-2">
            <Field label={t("common.type")}>
              <Select
                value={form.match_type}
                onChange={(v) => setForm({ ...form, match_type: v })}
                options={[
                  { value: "exact", label: t("alerts.matchExact") },
                  { value: "fuzzy", label: t("alerts.matchFuzzy") },
                ]}
              />
            </Field>
            <Field label={t("alerts.cooldown")}>
              <Input
                type="number"
                min={0}
                value={form.cooldown_minutes}
                onChange={(v) => setForm({ ...form, cooldown_minutes: Number(v) || 0 })}
              />
            </Field>
          </div>
          <div className="grid grid-2">
            <Field label={t("common.status")}>
              <Select
                value={form.condition}
                onChange={(v) => setForm({ ...form, condition: v })}
                options={[
                  { value: "always", label: t("alerts.condAlways") },
                  { value: "frequency", label: t("alerts.condFrequency") },
                  { value: "source", label: t("alerts.condSource") },
                ]}
              />
            </Field>
            {form.condition === "frequency" && (
              <Field label={t("alerts.conditionValue")}>
                <Input
                  type="number"
                  min={1}
                  value={form.condition_value}
                  onChange={(v) => setForm({ ...form, condition_value: Number(v) || 1 })}
                />
              </Field>
            )}
          </div>
          <Field label={t("common.channels")} hint={t("alerts.channelsHint")}>
            <div className="opt-grid">
              {(meta?.channels || []).map((c) => (
                <label className={`opt${form.channels.includes(c.id) ? " on" : ""}`} key={c.id}>
                  <input
                    type="checkbox"
                    checked={form.channels.includes(c.id)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        channels: e.target.checked
                          ? [...form.channels, c.id]
                          : form.channels.filter((x) => x !== c.id),
                      })
                    }
                  />
                  <span className="opt-body">
                    <span className="opt-name">{c.name}</span>
                  </span>
                </label>
              ))}
            </div>
          </Field>
          <Switch
            checked={form.enabled}
            onChange={(v) => setForm({ ...form, enabled: v })}
            label={t("common.enabled")}
          />
        </Modal>
      )}

      {rules?.length > 0 && history?.length === 0 && (
        <AlertBar kind="info">{t("alerts.scan")}</AlertBar>
      )}
    </>
  );
}
