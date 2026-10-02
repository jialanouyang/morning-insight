import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import api, { getToken } from "../api";
import { useToast } from "../components/Toast";
import {
  Accordion,
  AlertBar,
  Card,
  Empty,
  Field,
  Input,
  Loading,
  Modal,
  OptionCard,
  PageHead,
  Seg,
  Select,
  Stat,
  Switch,
  Tabs,
  Tag,
  TagInput,
  Textarea,
} from "../components/ui";
import { LANGUAGES, setLanguage } from "../i18n";
import { useConfig, useMeta } from "../store";

const clone = (v) => (v === undefined || v === null ? v : JSON.parse(JSON.stringify(v)));

/* ---------------------------------------------------------------- 通用小件 */

function SaveBar({ dirty, busy, onSave, onReset, hint }) {
  const { t } = useTranslation();
  return (
    <div className="row-between mt-14">
      <span className="field-hint mb-0">{hint}</span>
      <div className="row">
        {onReset && (
          <button className="btn btn-ghost" onClick={onReset}>
            {t("settings.resetFocus")}
          </button>
        )}
        <button className="btn btn-primary" onClick={onSave} disabled={busy || !dirty}>
          {busy && <span className="spinner" />}
          {dirty ? t("common.save") : t("common.saved")}
        </button>
      </div>
    </div>
  );
}

/* ================================================================= 行业 */
function IndustryTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const toast = useToast();
  const [generating, setGenerating] = useState(false);

  const industries = draft.industries || [];
  const toggle = (name) =>
    patch({ industries: industries.includes(name) ? industries.filter((x) => x !== name) : [...industries, name] });

  const makeSources = async () => {
    const kws = [...(draft.keywords || []), ...(draft.industries || [])];
    if (!kws.length) {
      toast.err(t("common.failed"), t("settings.keywordsHint"));
      return;
    }
    setGenerating(true);
    try {
      const res = await api.sourcesFromKeywords(kws, "zh");
      toast.ok(t("common.success"), `${res.added?.length ?? 0} · ${res.note || ""}`);
      window.location.reload();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Card title={t("settings.tabIndustry")} subtitle={t("settings.industryHint")}>
      <Field label={t("settings.tabIndustry")}>
        <div className="opt-grid">
          {(meta?.industries || []).map((name) => (
            <OptionCard
              key={name}
              name={name}
              checked={industries.includes(name)}
              onChange={() => toggle(name)}
            />
          ))}
        </div>
      </Field>

      <Field label={t("settings.industryCustom")} hint={t("common.listHint")}>
        <TagInput
          value={industries.filter((x) => !(meta?.industries || []).includes(x))}
          onChange={(custom) => patch({ industries: [...(meta?.industries || []).filter((n) => industries.includes(n)), ...custom] })}
          placeholder={t("common.inputPlaceholder")}
        />
      </Field>

      <Field label={t("common.keyword")} hint={t("settings.keywordsHint")}>
        <TagInput
          value={draft.keywords || []}
          onChange={(v) => patch({ keywords: v })}
          placeholder={t("common.inputPlaceholder")}
        />
      </Field>

      <SaveBar
        dirty={true}
        busy={busy === "industry"}
        onSave={() => doSave({ industries: draft.industries || [], keywords: draft.keywords || [] })}
        hint={`${t("settings.tabSources")}: ${(draft.sources || []).length}`}
      />
      <div className="row mt-14">
        <button className="btn" onClick={makeSources} disabled={generating}>
          {generating && <span className="spinner" />}
          {t("settings.createKeywordSources")}
        </button>
      </div>
    </Card>
  );
}

/* ================================================================= 关注点 */
function FocusTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const points = draft.focus_points || [];

  const update = (idx, key, value) => {
    const next = clone(points);
    next[idx][key] = value;
    patch({ focus_points: next });
  };

  const addCustom = () => {
    const next = clone(points);
    next.push({
      id: `custom_${Date.now()}`,
      name: "",
      description: "",
      ai_hint: "",
      builtin: false,
      enabled: true,
    });
    patch({ focus_points: next });
  };

  const remove = (idx) => patch({ focus_points: points.filter((_, i) => i !== idx) });

  return (
    <Card
      title={t("settings.tabFocus")}
      subtitle={t("settings.focusHint")}
      actions={
        <button className="btn btn-sm" onClick={addCustom}>
          {t("settings.focusAddCustom")}
        </button>
      }
    >
      {points.length === 0 ? (
        <Empty title={t("common.empty")} />
      ) : (
        points.map((p, i) => (
          <Accordion
            key={p.id || i}
            defaultOpen={false}
            title={
              <span className="row" style={{ gap: 8 }}>
                <span>{p.name || t("settings.focusName")}</span>
                <Tag kind={p.builtin ? "" : "accent"}>
                  {p.builtin ? t("settings.focusBuiltin") : t("settings.focusCustom")}
                </Tag>
                {p.enabled ? <Tag kind="ok">{t("common.enabled")}</Tag> : <Tag>{t("common.disabled")}</Tag>}
              </span>
            }
            extra={
              <Switch
                checked={!!p.enabled}
                onChange={(v) => {
                  update(i, "enabled", v);
                }}
              />
            }
          >
            <div className="grid grid-2">
              <Field label={t("settings.focusName")}>
                <Input value={p.name} onChange={(v) => update(i, "name", v)} />
              </Field>
              <Field label={t("common.level")}>
                <Input value={p.ai_hint || ""} onChange={(v) => update(i, "ai_hint", v)} placeholder={t("settings.focusAiHint")} />
              </Field>
            </div>
            <Field label={t("settings.focusDesc")}>
              <Textarea value={p.description} onChange={(v) => update(i, "description", v)} />
            </Field>
            <div className="row">
              <div className="spacer" />
              <button className="btn btn-sm btn-danger" onClick={() => remove(i)}>
                {t("common.delete")}
              </button>
            </div>
          </Accordion>
        ))
      )}
      <SaveBar
        dirty={true}
        busy={busy === "focus"}
        onSave={() => doSave({ focus_points: draft.focus_points || [] })}
        hint={`${points.filter((p) => p.enabled).length} / ${points.length}`}
        onReset={async () => {
          await api.resetConfig("focus_points");
          window.location.reload();
        }}
      />
    </Card>
  );
}

