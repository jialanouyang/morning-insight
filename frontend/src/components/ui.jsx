/* 通用 UI 组件集合：表单控件、空态、加载、模态、提示条、标签等。
   全站样式统一来自 styles.css，组件只负责结构与交互。 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";

/* ---------------------------------- 表单 ---------------------------------- */

export function Field({ label, hint, required, tip, children, className = "" }) {
  return (
    <div className={`field ${className}`}>
      {label && (
        <label className="field-label">
          {label}
          {required && <span className="field-req">*</span>}
          {tip && <span className="field-label-tip">{tip}</span>}
        </label>
      )}
      {children}
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  );
}

export function Input({ value, onChange, ...rest }) {
  return (
    <input
      className="input"
      value={value ?? ""}
      onChange={(e) => onChange?.(e.target.value)}
      {...rest}
    />
  );
}

export function Textarea({ value, onChange, rows, className = "", ...rest }) {
  return (
    <textarea
      className={`textarea ${className}`}
      value={value ?? ""}
      rows={rows}
      onChange={(e) => onChange?.(e.target.value)}
      {...rest}
    />
  );
}

export function Select({ value, onChange, options = [], placeholder, ...rest }) {
  return (
    <select
      className="select"
      value={value ?? ""}
      onChange={(e) => onChange?.(e.target.value)}
      {...rest}
    >
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => {
        const val = typeof o === "string" ? o : o.value;
        const label = typeof o === "string" ? o : o.label;
        return (
          <option key={String(val)} value={val}>
            {label}
          </option>
        );
      })}
    </select>
  );
}

export function Switch({ checked, onChange, label, disabled }) {
  return (
    <label className="switch">
      <input
        type="checkbox"
        checked={!!checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
      />
      <span className="switch-track" />
      {label && <span className="switch-label">{label}</span>}
    </label>
  );
}

/** 标签输入：回车 / 逗号 / 失焦即确认，可删除 */
export function TagInput({ value = [], onChange, placeholder = "", splitComma = true }) {
  const [draft, setDraft] = useState("");

  const commit = (raw) => {
    const parts = (splitComma ? String(raw).split(/[,，]/) : [String(raw)])
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.length) return;
    const next = [...value];
    parts.forEach((p) => {
      if (!next.includes(p)) next.push(p);
    });
    onChange?.(next);
    setDraft("");
  };

  const remove = (idx) => onChange?.(value.filter((_, i) => i !== idx));

  return (
    <div className="tag-input">
      {value.map((tag, i) => (
        <span className="tag" key={`${tag}-${i}`}>
          {tag}
          <span className="tag-x" onClick={() => remove(i)}>
            ×
          </span>
        </span>
      ))}
      <input
        value={draft}
        placeholder={value.length ? "" : placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || (splitComma && (e.key === "," || e.key === "，"))) {
            e.preventDefault();
            commit(draft);
          } else if (e.key === "Backspace" && !draft && value.length) {
            remove(value.length - 1);
          }
        }}
        onBlur={() => draft && commit(draft)}
        onPaste={(e) => {
          const text = e.clipboardData?.getData("text");
          if (text && /[,，\n]/.test(text)) {
            e.preventDefault();
            commit(text);
          }
        }}
      />
    </div>
  );
}

/** 复选卡片：用于关注点 / 角色 / 渠道等「勾选即生效」的场景 */
export function OptionCard({ checked, onChange, name, description, right, children }) {
  return (
    <label className={`opt${checked ? " on" : ""}`}>
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange?.(e.target.checked)} />
      <span className="opt-body">
        <span className="row-between" style={{ alignItems: "flex-start" }}>
          <span className="opt-name">{name}</span>
          {right}
        </span>
        {description && <div className="opt-desc">{description}</div>}
        {children}
      </span>
    </label>
  );
}

/* ---------------------------------- 反馈 ---------------------------------- */

export function Loading({ text = "加载中…" }) {
  return (
    <div className="loading-box">
      <span className="spinner" />
      <span>{text}</span>
    </div>
  );
}

