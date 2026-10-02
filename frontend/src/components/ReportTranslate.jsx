/* 晨报一键翻译：语言检测、加载 / 失败 / 重试状态、原文 ⇄ 译文切换。
   首页（今日晨报 / 最近晨报 / 预览）与晨报详情页共用，保证交互一致。 */
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import api from "../api";
import { useLanguage } from "../i18n";

/** 前端兜底语言检测：CJK 字符占比高视为中文，否则视为英文。 */
export function detectReportLang(text = "") {
  const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const letters = (text.match(/[a-zA-Z]/g) || []).length;
  if (!cjk && !letters) return "";
  return cjk * 3 >= letters + cjk ? "zh" : "en";
}

/**
 * 单份晨报的翻译状态机。
 * - needsTranslate：晨报语言与界面语言不一致时才提供翻译；
 * - view(field)：当前应展示的字段（原文或译文），支持 title / excerpt / content_md；
 * - 界面语言切换后旧译文自动失效，可重新翻译。
 */
export function useReportTranslate(report) {
  const { t } = useTranslation();
  const uiLang = useLanguage();

  const [result, setResult] = useState(null); // { title, content_md, target_lang }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showTranslated, setShowTranslated] = useState(false);

  const sample = `${report?.title || ""} ${(report?.content_md || report?.excerpt || "").slice(0, 300)}`;
  const lang = detectReportLang(sample);
  const needsTranslate = !!report && !!lang && lang !== uiLang;

  // 切换界面语言后，已有译文不再匹配新目标语言 → 失效并回到原文
  useEffect(() => {
    if (result && result.target_lang !== uiLang) {
      setResult(null);
      setShowTranslated(false);
      setError("");
    }
  }, [uiLang, result]);

  const translate = useCallback(async () => {
    if (!report || loading) return;
    if (result) {
      setShowTranslated((v) => !v);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await api.translateReport(report.id, uiLang);
      setResult(res);
      setShowTranslated(true);
    } catch (e) {
      setError(e.message || t("translate.failed"));
    } finally {
      setLoading(false);
    }
  }, [report, loading, result, uiLang, t]);

  const view = useCallback(
    (field) => {
      if (showTranslated && result) {
        if (field === "excerpt") return _excerpt(result.content_md || "");
        if (result[field]) return result[field];
      }
      return report?.[field] ?? "";
    },
    [report, result, showTranslated]
  );

  return {
    lang,
    uiLang,
    needsTranslate,
    loading,
    error,
    hasResult: !!result,
    showingTranslated: !!result && showTranslated,
    translate, // 未翻译时触发翻译；已翻译时切换原文 ⇄ 译文
    retry: translate,
    view,
  };
}

/** 列表摘要：译文取正文前 180 字符，与后端 excerpt 口径一致。 */
function _excerpt(text) {
  return text.length > 180 ? `${text.slice(0, 180)}…` : text;
}

/** 显眼的翻译按钮：翻译 / 翻译中… / 失败·重试 / 显示原文 / 显示译文 五态。 */
export function TranslateButton({ tr, primary = false, className = "" }) {
  const { t } = useTranslation();
  if (!tr?.needsTranslate) return null;

  let label = t("translate.button");
  if (tr.loading) label = t("translate.translating");
  else if (tr.error) label = t("translate.failedRetry");
  else if (tr.hasResult) label = tr.showingTranslated ? t("translate.showOriginal") : t("translate.showTranslated");

  return (
    <button
      type="button"
      className={`btn btn-sm ${primary ? "btn-accent" : ""} ${className}`}
      onClick={tr.translate}
      disabled={tr.loading}
      title={tr.error ? tr.error : t("translate.hint")}
    >
      {tr.loading && <span className="spinner" />}
      <span aria-hidden="true" style={{ marginRight: 4 }}>
        ⇄
      </span>
      {label}
    </button>
  );
}

/** 翻译失败提示条（含重试），详情视图使用；列表视图用按钮自身的失败态。 */
export function TranslateErrorBar({ tr }) {
  const { t } = useTranslation();
  if (!tr?.error || tr.loading) return null;
  return (
    <div className="alert-bar alert-danger" style={{ marginTop: 10 }}>
      <div style={{ flex: 1 }}>
        {t("translate.failed")}：{tr.error}
      </div>
      <button className="btn btn-sm" onClick={tr.retry}>
        {t("translate.retry")}
      </button>
    </div>
  );
}