/* ================================================================= 角色 */
function RolesTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const roles = draft.roles || [];

  const update = (idx, key, value) => {
    const next = clone(roles);
    next[idx][key] = value;
    patch({ roles: next });
  };

  return (
    <Card
      title={t("settings.tabRoles")}
      subtitle={t("settings.rolesHint")}
      actions={
        <button
          className="btn btn-sm"
          onClick={() =>
            patch({
              roles: [
                ...clone(roles),
                { id: `custom_${Date.now()}`, name: "", description: "", system_prompt: "", builtin: false, enabled: true },
              ],
            })
          }
        >
          {t("settings.roleAddCustom")}
        </button>
      }
    >
      {roles.map((r, i) => (
        <Accordion
          key={r.id || i}
          title={
            <span className="row" style={{ gap: 8 }}>
              <span>{r.name || t("settings.roleName")}</span>
              <Tag kind={r.builtin ? "" : "accent"}>
                {r.builtin ? t("settings.focusBuiltin") : t("settings.focusCustom")}
              </Tag>
              {r.enabled && <Tag kind="ok">{t("common.enabled")}</Tag>}
            </span>
          }
          extra={<Switch checked={!!r.enabled} onChange={(v) => update(i, "enabled", v)} />}
        >
          <div className="grid grid-2">
            <Field label={t("settings.roleName")}>
              <Input value={r.name} onChange={(v) => update(i, "name", v)} />
            </Field>
            <Field label={t("settings.roleDesc")}>
              <Input value={r.description || ""} onChange={(v) => update(i, "description", v)} />
            </Field>
          </div>
          <Field label={t("settings.rolePrompt")}>
            <Textarea className="textarea-lg" value={r.system_prompt || ""} onChange={(v) => update(i, "system_prompt", v)} />
          </Field>
          <div className="row">
            <div className="spacer" />
            <button className="btn btn-sm btn-danger" onClick={() => patch({ roles: roles.filter((_, x) => x !== i) })}>
              {t("common.delete")}
            </button>
          </div>
        </Accordion>
      ))}
      <SaveBar
        dirty={true}
        busy={busy === "roles"}
        onSave={() => doSave({ roles: draft.roles || [] })}
        hint={`${roles.filter((r) => r.enabled).length} / ${roles.length}`}
        onReset={async () => {
          await api.resetConfig("roles");
          window.location.reload();
        }}
      />
    </Card>
  );
}

