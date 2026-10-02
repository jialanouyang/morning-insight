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
  TagInput,
  Textarea,
  useConfirm,
} from "../components/ui";

const EVENT_KEYS = {
  news: "新闻",
  announcement: "公告",
  funding: "融资",
  product: "产品更新",
  executive: "高管变动",
  other: "其它",
};

const EMPTY_FORM = { name: "", type: "company", keywords: [], level: "normal", notes: "", enabled: true };

export default function Competitors() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirm = useConfirm();

  const [items, setItems] = useState(null);
  const [compare, setCompare] = useState([]);
  const [view, setView] = useState("list");
  const [form, setForm] = useState(null);
  const [editing, setEditing] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [timelineFor, setTimelineFor] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [list, cmp] = await Promise.all([api.competitors(), api.compareCompetitors(30)]);
      setItems(list);
      setCompare(cmp);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
      setItems([]);
    }
  }, [t, toast]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
  };

  const openEdit = (item) => {
    setEditing(item.id);
    setForm({
      name: item.name,
      type: item.type,
      keywords: item.keywords || [],
      level: item.level,
      notes: item.notes || "",
      enabled: item.enabled,
    });
  };

  const submit = async () => {
    if (!form.name.trim()) {
      toast.err(t("common.failed"), t("competitors.namePlaceholder"));
      return;
    }
    setBusy(true);
    try {
      if (editing) await api.updateCompetitor(editing, form);
      else await api.createCompetitor(form);
      toast.ok(t("common.saved"));
      setForm(null);
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (item) => {
    if (!(await confirm({ message: `${t("common.deleteConfirm")}\n${item.name}`, danger: true, confirmText: t("common.delete") }))) return;
    try {
      await api.deleteCompetitor(item.id);
      toast.ok(t("common.success"));
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const showTimeline = async (item) => {
    setTimelineFor(item);
    setTimeline(null);
    try {
      setTimeline(await api.competitorTimeline(item.id, 200));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
      setTimeline([]);
    }
  };

  const scan = async () => {
    setScanning(true);
    try {
      const res = await api.scanCompetitors(200, true);
      toast.ok(t("common.success"), `${t("competitors.events")}: ${res.events}`);
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setScanning(false);
    }
  };

  const totalEvents = compare.reduce((s, c) => s + (c.event_count || 0), 0);
  const totalHighlights = compare.reduce((s, c) => s + (c.highlight_count || 0), 0);

  return (
    <>
      <PageHead title={t("competitors.title")} subtitle={t("competitors.subtitle")}>
        <Seg
          value={view}
          onChange={setView}
          items={[
            { value: "list", label: t("competitors.title") },
            { value: "compare", label: t("competitors.compare") },
          ]}
        />
        <button className="btn" onClick={scan} disabled={scanning}>
          {scanning && <span className="spinner" />}
          {scanning ? t("competitors.scanning") : t("competitors.scan")}
        </button>
        <button className="btn btn-primary" onClick={openCreate}>
          {t("competitors.addObject")}
        </button>
      </PageHead>

      <div className="grid grid-3 mb-14">
        <Stat label={t("competitors.addObject")} value={items?.length ?? "—"} />
        <Stat label={t("competitors.events")} value={totalEvents} />
        <Stat label={t("competitors.highlights")} value={totalHighlights} accent />
      </div>

      {items === null ? (
        <Loading />
      ) : items.length === 0 ? (
        <Card>
          <Empty
            icon="◎"
            title={t("competitors.addObject")}
            desc={t("competitors.subtitle")}
            action={
              <button className="btn btn-primary" onClick={openCreate}>
                {t("competitors.addObject")}
              </button>
            }
          />
        </Card>
      ) : view === "list" ? (
        <Card>
          {items.map((item) => (
            <div className="list-row" key={item.id}>
              <div className="list-row-main">
                <div className="list-row-title">
                  {item.name}{" "}
                  {item.level === "high" && <Tag kind="brand">{t("competitors.levelHigh")}</Tag>}
                  {item.level === "normal" && <Tag>{t("competitors.levelNormal")}</Tag>}
                  {!item.enabled && <Tag kind="danger">{t("common.disabled")}</Tag>}
                </div>
                <div className="list-row-meta">
                  <span>
                    {item.type === "product" ? t("competitors.typeProduct") : t("competitors.typeCompany")}
                  </span>
                  {item.keywords?.length > 0 && <span>{item.keywords.join(" / ")}</span>}
                  <span>
                    {t("competitors.lastSeen")}: {item.last_seen_at || t("common.never")}
                  </span>
                </div>
                {item.notes && <div className="list-row-text">{item.notes}</div>}
              </div>
              <div className="list-row-actions">
                <button className="btn btn-sm" onClick={() => showTimeline(item)}>
                  {t("competitors.timeline")}
                </button>
                <button className="btn btn-sm" onClick={() => openEdit(item)}>
                  {t("common.edit")}
                </button>
                <button className="btn btn-sm btn-danger" onClick={() => remove(item)}>
                  {t("common.delete")}
                </button>
              </div>
            </div>
          ))}
        </Card>
      ) : (
        <Card title={t("competitors.compare")} subtitle="近 30 天">
          {compare.length === 0 ? (
            <Empty title={t("competitors.noEvents")} />
          ) : (
            <div className="grid grid-auto">
              {compare.map((c) => (
                <div className="card card-tight mb-0" key={c.id}>
                  <div className="row-between">
                    <b>{c.name}</b>
                    <Tag kind={c.level === "high" ? "brand" : ""}>
                      {c.level === "high" ? t("competitors.levelHigh") : t("competitors.levelNormal")}
                    </Tag>
                  </div>
                  <div className="row mt-8" style={{ gap: 6 }}>
                    <Tag kind="accent">
                      {t("competitors.events")} {c.event_count}
                    </Tag>
                    {c.highlight_count > 0 && (
                      <Tag kind="warn">
                        {t("competitors.highlight")} {c.highlight_count}
                      </Tag>
                    )}
                  </div>
                  {Object.keys(c.by_type || {}).length > 0 && (
                    <div className="row mt-8" style={{ gap: 4 }}>
                      {Object.entries(c.by_type).map(([k, v]) => (
                        <Tag key={k}>
                          {EVENT_KEYS[k] || k} {v}
                        </Tag>
                      ))}
                    </div>
                  )}
                  {c.latest?.length > 0 && (
                    <div className="mt-8">
                      {c.latest.map((e, i) => (
                        <div className="fs-12 text-2" key={i}>
                          {e.is_highlight && <Tag kind="warn">{t("competitors.highlight")}</Tag>}{" "}
                          {e.title}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {form && (
        <Modal
          title={editing ? t("common.edit") : t("competitors.addObject")}
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
          <Field label={t("common.name")} required>
            <Input
              placeholder={t("competitors.namePlaceholder")}
              value={form.name}
              onChange={(v) => setForm({ ...form, name: v })}
            />
          </Field>
          <div className="grid grid-2">
            <Field label={t("common.type")}>
              <Select
                value={form.type}
                onChange={(v) => setForm({ ...form, type: v })}
                options={[
                  { value: "company", label: t("competitors.typeCompany") },
                  { value: "product", label: t("competitors.typeProduct") },
                ]}
              />
            </Field>
            <Field label={t("common.level")}>
              <Select
                value={form.level}
                onChange={(v) => setForm({ ...form, level: v })}
                options={[
                  { value: "high", label: t("competitors.levelHigh") },
                  { value: "normal", label: t("competitors.levelNormal") },
                ]}
              />
            </Field>
          </div>
          <Field label={t("common.keyword")} hint={t("common.listHint")}>
            <TagInput
              value={form.keywords}
              onChange={(v) => setForm({ ...form, keywords: v })}
              placeholder={t("competitors.keywordsPlaceholder")}
            />
          </Field>
          <Field label={t("common.notes")}>
            <Textarea value={form.notes} onChange={(v) => setForm({ ...form, notes: v })} />
          </Field>
          <Switch
            checked={form.enabled}
            onChange={(v) => setForm({ ...form, enabled: v })}
            label={t("common.enabled")}
          />
        </Modal>
      )}

      {timelineFor && (
        <Modal
          title={`${timelineFor.name} · ${t("competitors.timeline")}`}
          size="lg"
          onClose={() => {
            setTimelineFor(null);
            setTimeline(null);
          }}
        >
          {timeline === null ? (
            <Loading />
          ) : timeline.length === 0 ? (
            <Empty title={t("competitors.noEvents")} desc={t("competitors.scan")} />
          ) : (
            timeline.map((e) => (
              <div className="list-row" key={e.id}>
                <div className="list-row-main">
                  <div className="list-row-title">
                    {e.title}{" "}
                    {e.is_highlight && <Tag kind="warn">{t("competitors.highlight")}</Tag>}
                  </div>
                  <div className="list-row-meta">
                    <Tag kind="accent">{EVENT_KEYS[e.event_type] || e.event_type}</Tag>
                    <span>{e.event_date}</span>
                    {e.source && <span>{e.source}</span>}
                  </div>
                </div>
                {e.url && (
                  <a className="btn btn-sm" href={e.url} target="_blank" rel="noreferrer">
                    {t("competitors.viewSource")}
                  </a>
                )}
              </div>
            ))
          )}
        </Modal>
      )}

      {totalEvents === 0 && items?.length > 0 && (
        <AlertBar kind="info">{t("competitors.scan")}</AlertBar>
      )}
    </>
  );
}
