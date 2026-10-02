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
  Switch,
  Tag,
  Textarea,
  useConfirm,
} from "../components/ui";
import { useMe, useMeta } from "../store";

const TYPE_KEYS = { source: "数据源", push: "推送", ai: "AI 处理" };

export default function Plugins() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirm = useConfirm();
  const me = useMe();
  const meta = useMeta();

  const [view, setView] = useState("installed");
  const [type, setType] = useState("");
  const [plugins, setPlugins] = useState(null);
  const [market, setMarket] = useState(null);
  const [installSource, setInstallSource] = useState("");
  const [cfgTarget, setCfgTarget] = useState(null);
  const [cfgText, setCfgText] = useState("");
  const [busy, setBusy] = useState("");

  const isAdmin = me?.role === "admin";

  const load = useCallback(async () => {
    try {
      const [p, m] = await Promise.all([
        api.plugins().catch(() => ({ plugins: [] })),
        api.marketplace().catch(() => ({ items: [] })),
      ]);
      setPlugins(p.plugins || []);
      setMarket(m.items || []);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
      setPlugins([]);
    }
  }, [t, toast]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sync = async () => {
    setBusy("sync");
    try {
      const res = await api.syncPlugins();
      toast.ok(t("plugins.synced", { count: res.count }));
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy("");
    }
  };

  const install = async (source) => {
    if (!source?.trim()) return;
    setBusy("install");
    try {
      const res = await api.installPlugin(source.trim());
      toast.ok(t("plugins.installedOk"), res.warning || res.name);
      setInstallSource("");
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy("");
    }
  };

  const installFromMarket = async (slug) => {
    setBusy(`market-${slug}`);
    try {
      const res = await api.installFromMarket(slug);
      toast.ok(t("plugins.installedOk"), res.name);
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy("");
    }
  };

  const toggle = async (p, enabled) => {
    setBusy(`toggle-${p.id}`);
    try {
      await api.togglePlugin(p.id, enabled);
      toast.ok(t("common.saved"), `${p.name} · ${enabled ? t("common.enabled") : t("common.disabled")}`);
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy("");
    }
  };

  const uninstall = async (p) => {
    if (!(await confirm({ message: `${t("common.deleteConfirm")}\n${p.name}`, danger: true, confirmText: t("plugins.uninstall") }))) return;
    setBusy(`del-${p.id}`);
    try {
      await api.deletePlugin(p.id, false);
      toast.ok(t("common.success"));
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy("");
    }
  };

  const test = async (p) => {
    setBusy(`test-${p.id}`);
    try {
      const res = await api.testPlugin(p.id);
      if (res.ok) toast.ok(t("plugins.testPush"), res.detail);
      else toast.err(t("common.failed"), res.detail);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy("");
    }
  };

  const openConfig = (p) => {
    setCfgTarget(p);
    setCfgText(JSON.stringify(p.config || {}, null, 2));
  };

  const saveConfig = async () => {
    let parsed;
    try {
      parsed = JSON.parse(cfgText || "{}");
    } catch (e) {
      toast.err(t("common.failed"), "JSON 格式错误");
      return;
    }
    setBusy("cfg");
    try {
      await api.pluginConfig(cfgTarget.id, parsed);
      toast.ok(t("common.saved"));
      setCfgTarget(null);
      await load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setBusy("");
    }
  };

  const filtered = type ? (plugins || []).filter((p) => p.type === type) : plugins || [];

  return (
    <>
      <PageHead title={t("plugins.title")} subtitle={t("plugins.subtitle")}>
        <Seg
          value={view}
          onChange={setView}
          items={[
            { value: "installed", label: `${t("plugins.installed")} (${plugins?.length ?? 0})` },
            { value: "market", label: t("plugins.marketplace") },
          ]}
        />
        {isAdmin && (
          <button className="btn" onClick={sync} disabled={!!busy}>
            {busy === "sync" && <span className="spinner" />}
            {t("plugins.sync")}
          </button>
        )}
      </PageHead>

      <AlertBar kind="warn">{t("plugins.securityWarning")}</AlertBar>

      {!isAdmin && <AlertBar kind="info">插件安装 / 启用需要管理员权限，当前为只读视图。</AlertBar>}

      {view === "installed" ? (
        <>
          <Card tight>
            <div className="row-between">
              <Seg
                value={type}
                onChange={setType}
                items={[
                  { value: "", label: t("common.all") },
                  ...Object.entries(TYPE_KEYS).map(([k, v]) => ({ value: k, label: v })),
                ]}
              />
              {isAdmin && (
                <div className="inline-form" style={{ flex: 1, maxWidth: 460 }}>
                  <Input
                    className="input-sm"
                    placeholder={t("plugins.installPath")}
                    value={installSource}
                    onChange={setInstallSource}
                    onKeyDown={(e) => e.key === "Enter" && install(installSource)}
                  />
                  <button className="btn btn-sm btn-primary" onClick={() => install(installSource)} disabled={busy === "install"}>
                    {busy === "install" && <span className="spinner" />}
                    {t("plugins.install")}
                  </button>
                </div>
              )}
            </div>
          </Card>

          {plugins === null ? (
            <Loading />
          ) : filtered.length === 0 ? (
            <Card>
              <Empty
                icon="⊙"
                title={t("plugins.empty")}
                desc={t("plugins.subtitle")}
                action={
                  isAdmin && (
                    <button className="btn btn-primary" onClick={sync}>
                      {t("plugins.sync")}
                    </button>
                  )
                }
              />
            </Card>
          ) : (
            <div className="grid grid-auto">
              {filtered.map((p) => (
                <div className="card mb-0" key={p.id}>
                  <div className="row-between" style={{ alignItems: "flex-start" }}>
                    <div>
                      <div className="card-title">{p.name}</div>
                      <div className="card-sub">
                        v{p.version} · {p.author || "unknown"}
                      </div>
                    </div>
                    <Tag kind={p.type === "source" ? "accent" : p.type === "push" ? "brand" : "ok"}>
                      {TYPE_KEYS[p.type] || p.type}
                    </Tag>
                  </div>
                  <div className="fs-13 text-2 mt-8">{p.description}</div>
                  <div className="row mt-8" style={{ gap: 6 }}>
                    <Tag kind={p.valid ? "ok" : "danger"}>
                      {p.valid ? t("plugins.valid") : t("plugins.invalid")}
                    </Tag>
                    {p.enabled ? <Tag kind="ok">{t("common.enabled")}</Tag> : <Tag>{t("common.disabled")}</Tag>}
                    {(p.permissions || []).map((perm) => (
                      <Tag key={perm} title={t("plugins.permissions")}>
                        {perm}
                      </Tag>
                    ))}
                  </div>
                  {!p.valid && p.error && <div className="field-hint text-err">{p.error}</div>}

                  {isAdmin && (
                    <div className="row mt-14" style={{ gap: 6 }}>
                      <Switch
                        checked={p.enabled}
                        disabled={!p.valid || busy === `toggle-${p.id}`}
                        onChange={(v) => toggle(p, v)}
                      />
                      <div className="spacer" />
                      {p.type === "push" && (
                        <button className="btn btn-sm" onClick={() => test(p)} disabled={!p.enabled || !!busy}>
                          {busy === `test-${p.id}` && <span className="spinner" />}
                          {t("plugins.testPush")}
                        </button>
                      )}
                      <button className="btn btn-sm" onClick={() => openConfig(p)}>
                        {t("plugins.config")}
                      </button>
                      <button className="btn btn-sm btn-danger" onClick={() => uninstall(p)}>
                        {t("plugins.uninstall")}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      ) : market === null ? (
        <Loading />
      ) : market.length === 0 ? (
        <Card>
          <Empty icon="⊙" title={t("common.empty")} />
        </Card>
      ) : (
        <div className="grid grid-auto">
          {market.map((m) => (
            <div className="card mb-0" key={m.slug}>
              <div className="row-between" style={{ alignItems: "flex-start" }}>
                <div>
                  <div className="card-title">{m.title || m.name}</div>
                  <div className="card-sub">
                    v{m.version} · {m.author}
                  </div>
                </div>
                <Tag kind="accent">{TYPE_KEYS[m.type] || m.type}</Tag>
              </div>
              <div className="fs-13 text-2 mt-8">{m.description}</div>
              <div className="row mt-8" style={{ gap: 6 }}>
                <Tag>
                  {t("plugins.downloads")} {m.downloads ?? 0}
                </Tag>
                {(m.permissions || []).map((perm) => (
                  <Tag key={perm}>{perm}</Tag>
                ))}
              </div>
              <div className="row mt-14">
                {m.installed ? (
                  <Tag kind="ok">{t("plugins.installedTag")}</Tag>
                ) : (
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() => installFromMarket(m.slug)}
                    disabled={!isAdmin || busy === `market-${m.slug}`}
                  >
                    {busy === `market-${m.slug}` && <span className="spinner" />}
                    {t("plugins.install")}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {meta?.plugin_types && (
        <Card title={t("plugins.permissions")} tight>
          <div className="row" style={{ gap: 6 }}>
            {(meta.plugin_permissions || []).map((p) => (
              <Tag key={p}>{p}</Tag>
            ))}
          </div>
        </Card>
      )}

      {cfgTarget && (
        <Modal
          title={`${cfgTarget.name} · ${t("plugins.config")}`}
          onClose={() => setCfgTarget(null)}
          footer={
            <>
              <button className="btn" onClick={() => setCfgTarget(null)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" onClick={saveConfig} disabled={busy === "cfg"}>
                {busy === "cfg" && <span className="spinner" />}
                {t("common.save")}
              </button>
            </>
          }
        >
          {Object.keys(cfgTarget.config_schema || {}).length > 0 && (
            <AlertBar kind="info">
              <div className="mono fs-12">{JSON.stringify(cfgTarget.config_schema, null, 2)}</div>
            </AlertBar>
          )}
          <Field label="JSON 配置">
            <Textarea className="textarea-lg" value={cfgText} onChange={setCfgText} />
          </Field>
        </Modal>
      )}
    </>
  );
}