/* ================================================================= 信息源 */
function SourcesTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const toast = useToast();
  const sources = draft.sources || [];
  const [testResult, setTestResult] = useState({});
  const [testing, setTesting] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [newSource, setNewSource] = useState({ name: "", type: "rss", url: "", priority: 5 });
  const [aiUrl, setAiUrl] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);

  const update = (idx, key, value) => {
    const next = clone(sources);
    next[idx][key] = value;
    patch({ sources: next });
  };

  const test = async (src) => {
    setTesting(src.name);
    try {
      const res = await api.testSource(src);
      setTestResult((prev) => ({ ...prev, [src.name]: res }));
      if (res.ok) toast.ok(t("common.success"), `${res.count ?? 0}`);
      else toast.err(t("common.failed"), res.error || res.detail);
    } catch (e) {
      setTestResult((prev) => ({ ...prev, [src.name]: { ok: false, error: e.message } }));
      toast.err(t("common.failed"), e.message);
    } finally {
      setTesting("");
    }
  };

  const addSource = () => {
    if (!newSource.name.trim() || !newSource.url.trim()) return;
    patch({ sources: [...clone(sources), { ...newSource, enabled: true, tags: { language: "zh", region: "", category: "自定义" } }] });
    setNewSource({ name: "", type: "rss", url: "", priority: 5 });
    setShowAdd(false);
  };

  const aiSelectors = async () => {
    if (!aiUrl.trim()) return;
    setAiBusy(true);
    try {
      const res = await api.aiSelectors(aiUrl.trim());
      patch({ sources: [...clone(sources), { ...res.source, enabled: true, priority: 5, tags: { category: "自定义" } }] });
      toast.ok(t("common.success"), JSON.stringify(res.selectors));
      setAiUrl("");
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setAiBusy(false);
    }
  };

  const addFromCatalog = (item) => {
    if (sources.some((s) => s.name === item.name)) {
      toast.info(t("common.enabled"), item.name);
      return;
    }
    patch({ sources: [...clone(sources), { ...item, type: item.type || "rss", enabled: true, priority: item.priority || 5 }] });
  };

  const addAllFromCatalog = () => {
    // 按文档「数据源完整清单」：把目录中所有带 URL 的源一次性加入（跳过已存在）
    const existing = new Set(sources.map((s) => s.name));
    const additions = [];
    for (const list of Object.values(grouped)) {
      for (const item of list) {
        if (!item.url || existing.has(item.name)) continue;
        existing.add(item.name);
        additions.push({ ...item, type: item.type || "rss", enabled: true, priority: item.priority || 5 });
      }
    }
    if (!additions.length) {
      toast.info(t("common.enabled"), t("settings.sourceCatalog"));
      return;
    }
    patch({ sources: [...clone(sources), ...additions] });
    toast.ok(t("common.success"), t("settings.sourceAddAllDone", { count: additions.length, skip: 0 }));
  };

  const grouped = meta?.source_catalog_grouped || {};

  return (
    <>
      <Card
        title={t("settings.tabSources")}
        subtitle={t("settings.sourcesHint")}
        actions={
          <>
            <button className="btn btn-sm" onClick={() => setCatalogOpen(true)}>
              {t("settings.sourceCatalog")}
            </button>
            <button className="btn btn-sm btn-primary" onClick={() => setShowAdd(true)}>
              {t("settings.sourceAdd")}
            </button>
          </>
        }
      >
        <div className="row mb-14" style={{ gap: 8 }}>
          <Input className="input-sm" placeholder="网页源 URL" value={aiUrl} onChange={setAiUrl} style={{ maxWidth: 320 }} />
          <button className="btn btn-sm" onClick={aiSelectors} disabled={aiBusy}>
            {aiBusy && <span className="spinner" />}
            {t("settings.sourceAiSelectors")}
          </button>
          <span className="field-hint mb-0">{t("settings.sourcePriorityHint")}</span>
        </div>

        {sources.length === 0 ? (
          <Empty title={t("common.empty")} />
        ) : (
          sources.map((s, i) => (
            <div className="list-row" key={`${s.name}-${i}`}>
              <div className="list-row-main">
                <div className="list-row-title row" style={{ gap: 8 }}>
                  <Input
                    className="input-sm"
                    style={{ maxWidth: 160 }}
                    value={s.name}
                    onChange={(v) => update(i, "name", v)}
                  />
                  <Tag kind="accent">{s.type || "rss"}</Tag>
                  {s.tags?.language && <Tag>{s.tags.language}</Tag>}
                  {s.tags?.category && <Tag>{s.tags.category}</Tag>}
                  {s.verified === false && <Tag kind="warn">{t("settings.sourceUnverified")}</Tag>}
                </div>
                <div className="row mt-8" style={{ gap: 8 }}>
                  <Input
                    className="input-sm input-mono"
                    style={{ flex: 1, minWidth: 220 }}
                    value={s.url || ""}
                    onChange={(v) => update(i, "url", v)}
                  />
                  <Input
                    className="input-sm"
                    type="number"
                    style={{ width: 70 }}
                    value={s.priority ?? 5}
                    onChange={(v) => update(i, "priority", Number(v) || 1)}
                  />
                </div>
                {testResult[s.name] && (
                  <div className={`field-hint ${testResult[s.name].ok ? "text-ok" : "text-err"}`}>
                    {testResult[s.name].ok
                      ? `OK · ${testResult[s.name].count ?? 0} 条${testResult[s.name].sample?.title ? ` · ${testResult[s.name].sample.title}` : ""}`
                      : testResult[s.name].error || testResult[s.name].detail}
                  </div>
                )}
              </div>
              <div className="list-row-actions">
                <Switch checked={!!s.enabled} onChange={(v) => update(i, "enabled", v)} />
                <button className="btn btn-sm" onClick={() => test(s)} disabled={testing === s.name}>
                  {testing === s.name && <span className="spinner" />}
                  {testing === s.name ? t("settings.sourceTesting") : t("settings.sourceTest")}
                </button>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => patch({ sources: sources.filter((_, x) => x !== i) })}
                >
                  {t("common.delete")}
                </button>
              </div>
            </div>
          ))
        )}

        <SaveBar
          dirty={true}
          busy={busy === "sources"}
          onSave={() => doSave({ sources: draft.sources || [] })}
          hint={`${sources.filter((s) => s.enabled).length} / ${sources.length} 已启用`}
          onReset={async () => {
            await api.resetConfig("sources");
            window.location.reload();
          }}
        />
      </Card>

      {showAdd && (
        <Modal
          title={t("settings.sourceAdd")}
          onClose={() => setShowAdd(false)}
          footer={
            <>
              <button className="btn" onClick={() => setShowAdd(false)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" onClick={addSource}>
                {t("common.add")}
              </button>
            </>
          }
        >
          <Field label={t("settings.sourceTypeRss")}>
            <Select
              value={newSource.type}
              onChange={(v) => setNewSource({ ...newSource, type: v })}
              options={[
                { value: "rss", label: t("settings.sourceTypeRss") },
                { value: "api", label: t("settings.sourceTypeApi") },
                { value: "web", label: t("settings.sourceTypeWeb") },
              ]}
            />
          </Field>
          <Field label={t("common.name")} required>
            <Input value={newSource.name} onChange={(v) => setNewSource({ ...newSource, name: v })} />
          </Field>
          <Field label="URL" required>
            <Input value={newSource.url} onChange={(v) => setNewSource({ ...newSource, url: v })} />
          </Field>
          <Field label={t("common.priority")}>
            <Input
              type="number"
              value={newSource.priority}
              onChange={(v) => setNewSource({ ...newSource, priority: Number(v) || 5 })}
            />
          </Field>
        </Modal>
      )}

      {catalogOpen && (
        <Modal title={t("settings.sourceCatalog")} size="lg" onClose={() => setCatalogOpen(false)}>
          <div className="row mb-14" style={{ gap: 8 }}>
            <button className="btn btn-sm btn-primary" onClick={addAllFromCatalog}>
              {t("settings.sourceAddAll")}
            </button>
            <span className="field-hint mb-0">
              {Object.values(grouped).reduce((n, l) => n + l.length, 0)}
            </span>
          </div>
          {(meta?.source_templates || []).map((tpl) => (
            <AlertBar kind="info" key={tpl.type}>
              <b>{tpl.label}</b> · {tpl.doc}
            </AlertBar>
          ))}
          {Object.entries(grouped).map(([cat, list]) => (
            <Accordion key={cat} title={`${cat}（${list.length}）`}>
              {list.map((item) => (
                <div className="list-row" key={item.name}>
                  <div className="list-row-main">
                    <div className="list-row-title">
                      {item.name}{" "}
                      {item.verified === false ? (
                        <Tag kind="warn">{t("settings.sourceUnverified")}</Tag>
                      ) : (
                        <Tag kind="ok">{t("settings.sourceVerified")}</Tag>
                      )}
                    </div>
                    <div className="list-row-meta">
                      <span>{item.type || "rss"}</span>
                      <span className="mono">{item.url || item.homepage || ""}</span>
                      {item.note && <span>{item.note}</span>}
                    </div>
                  </div>
                  <button className="btn btn-sm" onClick={() => addFromCatalog(item)} disabled={!item.url}>
                    {t("settings.sourceAddFromCatalog")}
                  </button>
                </div>
              ))}
            </Accordion>
          ))}
        </Modal>
      )}
    </>
  );
}

