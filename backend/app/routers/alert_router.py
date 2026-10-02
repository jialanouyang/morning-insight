"""关键词预警路由：规则 CRUD、预警历史、立即检查。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, User
from ..security import get_current_user
from ..services import alert as alert_service
from ..services.pipeline import config_payload, ensure_default_config

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

MATCH_TYPES = ("exact", "fuzzy")
CONDITIONS = ("always", "frequency", "source")


class AlertIn(BaseModel):
    keyword: str
    match_type: str = "exact"
    condition: str = "always"
    condition_value: int = 1
    channels: list[str] | None = None
    cooldown_minutes: int = 180
    enabled: bool = True


def _get_owned(db: Session, user_id: int, alert_id: int) -> Alert:
    row = db.get(Alert, alert_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="预警规则不存在")
    return row


@router.get("")
def list_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.id.desc())
    ).all()
    return [
        {"id": r.id, "keyword": r.keyword, "match_type": r.match_type,
         "condition": r.condition, "condition_value": r.condition_value,
         "channels": r.channels or [], "cooldown_minutes": r.cooldown_minutes,
         "enabled": bool(r.enabled),
         "last_fired_at": r.last_fired_at.isoformat() if r.last_fired_at else "",
         "created_at": r.created_at.isoformat() if r.created_at else ""}
        for r in rows
    ]


@router.post("")
def create(data: AlertIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keyword = (data.keyword or "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    if data.match_type not in MATCH_TYPES:
        raise HTTPException(status_code=400, detail=f"match_type 必须是 {MATCH_TYPES} 之一")
    if data.condition not in CONDITIONS:
        raise HTTPException(status_code=400, detail=f"condition 必须是 {CONDITIONS} 之一")
    exists = db.scalar(select(Alert).where(Alert.user_id == user.id, Alert.keyword == keyword))
    if exists:
        raise HTTPException(status_code=400, detail="该关键词预警已存在")
    row = Alert(
        user_id=user.id, keyword=keyword, match_type=data.match_type,
        condition=data.condition, condition_value=max(int(data.condition_value or 1), 1),
        channels=data.channels or [], cooldown_minutes=max(int(data.cooldown_minutes or 0), 0),
        enabled=bool(data.enabled),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.put("/{alert_id}")
def update(alert_id: int, data: AlertIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _get_owned(db, user.id, alert_id)
    row.keyword = (data.keyword or row.keyword).strip()
    row.match_type = data.match_type if data.match_type in MATCH_TYPES else row.match_type
    row.condition = data.condition if data.condition in CONDITIONS else row.condition
    row.condition_value = max(int(data.condition_value or 1), 1)
    row.channels = data.channels or []
    row.cooldown_minutes = max(int(data.cooldown_minutes or 0), 0)
    row.enabled = bool(data.enabled)
    db.commit()
    return {"ok": True}


@router.delete("/{alert_id}")
def delete(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _get_owned(db, user.id, alert_id)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/history")
def history(limit: int = 100, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """预警历史（文档 5.8）。"""
    return alert_service.history(db, user.id, limit=limit)


@router.post("/scan")
def scan(limit: int = 200, use_ai: bool = True, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """立即对已入库文章跑一次预警检查。"""
    cfg = ensure_default_config(db, user.id)
    fired = alert_service.scan_existing_articles(db, user.id, config_payload(cfg), limit=limit)
    return {"ok": True, "fired": fired}
