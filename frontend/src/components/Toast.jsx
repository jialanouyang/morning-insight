/* 全局轻提示（Toast）：任何组件通过 useToast() 弹出一条消息。 */
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

const ToastContext = createContext(null);

let seq = 0;

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const timers = useRef({});

  const remove = useCallback((id) => {
    setItems((list) => list.filter((t) => t.id !== id));
    clearTimeout(timers.current[id]);
    delete timers.current[id];
  }, []);

  const push = useCallback(
    (kind, title, body, duration = 3600) => {
      const id = ++seq;
      setItems((list) => [...list.slice(-4), { id, kind, title, body }]);
      timers.current[id] = setTimeout(() => remove(id), duration);
      return id;
    },
    [remove]
  );

  const value = useMemo(
    () => ({
      ok: (title, body) => push("ok", title, body),
      err: (title, body) => push("err", title, body, 7000),
      info: (title, body) => push("info", title, body),
      push,
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {items.length > 0 && (
        <div className="toast-wrap">
          {items.map((t) => (
            <div key={t.id} className={`toast toast-${t.kind}`} onClick={() => remove(t.id)}>
              {t.title && <div className="toast-title">{t.title}</div>}
              {t.body && <div className="toast-body">{t.body}</div>}
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (ctx) return ctx;
  // 未挂载 Provider 时的兜底，避免组件直接崩溃
  return {
    ok: (t, b) => console.log("[ok]", t, b || ""),
    err: (t, b) => console.warn("[err]", t, b || ""),
    info: (t, b) => console.log("[info]", t, b || ""),
    push: () => 0,
  };
}
