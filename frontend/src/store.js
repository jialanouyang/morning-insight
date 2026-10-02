/* 轻量共享状态：元信息、当前用户、用户配置。
   元信息与用户信息在会话内缓存，避免每个页面重复请求。 */
import { useCallback, useEffect, useState } from "react";
import api, { getToken } from "./api";

let metaCache = null;
let metaPromise = null;
let meCache = null;
let mePromise = null;

export function invalidateMe() {
  meCache = null;
  mePromise = null;
}

/** 后端内置目录（关注点 / 角色 / 模板 / 渠道 / 源清单等），一次加载全程复用。 */
export function useMeta() {
  const [meta, setMeta] = useState(metaCache);
  useEffect(() => {
    if (metaCache) {
      setMeta(metaCache);
      return;
    }
    if (!metaPromise) metaPromise = api.meta().catch(() => null);
    let alive = true;
    metaPromise.then((m) => {
      if (m) metaCache = m;
      if (alive) setMeta(m);
    });
    return () => {
      alive = false;
    };
  }, []);
  return meta;
}

/** 当前登录用户。 */
export function useMe() {
  const [me, setMe] = useState(meCache);
  useEffect(() => {
    if (!getToken()) return;
    if (meCache) {
      setMe(meCache);
      return;
    }
    if (!mePromise) mePromise = api.me().catch(() => null);
    let alive = true;
    mePromise.then((u) => {
      if (u) meCache = u;
      if (alive) setMe(u);
    });
    return () => {
      alive = false;
    };
  }, []);
  return me;
}

/** 用户晨报配置（可读写、可局部更新）。 */
export function useConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getConfig();
      setConfig(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  /** 提交配置（只传需要改动的字段即可）。 */
  const save = useCallback(
    async (patch) => {
      const result = await api.saveConfig(patch);
      setConfig((prev) => {
        if (!prev) return prev;
        const next = { ...prev, ...patch };
        if (patch.ai_config) {
          next.ai_config = { ...(prev.ai_config || {}), ...patch.ai_config };
        }
        if (patch.push_config) {
          const merged = { ...(prev.push_config || {}) };
          Object.entries(patch.push_config).forEach(([k, v]) => {
            merged[k] = { ...(merged[k] || {}), ...(v || {}) };
          });
          next.push_config = merged;
        }
        return next;
      });
      return result;
    },
    []
  );

  return { config, setConfig, loading, error, reload, save };
}

/** 便捷：把后端返回的错误统一弹给用户 */
export function useAsync() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = useCallback(async (fn) => {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, setError, run };
}