/* ================================================================= 推送渠道 */
function ChannelField({ field, value, onChange }) {
  const label = (
    <>
      {field.label}
      {field.required && <span className="field-req">*</span>}
    </>
  );
  if (field.type === "boolean") {
    return (
      <Field label={field.label}>
        <Switch checked={!!value} onChange={onChange} />
      </Field>
    );
  }
  if (field.type === "list") {
    return (
      <Field label={label} hint={field.placeholder}>
        <TagInput value={Array.isArray(value) ? value : []} onChange={onChange} />
      </Field>
    );
  }
  if (field.type === "textarea") {
    return (
      <Field label={label} hint={field.placeholder}>
        <Textarea value={value ?? ""} onChange={onChange} />
      </Field>
    );
  }
  if (field.type === "select") {
    return (
      <Field label={label}>
        <Select value={value ?? field.default ?? ""} onChange={onChange} options={field.options || []} />
      </Field>
    );
  }
  return (
    <Field label={label} hint={field.placeholder}>
      <Input
        type={field.type === "password" ? "password" : field.type === "number" ? "number" : "text"}
        value={value ?? ""}
        onChange={onChange}
        placeholder={field.placeholder || ""}
      />
    </Field>
  );
}

function PushTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const toast = useToast();
  const [testing, setTesting] = useState("");
  const [webpush, setWebpush] = useState({ available: false, public_key: "" });

  const pushConfig = draft.push_config || {};

  useEffect(() => {
    api.webpushKey().then(setWebpush).catch(() => {});
  }, [draft.push_config?.webpush?.vapid_public_key]);

  const setChannel = (id, patchObj) => {
    patch({ push_config: { ...pushConfig, [id]: { ...(pushConfig[id] || {}), ...patchObj } } });
  };

  const test = async (id) => {
    setTesting(id);
    try {
      const res = await api.testChannel(id, pushConfig[id] || {}, "晨析测试推送");
      if (res.ok) toast.ok(t("settings.pushTestOk"), id);
      else toast.err(t("common.failed"), res.detail);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setTesting("");
    }
  };

  const genKeys = async () => {
    try {
      const res = await api.webpushGenKeys();
      setWebpush({ available: true, public_key: res.public_key });
      toast.ok(t("common.success"));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const subscribe = async () => {
    try {
      if (!("serviceWorker" in navigator)) throw new Error("当前浏览器不支持 Web Push");
      if (!webpush.public_key) throw new Error("请先生成 VAPID 密钥");
      const perm = await Notification.requestPermission();
      if (perm !== "granted") throw new Error("浏览器通知权限未授予");
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(webpush.public_key),
      });
      await api.webpushSubscribe(sub.toJSON());
      toast.ok(t("common.success"));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const groups = { 首发: [], 扩展: [] };
  (meta?.channels || []).forEach((c) => (groups[c.group === "扩展" ? "扩展" : "首发"].push(c)));

  return (
    <Card
      title={t("settings.tabPush")}
      subtitle={t("settings.pushHint")}
      actions={
        <span className="field-hint mb-0">
          已启用 {Object.values(pushConfig).filter((v) => v?.enabled).length} / {meta?.channels?.length ?? 0}
        </span>
      }
    >
      {Object.entries(groups).map(([group, list]) =>
        list.length === 0 ? null : (
          <div key={group} className="mb-14">
            <div className="nav-group-title" style={{ padding: "4px 0 8px" }}>
              {group === "扩展" ? t("settings.pushGroupExt") : t("settings.pushGroupFirst")}
            </div>
            {list.map((c) => {
              const cfg = pushConfig[c.id] || {};
              return (
                <Accordion
                  key={c.id}
                  title={
                    <span className="row" style={{ gap: 8 }}>
                      <span>{c.name}</span>
                      {cfg.enabled ? <Tag kind="ok">{t("common.enabled")}</Tag> : <Tag>{t("common.disabled")}</Tag>}
                    </span>
                  }
                  extra={
                    <Switch
                      checked={!!cfg.enabled}
                      onChange={(v) => setChannel(c.id, { enabled: v })}
                    />
                  }
                >
                  {c.doc && <div className="field-hint mb-14">{c.doc}</div>}
                  <div className="grid grid-2">
                    {c.fields.map((f) => (
                      <ChannelField
                        key={f.key}
                        field={f}
                        value={cfg[f.key]}
                        onChange={(v) => setChannel(c.id, { [f.key]: v })}
                      />
                    ))}
                  </div>

                  {c.id === "webpush" && (
                    <div className="row mt-8">
                      <button className="btn btn-sm" onClick={genKeys}>
                        {t("settings.pushWebpushGenKeys")}
                      </button>
                      <button className="btn btn-sm btn-accent" onClick={subscribe}>
                        {t("settings.pushWebpushSubscribe")}
                      </button>
                      <span className="field-hint mb-0">
                        {webpush.available ? t("about.ready") : t("about.notReady")}
                      </span>
                    </div>
                  )}

                  <div className="row mt-14">
                    <button className="btn btn-sm" onClick={() => test(c.id)} disabled={testing === c.id}>
                      {testing === c.id && <span className="spinner" />}
                      {t("settings.pushTest")}
                    </button>
                  </div>
                </Accordion>
              );
            })}
          </div>
        )
      )}

      <SaveBar
        dirty={true}
        busy={busy === "push"}
        onSave={() => doSave({ push_config: draft.push_config || {} })}
        hint={t("settings.pushHint")}
      />
    </Card>
  );
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

/* ================================================================= 调度 */
function ScheduleTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const s = draft.schedule || {};
  const set = (patchObj) => patch({ schedule: { ...s, ...patchObj } });
  const periodical = s.periodical || { weekly: {}, monthly: {} };

  return (
    <Card title={t("settings.tabSchedule")} subtitle={t("settings.scheduleHint")}>
      <Switch
        checked={!!s.enabled}
        onChange={(v) => set({ enabled: v })}
        label={t("settings.scheduleEnabled")}
      />
      <div className="grid grid-3 mt-14">
        <Field label={t("settings.scheduleTime")}>
          <Input value={s.time || ""} onChange={(v) => set({ time: v })} placeholder="07:30" />
        </Field>
        <Field label={t("settings.scheduleDays")}>
          <Select
            value={s.days || "daily"}
            onChange={(v) => set({ days: v })}
            options={[
              { value: "daily", label: t("settings.scheduleDaily") },
              { value: "weekday", label: t("settings.scheduleWeekday") },
              { value: "weekly", label: t("settings.scheduleWeekly") },
              { value: "custom", label: t("settings.scheduleCustom") },
            ]}
          />
        </Field>
        {s.days === "weekly" && (
          <Field label={t("settings.scheduleWeekdayPick")}>
            <Select
              value={String(s.weekday ?? 1)}
              onChange={(v) => set({ weekday: Number(v) })}
              options={[1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: String(n), label: `周${"一二三四五六日"[n - 1]}` }))}
            />
          </Field>
        )}
        {s.days === "custom" && (
          <Field label={t("settings.scheduleCron")} hint={t("settings.scheduleCronHint")}>
            <Input value={s.cron || ""} onChange={(v) => set({ cron: v })} placeholder="0 7 * * 1-5" />
          </Field>
        )}
      </div>

      <div className="nav-group-title" style={{ padding: "10px 0 6px" }}>
        {t("settings.schedulePeriodical")}
      </div>
      <div className="grid grid-2">
        <div className="card card-tight mb-0">
          <Switch
            checked={!!periodical.weekly?.enabled}
            onChange={(v) => set({ periodical: { ...periodical, weekly: { ...periodical.weekly, enabled: v } } })}
            label={t("settings.scheduleWeeklyReport")}
          />
          <div className="grid grid-2 mt-8">
            <Field label={t("settings.scheduleWeekdayPick")} className="mb-0">
              <Select
                value={String(periodical.weekly?.weekday ?? 1)}
                onChange={(v) =>
                  set({ periodical: { ...periodical, weekly: { ...periodical.weekly, weekday: Number(v) } } })
                }
                options={[1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: String(n), label: `周${"一二三四五六日"[n - 1]}` }))}
              />
            </Field>
            <Field label={t("settings.scheduleTime")} className="mb-0">
              <Input
                value={periodical.weekly?.time || "08:30"}
                onChange={(v) => set({ periodical: { ...periodical, weekly: { ...periodical.weekly, time: v } } })}
              />
            </Field>
          </div>
        </div>
        <div className="card card-tight mb-0">
          <Switch
            checked={!!periodical.monthly?.enabled}
            onChange={(v) => set({ periodical: { ...periodical, monthly: { ...periodical.monthly, enabled: v } } })}
            label={t("settings.scheduleMonthlyReport")}
          />
          <div className="grid grid-2 mt-8">
            <Field label="每月几号" className="mb-0">
              <Input
                type="number"
                value={periodical.monthly?.day ?? 1}
                onChange={(v) =>
                  set({ periodical: { ...periodical, monthly: { ...periodical.monthly, day: Number(v) || 1 } } })
                }
              />
            </Field>
            <Field label={t("settings.scheduleTime")} className="mb-0">
              <Input
                value={periodical.monthly?.time || "08:30"}
                onChange={(v) => set({ periodical: { ...periodical, monthly: { ...periodical.monthly, time: v } } })}
              />
            </Field>
          </div>
        </div>
      </div>

      <SaveBar
        dirty={true}
        busy={busy === "schedule"}
        onSave={() =>
          doSave({
            schedule: {
              ...s,
              periodical: {
                weekly: periodical.weekly || { enabled: false },
                monthly: periodical.monthly || { enabled: false },
              },
            },
          })
        }
        hint={t("settings.scheduleHint")}
      />
    </Card>
  );
}

