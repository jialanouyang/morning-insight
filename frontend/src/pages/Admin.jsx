import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import api from "../api";
import { useToast } from "../components/Toast";
import {
  AlertBar,
  Card,
  Empty,
  Loading,
  PageHead,
  Seg,
  Select,
  Stat,
  Tabs,
  Tag,
  useConfirm,
} from "../components/ui";
import { useMe } from "../store";

export default function Admin() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirm = useConfirm();
  const me = useMe();

  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState(null);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState(null);
  const [logStatus, setLogStatus] = useState("");
  const [jobs, setJobs] = useState(null);
  const [usage, setUsage] = useState(null);
  const [denied, setDenied] = useState(false);

  // 非管理员不做任何请求，避免必然失败的调用与多余报错
  const isAdmin = !!me && me.role === "admin";

  const load = useCallback(async () => {
    try {
      const [s, j] = await Promise.all([api.adminStats(), api.adminJobs()]);
      setStats(s);
      setJobs(j.jobs || []);
    } catch (e) {
      if (/权限|admin|403/.test(e.message)) setDenied(true);
      else toast.err(t("common.failed"), e.message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      setUsers(await api.adminUsers());
    } catch (e) {
      toast.err(t("common.failed"), e.message);
      setUsers([]);
    }
  }, [t, toast]);

  const loadLogs = useCallback(async () => {
    try {
      setLogs(await api.adminPushLogs({ limit: 200, status: logStatus }));
    } catch (e) {
      setLogs([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logStatus]);

  const loadUsage = useCallback(async () => {
    try {
      setUsage(await api.adminUsage(30));
    } catch (e) {
      setUsage(null);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return undefined;
    load();
    loadUsage();
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) return undefined;
    if (tab === "users") loadUsers();
    if (tab === "pushLogs") loadLogs();
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, logStatus, isAdmin]);

  const setRole = async (u, role) => {
    try {
      await api.adminUpdateUser(u.id, { role });
      toast.ok(t("common.saved"));
      loadUsers();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const toggleActive = async (u) => {
    try {
      await api.adminUpdateUser(u.id, { is_active: !u.is_active });
      toast.ok(t("common.saved"));
      loadUsers();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const removeUser = async (u) => {
    if (!(await confirm({ message: `${t("common.deleteConfirm")}\n${u.email}`, danger: true, confirmText: t("common.delete") }))) return;
    try {
      await api.adminDeleteUser(u.id);
      toast.ok(t("common.success"));
      loadUsers();
      load();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  const syncJobs = async () => {
    try {
      const res = await api.adminSyncJobs();
      setJobs(res.jobs || []);
      toast.ok(t("common.success"));
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  if (me && !isAdmin) {
    return (
      <>
        <PageHead title={t("admin.title")} subtitle={t("admin.subtitle")} />
        <AlertBar kind="warn">该页面仅管理员可见。当前账号角色为普通用户。</AlertBar>
      </>
    );
  }

  if (denied) {
    return (
      <>
        <PageHead title={t("admin.title")} subtitle={t("admin.subtitle")} />
        <AlertBar kind="warn">需要管理员权限。</AlertBar>
      </>
    );
  }

  const TABS = [
    { key: "users", label: t("admin.tabUsers") },
    { key: "stats", label: t("admin.tabStats") },
    { key: "pushLogs", label: t("admin.tabPushLogs") },
    { key: "jobs", label: t("admin.tabJobs") },
    { key: "usage", label: t("admin.tabUsage") },
  ];

  return (
    <>
      <PageHead title={t("admin.title")} subtitle={t("admin.subtitle")} />
      <Tabs items={TABS} value={tab} onChange={setTab} />

      {tab === "users" && (
        <Card>
          {users === null ? (
            <Loading />
          ) : users.length === 0 ? (
            <Empty title={t("common.empty")} />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("login.email")}</th>
                    <th>{t("login.displayName")}</th>
                    <th>{t("admin.role")}</th>
                    <th>{t("admin.active")}</th>
                    <th>{t("admin.reportCount")}</th>
                    <th>{t("admin.createdAt")}</th>
                    <th>{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td className="td-nowrap">{u.email}</td>
                      <td>{u.display_name}</td>
                      <td>
                        <Select
                          className="input-sm"
                          value={u.role}
                          onChange={(v) => setRole(u, v)}
                          options={[
                            { value: "admin", label: t("admin.roleAdmin") },
                            { value: "user", label: t("admin.roleUser") },
                          ]}
                        />
                      </td>
                      <td>
                        <Tag kind={u.is_active ? "ok" : "danger"}>
                          {u.is_active ? t("admin.active") : t("common.disabled")}
                        </Tag>
                      </td>
                      <td className="td-num">{u.report_count}</td>
                      <td className="td-nowrap fs-12">{u.created_at?.slice(0, 10)}</td>
                      <td>
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-sm" onClick={() => toggleActive(u)} disabled={u.id === me?.id}>
                            {u.is_active ? t("common.disabled") : t("common.enabled")}
                          </button>
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => removeUser(u)}
                            disabled={u.id === me?.id}
                          >
                            {t("common.delete")}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === "stats" && (
        <>
          {stats === null ? (
            <Loading />
          ) : (
            <>
              <div className="grid grid-4 mb-14">
                <Stat label={t("admin.users")} value={stats.users} />
                <Stat label={t("admin.reports")} value={stats.reports} hint={`7 天 ${stats.reports_7d}`} />
                <Stat label={t("admin.articles")} value={stats.articles} />
                <Stat label={t("admin.chunks")} value={stats.knowledge_chunks} />
                <Stat label={t("admin.periodicals")} value={stats.periodicals} />
                <Stat
                  label={t("competitors.title")}
                  value={stats.competitors}
                  hint={`${t("alerts.title")} ${stats.alerts}`}
                />
                <Stat
                  label={t("plugins.title")}
                  value={`${stats.plugins_enabled} / ${stats.plugins}`}
                  hint={t("common.enabled")}
                />
                <Stat label={t("admin.llmTokens")} value={stats.llm_tokens} hint={`$${stats.llm_cost}`} />
              </div>
              <Card title={t("admin.tabPushLogs")} tight>
                <div className="row" style={{ gap: 10 }}>
                  <Tag kind="ok">
                    {t("admin.pushSuccess")} {stats.push_by_status?.success ?? 0}
                  </Tag>
                  <Tag kind="danger">
                    {t("admin.pushFailed")} {stats.push_by_status?.failed ?? 0}
                  </Tag>
                  <Tag>
                    {t("common.total")} {stats.push_logs}
                  </Tag>
                </div>
              </Card>
            </>
          )}
        </>
      )}

      {tab === "pushLogs" && (
        <Card
          actions={
            <Seg
              value={logStatus}
              onChange={setLogStatus}
              items={[
                { value: "", label: t("common.all") },
                { value: "success", label: t("admin.pushSuccess") },
                { value: "failed", label: t("admin.pushFailed") },
              ]}
            />
          }
        >
          {logs === null ? (
            <Loading />
          ) : logs.length === 0 ? (
            <Empty title={t("common.empty")} />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("common.time")}</th>
                    <th>{t("login.email")}</th>
                    <th>{t("common.channel")}</th>
                    <th>{t("admin.kind")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("admin.error")}</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l) => (
                    <tr key={l.id}>
                      <td className="td-nowrap fs-12">{l.created_at?.slice(0, 19).replace("T", " ")}</td>
                      <td className="td-nowrap fs-12">{l.user}</td>
                      <td>
                        <Tag>{l.channel}</Tag>
                      </td>
                      <td className="fs-12">{l.kind}</td>
                      <td>
                        <Tag kind={l.status === "success" ? "ok" : "danger"}>{l.status}</Tag>
                      </td>
                      <td className="fs-12 text-err" style={{ maxWidth: 360 }}>
                        {l.error}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === "jobs" && (
        <Card
          title={t("admin.tabJobs")}
          actions={
            <button className="btn btn-sm" onClick={syncJobs}>
              {t("admin.syncJobs")}
            </button>
          }
        >
          {jobs === null ? (
            <Loading />
          ) : jobs.length === 0 ? (
            <Empty title={t("admin.noJobs")} desc={t("settings.scheduleHint")} />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Job ID</th>
                    <th>{t("admin.nextRun")}</th>
                    <th>{t("common.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id}>
                      <td className="mono fs-12">{j.id}</td>
                      <td className="td-nowrap fs-12">
                        {j.next_run ? j.next_run.slice(0, 19).replace("T", " ") : "—"}
                      </td>
                      <td>
                        <Tag kind={j.next_run ? "ok" : "warn"}>
                          {j.next_run ? t("common.enabled") : t("common.disabled")}
                        </Tag>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === "usage" && (
        <>
          {usage === null ? (
            <Loading />
          ) : (
            <>
              <div className="grid grid-3 mb-14">
                <Stat label={t("admin.llmCalls")} value={usage.calls} />
                <Stat label={t("admin.llmTokens")} value={usage.total_tokens} />
                <Stat label={t("admin.llmCost")} value={`$${usage.total_cost}`} accent />
              </div>
              <div className="grid grid-2">
                <Card title="按模型">
                  {Object.entries(usage.by_model || {}).map(([k, v]) => (
                    <div className="list-row" key={k}>
                      <div className="list-row-main">
                        <div className="list-row-title">{k}</div>
                        <div className="list-row-meta">
                          <span>{v.calls} 次</span>
                          <span>{v.tokens} tokens</span>
                        </div>
                      </div>
                      <Tag kind="brand">${v.cost.toFixed(4)}</Tag>
                    </div>
                  ))}
                </Card>
                <Card title="按用户">
                  {Object.entries(usage.by_user || {}).map(([k, v]) => (
                    <div className="list-row" key={k}>
                      <div className="list-row-main">
                        <div className="list-row-title">{k}</div>
                        <div className="list-row-meta">
                          <span>{v.calls} 次</span>
                          <span>{v.tokens} tokens</span>
                        </div>
                      </div>
                      <Tag kind="brand">${v.cost.toFixed(4)}</Tag>
                    </div>
                  ))}
                </Card>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
