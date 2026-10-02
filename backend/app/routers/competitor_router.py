"""动态追踪路由：关注对象 CRUD、事件时间线、多对象对比、立即扫描。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Article, Competitor, User
from ..security import get_current_user
from ..services import competitor as competitor_service
from ..services.pipeline import config_payload, ensure_default_config

router = APIRouter(prefix="/api/competitors", tags=["competitors"])


class CompetitorIn(BaseModel):
    name: str
    type: str = "company"
    keywords: list[str] | None = None
    level: str = "normal"
    notes: str = ""
    enabled: bool = True


@router.get("")
def list_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Competitor).where(Competitor.user_id == user.id).order_by(Competitor.level.desc(), Competitor.id.desc())
    ).all()
    return [
        {"id": r.id, "name": r.name, "type": r.type, "keywords": r.keywords or [],
         "level": r.level, "notes": r.notes, "enabled": bool(r.enabled),
         "last_seen_at": r.last_seen_at,
         "created_at": r.created_at.isoformat() if r.created_at else ""}
        for r in rows
    ]


def _get_owned(db: Session, user_id: int, item_id: int) -> Competitor:
    row = db.get(Competitor, item_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="追踪对象不存在")
    return row


@router.post("")
def create(data: CompetitorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    exists = db.scalar(select(Competitor).where(Competitor.user_id == user.id, Competitor.name == name))
    if exists:
        raise HTTPException(status_code=400, detail="该追踪对象已存在")
    row = Competitor(
        user_id=user.id, name=name, type=data.type or "company",
        keywords=[k.strip() for k in (data.keywords or []) if k and k.strip()],
        level=data.level or "normal", notes=data.notes or "", enabled=bool(data.enabled),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.put("/{item_id}")
def update(item_id: int, data: CompetitorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _get_owned(db, user.id, item_id)
    row.name = (data.name or row.name).strip()
    row.type = data.type or row.type
    row.keywords = [k.strip() for k in (data.keywords or []) if k and k.strip()]
    row.level = data.level or row.level
    row.notes = data.notes or ""
    row.enabled = bool(data.enabled)
    db.commit()
    return {"ok": True}


@router.delete("/{item_id}")
def delete(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _get_owned(db, user.id, item_id)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/compare")
def compare(days: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """多对象并列对比（文档 5.7「对多个追踪对象动态并列展示」）。"""
    return competitor_service.compare(db, user.id, days=days)


@router.get("/{item_id}/timeline")
def timeline(item_id: int, limit: int = 100, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned(db, user.id, item_id)
    return competitor_service.timeline(db, user.id, item_id, limit=limit)


@router.post("/scan")
def scan(limit: int = 200, use_ai: bool = True, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """立即对已入库文章跑一次追踪识别。"""
    cfg = ensure_default_config(db, user.id)
    rows = db.scalars(
        select(Article).where(Article.user_id == user.id).order_by(Article.id.desc()).limit(min(limit, 500))
    ).all()
    articles = [
        {"title": a.title, "url": a.url, "source": a.source, "summary": a.summary,
         "published_at": a.published_at}
        for a in rows
    ]
    result = competitor_service.run_tracking(db, user.id, config_payload(cfg), articles, use_ai=use_ai)
    return {"ok": True, **result}