/* ================================================================= AI */
function AiTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const toast = useToast();
  const ai = draft.ai_config || {};
  const [testing, setTesting] = useState(false);
  const [usage, setUsage] = useState(null);

  useEffect(() => {
    api.usage(30).then(setUsage).catch(() => {});
  }, []);

  const set = (patchObj) => patch({ ai_config: { ...ai, ...patchObj } });

  const applyProvider = (id) => {
    const p = (meta?.ai_providers || []).find((x) => x.id === id);
    if (!p) return;
    set({ base_url: p.base_url, model: p.models?.[0] || ai.model, provider: id });
  };

  const aiPayload = () => ({
    base_url: ai.base_url || "",
    api_key: ai.api_key || "",
    model: ai.model || "",
    embedding_model: ai.embedding_model || "",
    prompt: ai.prompt || "",
    temperature: ai.temperature ?? 0.45,
    length: ai.length || "brief",
  });

  const saveNow = () => doSave({ ai_config: aiPayload() });

  const test = async () => {
    // 先保存当前填写内容，再让后端用已保存的配置实调一次模型
    const ok = await doSave({ ai_config: aiPayload() });
    if (!ok) return;
    setTesting(true);
    try {
      const res = await api.testAi();
      toast.ok(t("settings.aiTestOk"), res.detail);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setTesting(false);
    }
  };

  const currentProvider = (meta?.ai_providers || []).find((p) => p.id === ai.provider) || null;

  return (
    <Card title={t("settings.tabAi")} subtitle={t("settings.aiHint")}>
      <Field label={t("settings.aiProvider")} hint={currentProvider?.doc}>
        <Select
          value={ai.provider || ""}
          onChange={applyProvider}
          placeholder={t("common.inputPlaceholder")}
          options={(meta?.ai_providers || []).map((p) => ({ value: p.id, label: p.name }))}
        />
      </Field>

      <div className="grid grid-2">
        <Field label={t("settings.aiBaseUrl")} required>
          <Input
            className="input-mono"
            value={ai.base_url || ""}
            onChange={(v) => set({ base_url: v })}
            placeholder="https://api.deepseek.com/v1"
          />
        </Field>
        <Field label={t("settings.aiApiKey")} required hint="保存后以 *** 掩码返回，留 *** 表示不修改">
          <Input
            type="password"
            value={ai.api_key || ""}
            onChange={(v) => set({ api_key: v })}
            placeholder="sk-..."
          />
        </Field>
      </div>

      <div className="grid grid-2">
        <Field
          label={t("settings.aiModel")}
          hint={
            currentProvider?.models?.length ? `可用：${currentProvider.models.join(", ")}` : ""
          }
        >
          <Input value={ai.model || ""} onChange={(v) => set({ model: v })} />
        </Field>
        <Field
          label={t("settings.aiEmbeddingModel")}
          hint={
            currentProvider?.embedding_models?.length
              ? `可用：${currentProvider.embedding_models.join(", ")}`
              : t("settings.knowledgeHint")
          }
        >
          <Input value={ai.embedding_model || ""} onChange={(v) => set({ embedding_model: v })} />
        </Field>
      </div>

      <Field label={t("settings.aiPrompt")} hint={t("settings.aiPromptPlaceholder")}>
        <Textarea value={ai.prompt || ""} onChange={(v) => set({ prompt: v })} />
      </Field>

      <div className="grid grid-2">
        <Field label="Temperature">
          <Input
            type="number"
            step="0.05"
            value={ai.temperature ?? 0.45}
            onChange={(v) => set({ temperature: Number(v) })}
          />
        </Field>
        <Field label={t("settings.reportLength")}>
          <Select
            value={ai.length || "brief"}
            onChange={(v) => set({ length: v })}
            options={(meta?.report_lengths || []).map((x) => ({ value: x.id, label: x.name }))}
          />
        </Field>
      </div>

      {usage && (
        <div className="grid grid-3 mb-14">
          <Stat label={t("admin.llmCalls")} value={usage.calls} hint={`${usage.cached_calls} 命中缓存`} />
          <Stat label={t("admin.llmTokens")} value={usage.total_tokens} />
          <Stat label={t("admin.llmCost")} value={`$${usage.total_cost}`} accent />
        </div>
      )}

      <div className="row-between mt-14">
        <span className="field-hint mb-0">{t("settings.aiHint")}</span>
        <div className="row">
          <button className="btn" onClick={test} disabled={testing}>
            {testing && <span className="spinner" />}
            {t("settings.aiTest")}
          </button>
          <button className="btn btn-primary" onClick={saveNow} disabled={busy === "ai"}>
            {busy === "ai" && <span className="spinner" />}
            {t("common.save")}
          </button>
        </div>
      </div>
    </Card>
  );
}

