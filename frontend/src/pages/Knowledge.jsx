import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import api from "../api";
import Markdown from "../components/Markdown";
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
  Stat,
  Tag,
  useConfirm,
} from "../components/ui";

export default function Knowledge() {
  const { t } = useTranslation();
  const toast = useToast();
  const confirm = useConfirm();

  const [stats, setStats] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState({ date_from: "", date_to: "", industry: "" });
  const [showFilters, setShowFilters] = useState(false);
  const [hits, setHits] = useState(null);
  const [searching, setSearching] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [indexBusy, setIndexBusy] = useState("");
  const bottomRef = useRef(null);

  const loadStats = useCallback(async () => {
    try {
      setStats(await api.knowledgeStats());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const ask = async (text) => {
    const q = (text ?? question).trim();
    if (!q || busy) return;
    setQuestion("");
    const history = messages
      .filter((m) => m.role)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setBusy(true);
    try {
      const res = await api.knowledgeAsk({ question: q, ...filters, history });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, sources: res.sources || [] },
      ]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: `⚠️ ${e.message}`, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  const doSearch = async () => {
    if (!filters.query && !question.trim()) return;
    setSearching(true);
    try {
      const res = await api.knowledgeSearch({ query: question.trim() || filters.query, ...filters, top_k: 10 });
      setHits(res.items || []);
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setSearching(false);
    }
  };

  const ingest = async () => {
    setIndexBusy("ingest");
    try {
      const res = await api.knowledgeIngest(50);
      toast.ok(t("common.success"), `${res.added ?? 0} / ${res.scanned ?? 0}`);
      await loadStats();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setIndexBusy("");
    }
  };

  const reindex = async () => {
    if (!(await confirm({ message: t("settings.knowledgeHint") + "\n\n" + t("knowledge.reindexHint") }))) return;
    setIndexBusy("reindex");
    try {
      await api.knowledgeReindex(200);
      toast.ok(t("knowledge.reindexed"));
      await loadStats();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    } finally {
      setIndexBusy("");
    }
  };

  const clear = async () => {
    if (!(await confirm({ message: t("common.deleteConfirm"), danger: true, confirmText: t("common.delete") }))) return;
    try {
      await api.knowledgeClear();
      toast.ok(t("common.success"));
      await loadStats();
    } catch (e) {
      toast.err(t("common.failed"), e.message);
    }
  };

  return (
    <>
      <PageHead title={t("knowledge.title")} subtitle={t("knowledge.subtitle")}>
        <button className="btn" onClick={ingest} disabled={!!indexBusy}>
          {indexBusy === "ingest" && <span className="spinner" />}
          {t("knowledge.ingest")}
        </button>
        <button className="btn" onClick={reindex} disabled={!!indexBusy}>
          {indexBusy === "reindex" && <span className="spinner" />}
          {t("knowledge.reindex")}
        </button>
        <button className="btn btn-ghost" onClick={() => setShowSearch(true)}>
          {t("common.search")}
        </button>
        <button className="btn btn-danger" onClick={clear}>
          {t("knowledge.clear")}
        </button>
      </PageHead>

      <div className="grid grid-4 mb-14">
        <Stat label={t("knowledge.chunks")} value={stats?.chunks ?? "—"} />
        <Stat
          label={t("knowledge.byType")}
          value={Object.keys(stats?.by_type || {}).length || "—"}
          hint={Object.entries(stats?.by_type || {})
            .map(([k, v]) => `${k}:${v}`)
            .join("  ")}
        />
        <Stat
          label={t("knowledge.providers")}
          value={stats?.providers?.length ? stats.providers.join(", ") : "builtin"}
        />
        <Stat
          label={t("common.time")}
          value={stats?.latest_at ? stats.latest_at.slice(5, 16).replace("T", " ") : "—"}
        />
      </div>

      <Card
        title={t("knowledge.title")}
        actions={
          <>
            <button className="btn btn-sm btn-ghost" onClick={() => setShowFilters((v) => !v)}>
              {t("knowledge.filters")}
            </button>
            {messages.length > 0 && (
              <button className="btn btn-sm btn-ghost" onClick={() => setMessages([])}>
                {t("common.close")}
              </button>
            )}
          </>
        }
      >
        {showFilters && (
          <div className="grid grid-3 mb-14">
            <Field label={t("knowledge.industry")} className="mb-0">
              <Input value={filters.industry} onChange={(v) => setFilters({ ...filters, industry: v })} />
            </Field>
            <Field label={t("reports.dateFrom")} className="mb-0">
              <Input
                type="date"
                value={filters.date_from}
                onChange={(v) => setFilters({ ...filters, date_from: v })}
              />
            </Field>
            <Field label={t("reports.dateTo")} className="mb-0">
              <Input
                type="date"
                value={filters.date_to}
                onChange={(v) => setFilters({ ...filters, date_to: v })}
              />
            </Field>
          </div>
        )}

        {messages.length === 0 && !busy ? (
          <Empty
            icon="⌕"
            title={t("knowledge.placeholder")}
            desc={t("knowledge.subtitle")}
            action={
              <div className="col" style={{ alignItems: "center" }}>
                {["example1", "example2", "example3"].map((k) => (
                  <button key={k} className="btn btn-sm" onClick={() => ask(t(`knowledge.${k}`))}>
                    {t(`knowledge.${k}`)}
                  </button>
                ))}
              </div>
            }
          />
        ) : (
          <div className="chat">
            {messages.map((m, i) => (
              <div className={`bubble ${m.role === "user" ? "user" : ""}`} key={i}>
                <div className="bubble-avatar">{m.role === "user" ? "我" : "析"}</div>
                <div className="bubble-body">
                  <div className="bubble-role">
                    {m.role === "user" ? t("login.displayName") : "晨析"}
                  </div>
                  <div className="bubble-content">
                    {m.role === "user" ? (
                      <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                    ) : (
                      <Markdown>{m.content}</Markdown>
                    )}
                    {m.sources?.length > 0 && (
                      <div className="mt-14">
                        <div className="fs-12 text-3 mb-8">
                          <b>{t("knowledge.sources")}</b>
                        </div>
                        {m.sources.map((s) => (
                          <div className="cite" key={s.index}>
                            <div className="cite-idx">{s.index}</div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div className="row-between" style={{ alignItems: "baseline" }}>
                                <b>{s.title}</b>
                                <span className="text-3 fs-12 nowrap">{s.score}</span>
                              </div>
                              <div className="text-3 fs-12">
                                {s.doc_date} · <Tag>{s.source_type}</Tag>
                              </div>
                              <div className="mt-8 text-2">{s.excerpt}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {busy && (
              <div className="bubble">
                <div className="bubble-avatar">析</div>
                <div className="bubble-body">
                  <div className="bubble-role">晨析</div>
                  <div className="bubble-content row">
                    <span className="spinner" />
                    <span className="text-3">{t("knowledge.asking")}</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}

        <div className="inline-form mt-14">
          <Input
            placeholder={t("knowledge.placeholder")}
            value={question}
            onChange={setQuestion}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask();
              }
            }}
          />
          <button className="btn" onClick={doSearch} disabled={searching}>
            {searching && <span className="spinner" />}
            {t("common.search")}
          </button>
          <button className="btn btn-primary" onClick={() => ask()} disabled={busy || !question.trim()}>
            {busy && <span className="spinner" />}
            {t("knowledge.ask")}
          </button>
        </div>
      </Card>

      {showSearch && (
        <Modal title={t("common.search")} size="lg" onClose={() => setShowSearch(false)}>
          <div className="inline-form mb-14">
            <Input
              placeholder={t("knowledge.placeholder")}
              value={question}
              onChange={setQuestion}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
            />
            <button className="btn btn-primary" onClick={doSearch} disabled={searching}>
              {searching && <span className="spinner" />}
              {t("common.search")}
            </button>
          </div>
          {hits === null ? (
            <Empty title={t("knowledge.subtitle")} />
          ) : hits.length === 0 ? (
            <Empty title={t("common.empty")} />
          ) : (
            hits.map((h) => (
              <div className="cite" key={h.id}>
                <div className="cite-idx">{h.score}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b>{h.title}</b>
                  <div className="text-3 fs-12">
                    {h.doc_date} · <Tag>{h.source_type}</Tag>
                  </div>
                  <div className="mt-8 text-2">{h.chunk_text}</div>
                </div>
              </div>
            ))
          )}
        </Modal>
      )}

      {stats?.chunks === 0 && (
        <AlertBar kind="info">{t("knowledge.reindexHint")}</AlertBar>
      )}
    </>
  );
}
