"""知识库路由：语义检索 / 自然语言问答 / 重建索引 / 统计。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services import knowledge
from ..services.pipeline import config_payload, ensure_default_config

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class AskIn(BaseModel):
    question: str
    top_k: int | None = None
    date_from: str = ""
    date_to: str = ""
    industry: str = ""
    history: list[dict] | None = None


@router.post("/ask")
def ask(data: AskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """自然语言问答，返回答案与引用来源。"""
    question = (data.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="请输入问题")
    cfg = ensure_default_config(db, user.id)
    payload = config_payload(cfg)
    knowledge_cfg = cfg.knowledge_config or {}
    if not (cfg.ai_config or {}).get("base_url"):
        raise HTTPException(status_code=400, detail="问答需要 AI 模型，请先在「设置 → AI 模型」配置 API 地址与密钥")
    try:
        result = knowledge.answer(
            db, user.id, question, payload,
            top_k=int(data.top_k or knowledge_cfg.get("top_k") or 6),
            date_from=data.date_from, date_to=data.date_to, industry=data.industry,
            history=data.history,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"问答失败：{exc}")
    return result


class SearchIn(BaseModel):
    query: str
    top_k: int = 10
    date_from: str = ""
    date_to: str = ""
    industry: str = ""
    source_types: list[str] | None = None


@router.post("/search")
def search(data: SearchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """仅检索片段，不调用大模型（用于快速定位）。"""
    cfg = ensure_default_config(db, user.id)
    hits = knowledge.search(
        db, user.id, data.query, config_payload(cfg), top_k=data.top_k,
        date_from=data.date_from, date_to=data.date_to, industry=data.industry,
        source_types=data.source_types,
    )
    return {"count": len(hits), "items": hits}


@router.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return knowledge.stats(db, user.id)


@router.post("/ingest")
def ingest(limit: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """把尚未入库的晨报 / 周月报补进知识库。"""
    cfg = ensure_default_config(db, user.id)
    result = knowledge.ingest_pending(db, user.id, config_payload(cfg), limit=limit)
    return {"ok": True, **result, "stats": knowledge.stats(db, user.id)}


@router.post("/reindex")
def reindex(limit: int = 200, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """全量重建索引（切换 Embedding 模型后需要执行）。"""
    cfg = ensure_default_config(db, user.id)
    try:
        result = knowledge.reindex(db, user.id, config_payload(cfg), limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"重建索引失败：{exc}")
    return {"ok": True, **result, "stats": knowledge.stats(db, user.id)}


@router.delete("")
def clear(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import KnowledgeChunk

    db.query(KnowledgeChunk).filter(KnowledgeChunk.user_id == user.id).delete()
    db.commit()
    return {"ok": True}