/* ================================================================= 模板与语言 */
function TemplateTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const tc = draft.template_config || {};
  const set = (patchObj) => patch({ template_config: { ...tc, ...patchObj } });
  const [advanced, setAdvanced] = useState(false);

  return (
    <Card title={t("settings.tabTemplate")} subtitle={t("settings.templateHint")}>
      <Field label={t("settings.templatePick")}>
        <div className="opt-grid">
          {(meta?.templates || []).map((tpl) => (
            <label className={`opt${draft.template === tpl.id ? " on" : ""}`} key={tpl.id}>
              <input
                type="radio"
                name="template"
                checked={draft.template === tpl.id}
                onChange={() => patch({ template: tpl.id })}
                style={{ accentColor: "var(--brand)", marginTop: 3 }}
              />
              <span className="opt-body">
                <span className="opt-name">
                  {tpl.name}
                  <span
                    style={{
                      display: "inline-block",
                      width: 9,
                      height: 9,
                      borderRadius: 3,
                      background: tpl.accent,
                      marginLeft: 7,
                      verticalAlign: 0,
                    }}
                  />
                </span>
                <div className="opt-desc">{tpl.description}</div>
              </span>
            </label>
          ))}
        </div>
      </Field>

      <div className="grid grid-3">
        <Field label={t("settings.reportLanguage")}>
          <Select
            value={["zh", "en", "bilingual"].includes(draft.report_language) ? draft.report_language : "zh"}
            onChange={(v) => patch({ report_language: v })}
            options={(meta?.report_languages || [])
              .filter((x) => ["zh", "en", "bilingual"].includes(x.id))
              .map((x) => ({ value: x.id, label: x.name }))}
          />
        </Field>
        <Field label={t("settings.uiLanguage")}>
          <Select
            value={draft.ui_language === "en" ? "en" : "zh"}
            onChange={(v) => {
              patch({ ui_language: v });
              setLanguage(v);
            }}
            options={LANGUAGES.map((l) => ({ value: l.id, label: l.label }))}
          />
        </Field>
        <Field label={t("settings.translateEnabled")}>
          <Switch
            checked={!!draft.translate_enabled}
            onChange={(v) => patch({ translate_enabled: v })}
          />
        </Field>
      </div>

      <Field label={t("settings.templateCustom")} hint={t("settings.templateCustomHint")}>
        <div className="row mb-8">
          <Switch checked={advanced} onChange={setAdvanced} label={t("common.advanced")} />
        </div>
        {advanced && (
          <>
            <Textarea
              className="textarea-lg"
              value={tc.custom_html || ""}
              onChange={(v) => set({ custom_html: v })}
              placeholder="<article><h1>{{title}}</h1>{{content}}</article>"
            />
            <Textarea
              className="mt-8"
              value={tc.custom_css || ""}
              onChange={(v) => set({ custom_css: v })}
              placeholder="article { font-family: serif; }"
            />
          </>
        )}
      </Field>

      <SaveBar
        dirty={true}
        busy={busy === "template"}
        onSave={() =>
          doSave({
            template: draft.template,
            template_config: draft.template_config || {},
            report_language: draft.report_language,
            ui_language: draft.ui_language,
            translate_enabled: !!draft.translate_enabled,
          })
        }
        hint={t("settings.templateHint")}
      />
    </Card>
  );
}

