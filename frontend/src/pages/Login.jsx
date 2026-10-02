import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import api, { setToken } from "../api";
import Logo from "../components/Logo";
import { AlertBar, Field, Input, Seg } from "../components/ui";
import { LANGUAGES, setLanguage, useLanguage } from "../i18n";

export default function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const lang = useLanguage();

  const [mode, setMode] = useState("login");
  const [status, setStatus] = useState({ has_user: true, allow_registration: true });
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .authStatus()
      .then((s) => {
        setStatus(s);
        // 全新部署、尚未创建管理员时，直接引导到注册
        if (!s.has_user) setMode("register");
      })
      .catch(() => {});
  }, []);

  const registerClosed = mode === "register" && status.has_user && !status.allow_registration;

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.email.trim() || !form.password) {
      setError("请填写邮箱与密码");
      return;
    }
    setBusy(true);
    try {
      const payload =
        mode === "login"
          ? { email: form.email.trim(), password: form.password, ui_language: lang }
          : {
              email: form.email.trim(),
              password: form.password,
              display_name: form.display_name.trim(),
              ui_language: lang,
            };
      const data = mode === "login" ? await api.login(payload) : await api.register(payload);
      setToken(data.token);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-brand">
          <Logo size={54} />
          <div className="login-title">{t("app.name")}</div>
          <div className="login-sub">{t("login.subtitle")}</div>
        </div>

        {!status.has_user && (
          <AlertBar kind="info">
            <b>{t("login.firstRun")}</b>
          </AlertBar>
        )}
        {registerClosed && <AlertBar kind="warn">{t("login.registerClosed")}</AlertBar>}
        {error && (
          <AlertBar kind="danger" onClose={() => setError("")}>
            {error}
          </AlertBar>
        )}

        <form onSubmit={submit}>
          <Field label={t("login.email")} required>
            <Input
              type="email"
              autoComplete="username"
              placeholder="you@example.com"
              value={form.email}
              onChange={(v) => setForm({ ...form, email: v })}
            />
          </Field>

          {mode === "register" && (
            <Field label={t("login.displayName")} tip={t("common.optional")}>
              <Input
                value={form.display_name}
                onChange={(v) => setForm({ ...form, display_name: v })}
              />
            </Field>
          )}

          <Field
            label={t("login.password")}
            required
            hint={mode === "register" ? t("login.passwordHint") : ""}
          >
            <Input
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={form.password}
              onChange={(v) => setForm({ ...form, password: v })}
            />
          </Field>

          <button
            className="btn btn-primary btn-block"
            type="submit"
            disabled={busy || registerClosed}
          >
            {busy && <span className="spinner" />}
            {mode === "login" ? t("login.signIn") : t("login.signUp")}
          </button>
        </form>

        <div className="row-between mt-14">
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={() => {
              setError("");
              setMode(mode === "login" ? "register" : "login");
            }}
          >
            {mode === "login" ? t("login.toSignUp") : t("login.toSignIn")}
          </button>
          <Seg
            items={LANGUAGES.map((l) => ({ value: l.id, label: l.short }))}
            value={lang}
            onChange={setLanguage}
          />
        </div>
      </div>
    </div>
  );
}
