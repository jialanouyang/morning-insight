import { useEffect, useState } from "react";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import zh from "./locales/zh.json";
import en from "./locales/en.json";

export const LANGUAGES = [
  { id: "zh", label: "简体中文", short: "中" },
  { id: "en", label: "English", short: "EN" },
];

const UI_LANG_KEY = "mi_ui_language";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      zh: { translation: zh },
      en: { translation: en },
    },
    fallbackLng: "en",
    supportedLngs: ["zh", "en"],
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: UI_LANG_KEY,
      caches: ["localStorage"],
    },
  });

/** 切换界面语言（同时持久化到 localStorage，供 i18next 检测器读取）。 */
export function setLanguage(lang) {
  const next = LANGUAGES.some((l) => l.id === lang) ? lang : "zh";
  localStorage.setItem(UI_LANG_KEY, next);
  i18n.changeLanguage(next);
}

/** 一键切换：中文 ↔ English。 */
export function toggleLanguage() {
  setLanguage(currentLanguage() === "zh" ? "en" : "zh");
}

/** 读取当前界面语言。 */
export function currentLanguage() {
  const lang = (i18n.language || "zh").split("-")[0];
  return lang === "en" ? "en" : "zh";
}

/** 订阅语言变化的 hook，用于强制重渲染。 */
export function useLanguage() {
  const [lang, setLang] = useState(currentLanguage());
  useEffect(() => {
    const handler = () => setLang(currentLanguage());
    i18n.on("languageChanged", handler);
    return () => i18n.off("languageChanged", handler);
  }, []);
  return lang;
}

export default i18n;