/* ================================================================= 语音 */
function TtsTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const tts = draft.tts_config || {};
  const set = (patchObj) => patch({ tts_config: { ...tts, ...patchObj } });
  const provider = (meta?.tts_providers || []).find((p) => p.id === (tts.provider || "edge"));

  return (
    <Card title={t("settings.tabTts")} subtitle={t("settings.ttsHint")}>
      <Switch checked={!!tts.enabled} onChange={(v) => set({ enabled: v })} label={t("settings.ttsEnabled")} />
      <div className="grid grid-3 mt-14">
        <Field label={t("settings.ttsProvider")}>
          <Select
            value={tts.provider || "edge"}
            onChange={(v) => set({ provider: v, voice: "" })}
            options={(meta?.tts_providers || []).map((p) => ({ value: p.id, label: p.name }))}
          />
        </Field>
        <Field label={t("settings.ttsVoice")}>
          <Select
            value={tts.voice || ""}
            onChange={(v) => set({ voice: v })}
            placeholder={t("common.inputPlaceholder")}
            options={(provider?.voices || []).map((v) => ({ value: v.id, label: `${v.name} · ${v.id}` }))}
          />
        </Field>
        <Field label={t("settings.ttsFormat")}>
          <Select
            value={tts.format || "mp3"}
            onChange={(v) => set({ format: v })}
            options={(meta?.tts_formats || []).map((f) => ({ value: f.id, label: f.name }))}
          />
        </Field>
      </div>
      <div className="grid grid-2">
        <Field label={t("settings.reportLength")}>
          <Select
            value={tts.length || "brief"}
            onChange={(v) => set({ length: v })}
            options={(meta?.report_lengths || []).map((x) => ({ value: x.id, label: x.name }))}
          />
        </Field>
        <Field label={t("settings.ttsPush")}>
          <Switch checked={!!tts.push} onChange={(v) => set({ push: v })} />
        </Field>
      </div>
      <SaveBar
        dirty={true}
        busy={busy === "tts"}
        onSave={() => doSave({ tts_config: draft.tts_config || {} })}
        hint={t("settings.ttsHint")}
      />
    </Card>
  );
}

