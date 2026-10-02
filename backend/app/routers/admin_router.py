"""管理员路由：用户管理、系统统计、推送记录、定时任务总览。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Alert,
    Article,
    Competitor,
    KnowledgeChunk,
    LLMUsage,
    PeriodicalReport,
    Plugin,
    PushLog,
    Report,
    User,
    UserConfig,
)
from ..security import require_admin
from ..services.scheduler import _sync_jobs, job_overview

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdateIn(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    display_name: str | None = None


@router.get("/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id)).all()
    report_counts = dict(db.execute(
        select(Report.user_id, func.count(Report.id)).group_by(Report.user_id)
    ).all())
    return [
        {
            "id": u.id, "email": u.email, "role": u.role, "display_name": u.display_name,
            "is_active": bool(u.is_active),
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "report_count": report_counts.get(u.id, 0),
        }
        for u in users
    ]


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if data.role and data.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 user")
    if data.role == "user" and user.role == "admin":
        admins = db.scalar(select(func.count(User.id)).where(User.role == "admin"))
        if (admins or 0) <= 1:
            raise HTTPException(status_code=400, detail="不能降级最后一个管理员")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        if not data.is_active and user.id == admin.id:
            raise HTTPException(status_code=400, detail="不能停用自己的账号")
        user.is_active = bool(data.is_active)
    if data.display_name is not None:
        user.display_name = data.display_name
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        admins = db.scalar(select(func.count(User.id)).where(User.role == "admin"))
        if (admins or 0) <= 1:
            raise HTTPException(status_code=400, detail="不能删除最后一个管理员")
    # 级联清理该用户的业务数据
    for model, column in (
        (Report, Report.user_id), (Article, Article.user_id), (KnowledgeChunk, KnowledgeChunk.user_id),
        (Competitor, Competitor.user_id), (Alert, Alert.user_id), (PeriodicalReport, PeriodicalReport.user_id),
        (PushLog, PushLog.user_id), (LLMUsage, LLMUsage.user_id), (UserConfig, UserConfig.user_id),
    ):
        db.query(model).filter(column == user_id).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/stats")
def stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    def count(model, *conditions) -> int:
        stmt = select(func.count()).select_from(model)
        for cond in conditions:
            stmt = stmt.where(cond)
        return db.scalar(stmt) or 0

    push_by_status = dict(db.execute(
        select(PushLog.status, func.count(PushLog.id)).group_by(PushLog.status)
    ).all())
    usage = db.execute(
        select(func.count(LLMUsage.id), func.coalesce(func.sum(LLMUsage.total_tokens), 0),
               func.coalesce(func.sum(LLMUsage.cost), 0.0))
    ).one()
    return {
        "users": count(User),
        "configs": count(UserConfig),
        "reports": count(Report),
        "reports_7d": count(Report, Report.created_at >= cutoff),
        "articles": count(Article),
        "periodicals": count(PeriodicalReport),
        "knowledge_chunks": count(KnowledgeChunk),
        "competitors": count(Competitor),
        "alerts": count(Alert),
        "push_logs": count(PushLog),
        "push_by_status": push_by_status,
        "plugins": count(Plugin),
        "plugins_enabled": count(Plugin, Plugin.enabled == True),  # noqa: E712
        "llm_calls": usage[0] or 0,
        "llm_tokens": usage[1] or 0,
        "llm_cost": round(float(usage[2] or 0), 4),
    }


@router.get("/push-logs")
def push_logs(limit: int = 100, status: str = "", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(PushLog)
    if status:
        stmt = stmt.where(PushLog.status == status)
    rows = db.scalars(stmt.order_by(PushLog.id.desc()).limit(min(limit, 500))).all()
    users = {u.id: u.email for u in db.scalars(select(User)).all()}
    return [
        {"id": r.id, "user": users.get(r.user_id, str(r.user_id)), "channel": r.channel,
         "kind": r.kind, "status": r.status, "error": r.error,
         "report_id": r.report_id, "periodical_id": r.periodical_id,
         "created_at": r.created_at.isoformat() if r.created_at else ""}
        for r in rows
    ]


@router.get("/jobs")
def jobs(admin: User = Depends(require_admin)):
    """当前已注册的定时任务（含下次执行时间）。"""
    return {"jobs": job_overview()}


@router.post("/jobs/sync")
def sync_jobs(admin: User = Depends(require_admin)):
    _sync_jobs()
    return {"ok": True, "jobs": job_overview()}


@router.get("/usage")
def usage(days: int = 30, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(int(days), 1))
    rows = db.scalars(select(LLMUsage).where(LLMUsage.created_at >= cutoff)).all()
    by_model: dict[str, dict] = {}
    by_user: dict[str, dict] = {}
    users = {u.id: u.email for u in db.scalars(select(User)).all()}
    for r in rows:
        for bucket, key in ((by_model, r.model or "unknown"), (by_user, users.get(r.user_id, str(r.user_id)))):
            item = bucket.setdefault(key, {"calls": 0, "tokens": 0, "cost": 0.0})
            item["calls"] += 1
            item["tokens"] += r.total_tokens or 0
            item["cost"] += r.cost or 0.0
    return {
        "calls": len(rows),
        "total_tokens": sum(r.total_tokens or 0 for r in rows),
        "total_cost": round(sum(r.cost or 0 for r in rows), 4),
        "by_model": by_model,
        "by_user": by_user,
    }
