/* 统一的 API 客户端：鉴权、错误处理、以及全部后端端点的封装。 */

const TOKEN_KEY = "mi_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, raw = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const resp = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 401) {
    clearToken();
    if (!location.pathname.startsWith("/login")) location.href = "/login";
    throw new Error("登录状态已失效，请重新登录");
  }

  if (raw) {
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.detail || `请求失败（${resp.status}）`);
    }
    return resp;
  }

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = data.detail;
    throw new Error(
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `请求失败（${resp.status}）`
    );
  }
  return data;
}

/** 下载二进制/文本导出（md / html / pdf / png） */
export async function download(path, filename) {
  const resp = await fetch(path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || `导出失败（${resp.status}）`);
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "download";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

const qs = (params = {}) => {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ""
  );
  return entries.length ? `?${new URLSearchParams(entries)}` : "";
};

export const api = {
  // ---------------- 元信息 / 健康 ----------------
  meta: () => request("/api/meta"),
  features: () => request("/api/features"),
  health: () => request("/api/health"),

  // ---------------- 认证 ----------------
  authStatus: () => request("/api/auth/status"),
  register: (body) => request("/api/auth/register", { method: "POST", body }),
  login: (body) => request("/api/auth/login", { method: "POST", body }),
  me: () => request("/api/auth/me"),
  updateMe: (body) => request("/api/auth/me", { method: "PUT", body }),
  changePassword: (body) => request("/api/auth/password", { method: "POST", body }),

  // ---------------- 配置 ----------------
  getConfig: () => request("/api/config"),
  saveConfig: (body) => request("/api/config", { method: "PUT", body }),
  resetConfig: (section = "") => request(`/api/config/reset${qs({ section })}`, { method: "POST" }),
  testSource: (source) => request("/api/config/sources/test", { method: "POST", body: { source } }),
  sourcesFromKeywords: (keywords, lang = "zh") =>
    request("/api/config/sources/from-keywords", { method: "POST", body: { keywords, lang } }),
  aiSelectors: (url, fields) =>
    request("/api/config/sources/ai-selectors", { method: "POST", body: { url, fields } }),
  testChannel: (channel, config, title) =>
    request("/api/config/channels/test", { method: "POST", body: { channel, config, title } }),
  webpushKey: () => request("/api/config/webpush/key"),  webpushGenKeys: () => request("/api/config/webpush/keys", { method: "POST" }),
  webpushSubscribe: (subscription) =>
    request("/api/config/webpush/subscribe", { method: "POST", body: { subscription } }),
  usage: (days = 30) => request(`/api/config/usage${qs({ days })}`),
  testAi: (model = "") => request("/api/config/ai/test", { method: "POST", body: { model } }),

  // ---------------- 晨报 ----------------
  reports: (params) => request(`/api/reports${qs(params)}`),
  report: (id) => request(`/api/reports/${id}`),
  translateReport: (id, targetLang) =>
    request(`/api/reports/${id}/translate`, { method: "POST", body: { target_lang: targetLang } }),
  deleteReport: (id) => request(`/api/reports/${id}`, { method: "DELETE" }),
  generateReport: (opts = {}) => request("/api/reports/generate", { method: "POST", body: opts }),
  pushReport: (id, channels) =>
    request(`/api/reports/${id}/push`, { method: "POST", body: { channels: channels || null } }),
  exportReport: (id, fmt) => download(`/api/reports/${id}/export?fmt=${fmt}`, `report.${fmt}`),
  generateTts: (id, opts = {}) => request(`/api/reports/${id}/tts`, { method: "POST", body: opts }),
  reportTts: (id) => request(`/api/reports/${id}/tts`),
  ttsAssets: (limit = 50) => request(`/api/reports/tts/assets${qs({ limit })}`),

  // ---------------- 知识库 ----------------
  knowledgeAsk: (body) => request("/api/knowledge/ask", { method: "POST", body }),
  knowledgeSearch: (body) => request("/api/knowledge/search", { method: "POST", body }),
  knowledgeStats: () => request("/api/knowledge/stats"),
  knowledgeIngest: (limit = 30) => request(`/api/knowledge/ingest${qs({ limit })}`, { method: "POST" }),
  knowledgeReindex: (limit = 200) => request(`/api/knowledge/reindex${qs({ limit })}`, { method: "POST" }),
  knowledgeClear: () => request("/api/knowledge", { method: "DELETE" }),

  // ---------------- 动态追踪 ----------------
  competitors: () => request("/api/competitors"),
  createCompetitor: (body) => request("/api/competitors", { method: "POST", body }),
  updateCompetitor: (id, body) => request(`/api/competitors/${id}`, { method: "PUT", body }),
  deleteCompetitor: (id) => request(`/api/competitors/${id}`, { method: "DELETE" }),
  compareCompetitors: (days = 30) => request(`/api/competitors/compare${qs({ days })}`),
  competitorTimeline: (id, limit = 100) =>
    request(`/api/competitors/${id}/timeline${qs({ limit })}`),
  scanCompetitors: (limit = 200, useAi = true) =>
    request(`/api/competitors/scan${qs({ limit, use_ai: useAi })}`, { method: "POST" }),

  // ---------------- 关键词预警 ----------------
  alerts: () => request("/api/alerts"),
  createAlert: (body) => request("/api/alerts", { method: "POST", body }),
  updateAlert: (id, body) => request(`/api/alerts/${id}`, { method: "PUT", body }),
  deleteAlert: (id) => request(`/api/alerts/${id}`, { method: "DELETE" }),
  alertHistory: (limit = 100) => request(`/api/alerts/history${qs({ limit })}`),
  scanAlerts: (limit = 200, useAi = true) =>
    request(`/api/alerts/scan${qs({ limit, use_ai: useAi })}`, { method: "POST" }),

  // ---------------- 周报 / 月报 ----------------
  periodicals: (params) => request(`/api/periodicals${qs(params)}`),
  periodical: (id) => request(`/api/periodicals/${id}`),
  generatePeriodical: (body) => request("/api/periodicals/generate", { method: "POST", body }),
  pushPeriodical: (id) => request(`/api/periodicals/${id}/push`, { method: "POST" }),
  exportPeriodical: (id, fmt) =>
    download(`/api/periodicals/${id}/export?fmt=${fmt}`, `periodical.${fmt}`),
  deletePeriodical: (id) => request(`/api/periodicals/${id}`, { method: "DELETE" }),

  // ---------------- 插件 ----------------
  plugins: (type = "") => request(`/api/plugins${qs({ type })}`),
  syncPlugins: () => request("/api/plugins/sync", { method: "POST" }),
  installPlugin: (source) => request("/api/plugins/install", { method: "POST", body: { source } }),
  togglePlugin: (id, enabled) =>
    request(`/api/plugins/${id}/enable`, { method: "POST", body: { enabled } }),
  pluginConfig: (id, config) =>
    request(`/api/plugins/${id}/config`, { method: "PUT", body: { config } }),
  deletePlugin: (id, removeFiles = false) =>
    request(`/api/plugins/${id}${qs({ remove_files: removeFiles })}`, { method: "DELETE" }),
  testPlugin: (id) => request(`/api/plugins/${id}/test`, { method: "POST" }),
  marketplace: () => request("/api/plugins/marketplace/catalog"),
  installFromMarket: (slug) => request(`/api/plugins/marketplace/${slug}/install`, { method: "POST" }),

  // ---------------- 管理后台 ----------------
  adminUsers: () => request("/api/admin/users"),
  adminUpdateUser: (id, body) => request(`/api/admin/users/${id}`, { method: "PUT", body }),
  adminDeleteUser: (id) => request(`/api/admin/users/${id}`, { method: "DELETE" }),
  adminStats: () => request("/api/admin/stats"),
  adminPushLogs: (params) => request(`/api/admin/push-logs${qs(params)}`),
  adminJobs: () => request("/api/admin/jobs"),
  adminSyncJobs: () => request("/api/admin/jobs/sync", { method: "POST" }),
  adminUsage: (days = 30) => request(`/api/admin/usage${qs({ days })}`),
};

export default api;