/* ================================================================= 知识库 */
function KnowledgeTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const meta = useMeta();
  const kc = draft.knowledge_config || {};
  const set = (patchObj) => patch({ knowledge_config: { ...kc, ...patchObj } });

  return (
    <Card title={t("settings.tabKnowledge")} subtitle={t("settings.knowledgeHint")}>
      <div className="row mb-14" style={{ gap: 26 }}>
        <Switch checked={!!kc.enabled} onChange={(v) => set({ enabled: v })} label={t("settings.knowledgeEnabled")} />
        <Switch
          checked={!!kc.auto_ingest}
          onChange={(v) => set({ auto_ingest: v })}
          label={t("settings.knowledgeAutoIngest")}
        />
      </div>
      <div className="grid grid-3">
        <Field label={t("settings.knowledgeTopK")}>
          <Input
            type="number"
            value={kc.top_k ?? 6}
            onChange={(v) => set({ top_k: Number(v) || 6 })}
          />
        </Field>
        <Field label={t("settings.knowledgeProvider")}>
          <Select
            value={kc.embedding_provider || "auto"}
            onChange={(v) => set({ embedding_provider: v })}
            options={(meta?.embedding_providers || []).map((p) => ({ value: p.id, label: p.name }))}
          />
        </Field>
        <Field label={t("settings.knowledgeVectorStore")}>
          <Select
            value={kc.vector_store || "builtin"}
            onChange={(v) => set({ vector_store: v })}
            options={(meta?.vector_stores || []).map((p) => ({ value: p.id, label: p.name }))}
          />
        </Field>
      </div>
      <AlertBar kind="info">{t("knowledge.reindexHint")}</AlertBar>
      <SaveBar
        dirty={true}
        busy={busy === "knowledge"}
        onSave={() => doSave({ knowledge_config: draft.knowledge_config || {} })}
        hint={t("settings.knowledgeHint")}
      />
    </Card>
  );
}

/* ================================================================= 抓取 */
function FetchTab({ draft, patch, busy, doSave }) {
  const { t } = useTranslation();
  const fc = draft.fetch_config || {};
  const set = (patchObj) => patch({ fetch_config: { ...fc, ...patchObj } });

  return (
    <Card title={t("settings.tabFetch")} subtitle={t("settings.fetchHint")}>
      <div className="grid grid-2">
        <Field label={t("settings.fetchSinceHours")}>
          <Input
            type="number"
            value={fc.since_hours ?? 24}
            onChange={(v) => set({ since_hours: Number(v) || 24 })}
          />
        </Field>
        <Field label={t("settings.fetchLimit")}>
          <Input
            type="number"
            value={fc.limit_per_source ?? 60}
            onChange={(v) => set({ limit_per_source: Number(v) || 60 })}
          />
        </Field>
      </div>
      <div className="row" style={{ gap: 26 }}>
        <Switch
          checked={!!fc.use_ai_summary}
          onChange={(v) => set({ use_ai_summary: v })}
          label={t("settings.fetchAiSummary")}
        />
        <Switch
          checked={!!fc.use_ai_classify}
          onChange={(v) => set({ use_ai_classify: v })}
          label={t("settings.fetchAiClassify")}
        />
        <Switch
          checked={!!fc.render_js}
          onChange={(v) => set({ render_js: v })}
          label="Playwright 渲染 JS（可选依赖）"
        />
      </div>
      <SaveBar
        dirty={true}
        busy={busy === "fetch"}
        onSave={() => doSave({ fetch_config: draft.fetch_config || {} })}
        hint={t("settings.fetchHint")}
      />
    </Card>
  );
}

/* ================================================================= 页面 */
export default function Settings() {
  const { t } = useTranslation();
  const toast = useToast();
  const meta = useMeta();
  const { config, loading, error, save } = useConfig();

  const [tab, setTab] = useState("industry");
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (config) setDraft(clone(config));
  }, [config]);

  const patch = useCallback((partial) => setDraft((prev) => ({ ...prev, ...partial })), []);

  const doSave = useCallback(
    async (payload) => {
      setBusy(tab);
      try {
        await save(payload);
        toast.ok(t("common.saved"));
        return true;
      } catch (e) {
        toast.err(t("common.failed"), e.message);
        return false;
      } finally {
        setBusy("");
      }
    },
    [save, tab, t, toast]
  );

  const TABS = useMemo(
    () => [
      { key: "industry", label: t("settings.tabIndustry") },
      { key: "focus", label: t("settings.tabFocus") },
      { key: "roles", label: t("settings.tabRoles") },
      { key: "sources", label: t("settings.tabSources") },
      { key: "push", label: t("settings.tabPush") },
      { key: "schedule", label: t("settings.tabSchedule") },
      { key: "ai", label: t("settings.tabAi") },
      { key: "template", label: t("settings.tabTemplate") },
      { key: "tts", label: t("settings.tabTts") },
      { key: "knowledge", label: t("settings.tabKnowledge") },
      { key: "fetch", label: t("settings.tabFetch") },
    ],
    [t]
  );

  if (loading || !draft) return <Loading text={t("common.loading")} />;
  if (error) return <AlertBar kind="danger">{error}</AlertBar>;

  const props = { draft, patch, busy, doSave };

  return (
    <>
      <PageHead title={t("settings.title")} subtitle={t("settings.subtitle")} />
      <Tabs items={TABS} value={tab} onChange={setTab} />
      {tab === "industry" && <IndustryTab {...props} />}
      {tab === "focus" && <FocusTab {...props} />}
      {tab === "roles" && <RolesTab {...props} />}
      {tab === "sources" && <SourcesTab {...props} />}
      {tab === "push" && <PushTab {...props} />}
      {tab === "schedule" && <ScheduleTab {...props} />}
      {tab === "ai" && <AiTab {...props} />}
      {tab === "template" && <TemplateTab {...props} />}
      {tab === "tts" && <TtsTab {...props} />}
      {tab === "knowledge" && <KnowledgeTab {...props} />}
      {tab === "fetch" && <FetchTab {...props} />}
    </>
  );
}
