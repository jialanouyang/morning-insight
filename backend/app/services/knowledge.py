"""知识库（RAG）：历史晨报 / 周月报 / 文章自动入库 → 切片 → 向量化 → 语义检索 → 自然语言问答。

设计说明：
- 默认使用**内置向量检索**（向量以 JSON 存于 `knowledge_chunks`，余弦相似度在进程内计算），
  零额外依赖即可开箱可用，适合中小规模（数万切片）自托管场景。
- 向量化优先使用配置的 Embedding 接口，未配置时降级为内置离线算法（见 `ai.llm.local_embed`）。
- `knowledge_config.vector_store` 预留 chroma / qdrant / pgvector 切换位，
  当前实现统一走内置检索，接口签名保持一致，便于后续替换。
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import llm as llm_mod
from ..ai import processing
from ..models import Article, KnowledgeChunk, PeriodicalReport, Report, utcnow
from ..utils.text import split_text, truncate

logger = logging.getLogger("morning_insight.knowledge")

DEFAULT_TOP_K = 6
MAX_CANDIDATES = 8000
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120


def _embedding_cfg(cfg: dict) -> dict:
    ai = dict(cfg or {})
    knowledge = cfg.get("knowledge_config") or {}
    if knowledge.get("embedding_model"):
        ai["embedding_model"] = knowledge["embedding_model"]
    if knowledge.get("embedding_provider"):
        ai["embedding_provider"] = knowledge["embedding_provider"]
    return ai


def _existing_chunk_count(db: Session, user_id: int, source_type: str, source_id: int) -> int:
    column = {
        "report": KnowledgeChunk.report_id,
        "periodical": KnowledgeChunk.periodical_id,
        "article": KnowledgeChunk.article_id,
    }.get(source_type, KnowledgeChunk.report_id)
    return db.query(KnowledgeChunk).filter(
        KnowledgeChunk.user_id == user_id,
        KnowledgeChunk.source_type == source_type,
        column == source_id,
    ).count()


def _store_chunks(db: Session, user_id: int, *, source_type: str, source_id: int, title: str,
                  text: str, doc_date: str, industry: str, cfg: dict) -> int:
    chunks = split_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        return 0
    vectors, provider = llm_mod.embed_texts(chunks, _embedding_cfg(cfg), db=db, user_id=user_id)
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        row = KnowledgeChunk(
            user_id=user_id, source_type=source_type, title=truncate(title, 500),
            chunk_index=idx, chunk_text=chunk, embedding=vec, embedding_provider=provider,
            doc_date=doc_date, industry=industry,
        )
        if source_type == "report":
            row.report_id = source_id
        elif source_type == "periodical":
            row.periodical_id = source_id
        elif source_type == "article":
            row.article_id = source_id
        db.add(row)
    db.commit()
    return len(chunks)


def ingest_report(db: Session, user_id: int, report: Report, cfg: dict | None = None, *, force: bool = False) -> int:
    if not force and _existing_chunk_count(db, user_id, "report", report.id):
        return 0
    if force:
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.user_id == user_id, KnowledgeChunk.report_id == report.id
        ).delete()
        db.commit()
    return _store_chunks(
        db, user_id, source_type="report", source_id=report.id, title=report.title,
        text=report.content_md or "", doc_date=report.report_date, industry=report.industry or "",
        cfg=cfg or {},
    )


def ingest_periodical(db: Session, user_id: int, item: PeriodicalReport, cfg: dict | None = None, *, force: bool = False) -> int:
    if not force and _existing_chunk_count(db, user_id, "periodical", item.id):
        return 0
    if force:
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.user_id == user_id, KnowledgeChunk.periodical_id == item.id
        ).delete()
        db.commit()
    return _store_chunks(
        db, user_id, source_type="periodical", source_id=item.id, title=item.title,
        text=item.content_md or "", doc_date=item.period_end, industry="", cfg=cfg or {},
    )


def ingest_article(db: Session, user_id: int, article: Article, cfg: dict | None = None) -> int:
    if _existing_chunk_count(db, user_id, "article", article.id):
        return 0
    text = article.raw_content or article.summary or article.title
    if not text:
        return 0
    return _store_chunks(
        db, user_id, source_type="article", source_id=article.id, title=article.title,
        text=f"{article.title}\n{text}", doc_date=(article.published_at or "")[:10],
        industry="", cfg=cfg or {},
    )


def ingest_pending(db: Session, user_id: int, cfg: dict | None = None, limit: int = 30) -> dict:
    """把尚未入库的晨报 / 周月报补进知识库（供「重建索引」与定时任务调用）。"""
    cfg = cfg or {}
    reports = db.scalars(
        select(Report).where(Report.user_id == user_id).order_by(Report.created_at.desc()).limit(limit)
    ).all()
    periodicals = db.scalars(
        select(PeriodicalReport).where(PeriodicalReport.user_id == user_id)
        .order_by(PeriodicalReport.created_at.desc()).limit(limit)
    ).all()
    n_reports = sum(ingest_report(db, user_id, r, cfg) for r in reports)
    n_period = sum(ingest_periodical(db, user_id, p, cfg) for p in periodicals)
    return {"reports": n_reports, "periodicals": n_period}


def reindex(db: Session, user_id: int, cfg: dict, limit: int = 200) -> dict:
    """全量重建索引：清空后可重算（切换 Embedding 模型后需要执行）。"""
    db.query(KnowledgeChunk).filter(KnowledgeChunk.user_id == user_id).delete()
    db.commit()
    reports = db.scalars(
        select(Report).where(Report.user_id == user_id).order_by(Report.created_at.desc()).limit(limit)
    ).all()
    periodicals = db.scalars(
        select(PeriodicalReport).where(PeriodicalReport.user_id == user_id)
        .order_by(PeriodicalReport.created_at.desc()).limit(limit)
    ).all()
    total = 0
    for r in reports:
        total += ingest_report(db, user_id, r, cfg, force=True)
    for p in periodicals:
        total += ingest_periodical(db, user_id, p, cfg, force=True)
    return {"chunks": total, "reports": len(reports), "periodicals": len(periodicals)}


def search(
    db: Session,
    user_id: int,
    query: str,
    cfg: dict | None = None,
    *,
    top_k: int = DEFAULT_TOP_K,
    date_from: str = "",
    date_to: str = "",
    industry: str = "",
    source_types: list[str] | None = None,
) -> list[dict]:
    """语义检索：向量余弦 + 关键词命中加权。"""
    cfg = cfg or {}
    if not (query or "").strip():
        return []

    stmt = select(KnowledgeChunk).where(KnowledgeChunk.user_id == user_id)
    if date_from:
        stmt = stmt.where(KnowledgeChunk.doc_date >= date_from[:10])
    if date_to:
        stmt = stmt.where(KnowledgeChunk.doc_date <= date_to[:10])
    if industry:
        stmt = stmt.where(KnowledgeChunk.industry.contains(industry))
    if source_types:
        stmt = stmt.where(KnowledgeChunk.source_type.in_(source_types))
    rows = db.scalars(stmt.order_by(KnowledgeChunk.id.desc()).limit(MAX_CANDIDATES)).all()
    if not rows:
        return []

    vectors, provider = llm_mod.embed_texts([query], _embedding_cfg(cfg))
    query_vec = vectors[0]
    from ..utils.text import tokenize_for_search

    query_tokens = set(tokenize_for_search(query))

    scored: list[tuple[float, KnowledgeChunk]] = []
    for row in rows:
        if row.embedding and len(row.embedding) == len(query_vec):
            score = llm_mod.cosine(query_vec, row.embedding)
        else:
            score = 0.0
        # 关键词命中加权，避免纯向量在小库上漏掉精确匹配
        if query_tokens:
            chunk_tokens = set(tokenize_for_search(row.chunk_text))
            overlap = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)
            score = score * 0.75 + overlap * 0.25
        scored.append((score, row))

    scored.sort(key=lambda x: -x[0])
    results = []
    for score, row in scored[: max(top_k, 1)]:
        if score <= 0.02:
            continue
        results.append({
            "id": row.id,
            "score": round(score, 4),
            "source_type": row.source_type,
            "report_id": row.report_id,
            "periodical_id": row.periodical_id,
            "title": row.title,
            "doc_date": row.doc_date,
            "industry": row.industry,
            "chunk_text": truncate(row.chunk_text, 1200),
            "chunk_index": row.chunk_index,
        })
    if not results:
        # 全为 0 分时至少返回最相关的前几条，避免「有库但答不出」
        results = [
            {
                "id": r.id, "score": 0.0, "source_type": r.source_type, "report_id": r.report_id,
                "periodical_id": r.periodical_id, "title": r.title, "doc_date": r.doc_date,
                "industry": r.industry, "chunk_text": truncate(r.chunk_text, 1200), "chunk_index": r.chunk_index,
            }
            for _, r in scored[: min(top_k, 3)]
        ]
    return results


def answer(
    db: Session,
    user_id: int,
    question: str,
    cfg: dict,
    *,
    top_k: int = DEFAULT_TOP_K,
    date_from: str = "",
    date_to: str = "",
    industry: str = "",
    history: list[dict] | None = None,
) -> dict:
    """自然语言问答，返回答案与引用来源。"""
    chunks = search(
        db, user_id, question, cfg, top_k=top_k,
        date_from=date_from, date_to=date_to, industry=industry,
    )
    if not chunks:
        return {"answer": "知识库中还没有相关内容。先去「晨报历史」生成几份晨报，或点击「重建索引」。", "sources": []}
    text = processing.answer_question(question, chunks, cfg, history=history, db=db, user_id=user_id)
    sources = [
        {
            "index": i + 1,
            "title": c["title"],
            "doc_date": c["doc_date"],
            "source_type": c["source_type"],
            "report_id": c["report_id"],
            "periodical_id": c["periodical_id"],
            "score": c["score"],
            "excerpt": truncate(c["chunk_text"], 240),
        }
        for i, c in enumerate(chunks)
    ]
    return {"answer": text, "sources": sources}


def stats(db: Session, user_id: int) -> dict:
    total = db.query(KnowledgeChunk).filter(KnowledgeChunk.user_id == user_id).count()
    rows = db.query(KnowledgeChunk.source_type).filter(KnowledgeChunk.user_id == user_id).all()
    by_type: dict[str, int] = {}
    for (stype,) in rows:
        by_type[stype] = by_type.get(stype, 0) + 1
    providers = {
        p for (p,) in db.query(KnowledgeChunk.embedding_provider)
        .filter(KnowledgeChunk.user_id == user_id).distinct().all() if p
    }
    latest = db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.user_id == user_id)
        .order_by(KnowledgeChunk.id.desc()).limit(1)
    ).first()
    return {
        "chunks": total,
        "by_type": by_type,
        "providers": sorted(providers),
        "latest_at": latest.created_at.isoformat() if latest and latest.created_at else "",
    }