export function Empty({ icon = "○", title, desc, action }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      {title && <div className="empty-title">{title}</div>}
      {desc && <div className="empty-desc">{desc}</div>}
      {action && <div className="mt-14">{action}</div>}
    </div>
  );
}

export function AlertBar({ kind = "info", children, onClose, action }) {
  return (
    <div className={`alert-bar alert-${kind}`}>
      <div style={{ flex: 1 }}>{children}</div>
      {action}
      {onClose && (
        <button className="alert-close" onClick={onClose} aria-label="关闭">
          ×
        </button>
      )}
    </div>
  );
}

export function InlineError({ children }) {
  if (!children) return null;
  return <div className="alert-bar alert-danger">{children}</div>;
}

/* ---------------------------------- 结构 ---------------------------------- */

export function PageHead({ title, subtitle, children }) {
  return (
    <div className="page-head">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <div className="page-sub">{subtitle}</div>}
      </div>
      {children && <div className="page-head-actions">{children}</div>}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, className = "", tight, ...rest }) {
  return (
    <section className={`card${tight ? " card-tight" : ""} ${className}`} {...rest}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <div className="card-title">{title}</div>}
            {subtitle && <div className="card-sub">{subtitle}</div>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, accent }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${accent ? " stat-accent" : ""}`}>{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function Tag({ kind = "", children, title }) {
  return (
    <span className={`tag${kind ? ` tag-${kind}` : ""}`} title={title}>
      {children}
    </span>
  );
}

export function Dot({ kind = "" }) {
  return <span className={`dot${kind ? ` dot-${kind}` : ""}`} />;
}

export function Tabs({ items, value, onChange }) {
  return (
    <div className="tabs">
      {items.map((it) => (
        <button
          key={it.key}
          className={`tab${value === it.key ? " active" : ""}`}
          onClick={() => onChange(it.key)}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function Seg({ items, value, onChange }) {
  return (
    <div className="seg">
      {items.map((it) => (
        <button
          key={it.value}
          className={`seg-item${value === it.value ? " active" : ""}`}
          onClick={() => onChange(it.value)}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function Modal({ title, onClose, children, footer, size = "" }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-mask" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal${size ? ` modal-${size}` : ""}`}>
        <div className="modal-head">
          <div className="modal-title">{title}</div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

/** 简易折叠面板。
 *  注意：标题区渲染为独立的 button，extra（常含开关）放在同级，
 *  避免「按钮里嵌交互控件」导致的 HTML 嵌套错误与点击穿透。
 */
export function Accordion({ title, extra, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <div className="accordion-head">
        <button
          type="button"
          className="accordion-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          <span style={{ width: 12, color: "var(--text-3)" }}>{open ? "▾" : "▸"}</span>
          <span style={{ flex: 1, textAlign: "left" }}>{title}</span>
        </button>
        {extra && <div className="accordion-extra">{extra}</div>}
      </div>
      {open && <div className="accordion-body">{children}</div>}
    </div>
  );
}

/** 确认对话框 Hook：const confirm = useConfirm(); if (await confirm({...})) ... */
const ConfirmContext = createContext(null);

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null);

  const confirm = (options) =>
    new Promise((resolve) => {
      setState({ ...(typeof options === "string" ? { message: options } : options), resolve });
    });

  const value = useMemo(() => confirm, []);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {state && (
        <Modal
          title={state.title || "请确认"}
          size="sm"
          onClose={() => {
            state.resolve(false);
            setState(null);
          }}
          footer={
            <>
              <button
                className="btn"
                onClick={() => {
                  state.resolve(false);
                  setState(null);
                }}
              >
                取消
              </button>
              <button
                className={`btn ${state.danger ? "btn-danger" : "btn-primary"}`}
                onClick={() => {
                  state.resolve(true);
                  setState(null);
                }}
              >
                {state.confirmText || "确定"}
              </button>
            </>
          }
        >
          <div style={{ whiteSpace: "pre-wrap", fontSize: 13.5 }}>{state.message}</div>
        </Modal>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  return ctx || (async () => window.confirm("确定执行该操作？"));
}
