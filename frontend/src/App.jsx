import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import api, { clearToken, getToken } from "./api";
import Logo from "./components/Logo";
import { ConfirmProvider, Seg } from "./components/ui";
import { ToastProvider } from "./components/Toast";
import { LANGUAGES, setLanguage, useLanguage } from "./i18n";
import { invalidateMe, useMe } from "./store";

import About from "./pages/About";
import Admin from "./pages/Admin";
import Alerts from "./pages/Alerts";
import Competitors from "./pages/Competitors";
import Dashboard from "./pages/Dashboard";
import Knowledge from "./pages/Knowledge";
import Login from "./pages/Login";
import Periodicals from "./pages/Periodicals";
import Plugins from "./pages/Plugins";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";

function RequireAuth({ children }) {
  const location = useLocation();
  if (!getToken()) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

function LanguageSwitch() {
  const lang = useLanguage();
  return (
    <Seg
      items={LANGUAGES.map((l) => ({ value: l.id, label: l.short }))}
      value={lang}
      onChange={(v) => {
        setLanguage(v);
        // 语言切换同步保存到用户配置：界面语言与晨报语言一起生效
        if (getToken()) {
          api.saveConfig({ ui_language: v, report_language: v }).catch(() => {});
        }
      }}
    />
  );
}

function Layout({ children }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const me = useMe();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    document.title = t("app.full");
  }, [t]);

  const NAV = [
    {
      group: t("nav.groupContent"),
      items: [
        { to: "/", icon: "◈", label: t("nav.dashboard"), end: true },
        { to: "/reports", icon: "▤", label: t("nav.reports") },
        { to: "/knowledge", icon: "⌕", label: t("nav.knowledge") },
        { to: "/periodicals", icon: "◷", label: t("nav.periodicals") },
      ],
    },
    {
      group: t("nav.groupGrowth"),
      items: [
        { to: "/competitors", icon: "◎", label: t("nav.competitors") },
        { to: "/alerts", icon: "⚑", label: t("nav.alerts") },
        { to: "/plugins", icon: "⊙", label: t("nav.plugins") },
      ],
    },
    {
      group: t("nav.groupSystem"),
      items: [
        { to: "/settings", icon: "⚙", label: t("nav.settings") },
        ...(me?.role === "admin" ? [{ to: "/admin", icon: "⛨", label: t("nav.admin") }] : []),
        { to: "/about", icon: "ⓘ", label: t("nav.about") },
      ],
    },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <Logo size={30} />
          <div>
            <div className="brand-name">{t("app.name")}</div>
            <div className="brand-sub">Morning Insight</div>
          </div>
        </div>

        {NAV.map((g) => (
          <nav className="nav-group" key={g.group}>
            <div className="nav-group-title">{g.group}</div>
            {g.items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
              >
                <span className="nav-icon">{it.icon}</span>
                <span>{it.label}</span>
              </NavLink>
            ))}
          </nav>
        ))}

        <div className="sidebar-foot">
          <div className="sidebar-user">
            {me?.display_name || me?.email || "—"}
            <div style={{ marginTop: 6 }}>
              <LanguageSwitch />
            </div>
          </div>
          <button
            className="nav-item"
            onClick={() => {
              clearToken();
              invalidateMe();
              navigate("/login");
            }}
          >
            <span className="nav-icon">⏻</span>
            <span>{t("nav.logout")}</span>
          </button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

const PAGE = (Component) => (
  <RequireAuth>
    <Layout>
      <Component />
    </Layout>
  </RequireAuth>
);

export default function App() {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={PAGE(Dashboard)} />
          <Route path="/reports" element={PAGE(Reports)} />
          <Route path="/knowledge" element={PAGE(Knowledge)} />
          <Route path="/periodicals" element={PAGE(Periodicals)} />
          <Route path="/competitors" element={PAGE(Competitors)} />
          <Route path="/alerts" element={PAGE(Alerts)} />
          <Route path="/plugins" element={PAGE(Plugins)} />
          <Route path="/settings" element={PAGE(Settings)} />
          <Route path="/admin" element={PAGE(Admin)} />
          <Route path="/about" element={PAGE(About)} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ConfirmProvider>
    </ToastProvider>
  );
}
