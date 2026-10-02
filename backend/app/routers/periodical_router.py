"""周报 / 月报路由：列表、详情、导出、生成。"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PeriodicalReport, User
from ..push import PushMessage, dispatch
from ..report import export_all_formats, render_report_html
from ..security import get_current_user
from ..services import periodical as periodical_service
from ..services.pipeline import combined_push_config, config_payload, ensure_default_config

router = APIRouter(prefix="/api/periodicals", tags=["periodicals"])


@router.get("")
def list_items(period_type: str = "", limit: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return periodical_service.list_periodicals(db, user.id, period_type=period_type, limit=limit)


@router.get("/{item_id}")
def detail(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(PeriodicalReport, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {
        "id": row.id, "period_type": row.period_type, "title": row.title,
        "period_start": row.period_start, "period_end": row.period_end,
        "content_md": row.content_md, "content_html": row.content_html,
        "stats": row.stats or {}, "sources_used": row.sources_used or [],
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


@router.get("/{item_id}/preview", response_class=HTMLResponse)
def preview(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(PeriodicalReport, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    if row.content_html:
        return HTMLResponse(row.content_html)
    return HTMLResponse(render_report_html(row.content_md, title=row.title, template="magazine"))


class GenerateIn(BaseModel):
    period_type: str = "weekly"
    start: str = ""
    end: str = ""
    push: bool = True


@router.post("/generate")
def generate(data: GenerateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.period_type not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period_type 必须是 weekly 或 monthly")
    cfg = ensure_default_config(db, user.id)

    def _parse(value: str):
        try:
            return date.fromisoformat(value) if value else None
        except ValueError:
            return None

    try:
        item = periodical_service.generate(
            db, user.id, config_payload(cfg), data.period_type,
            start=_parse(data.start), end=_parse(data.end), push=data.push,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败：{exc}")
    return {"ok": True, "id": item.id, "title": item.title}


@router.post("/{item_id}/push")
def push(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(PeriodicalReport, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    cfg = ensure_default_config(db, user.id)
    results = dispatch(
        db, user.id, combined_push_config(cfg),
        PushMessage(title=row.title, content_md=row.content_md, content_html=row.content_html, kind="periodical"),
        periodical_id=row.id,
    )
    return {"ok": any(r.ok for r in results),
            "results": [{"channel": r.channel, "ok": r.ok, "detail": r.detail} for r in results]}


@router.get("/{item_id}/export")
def export(item_id: int, fmt: str = "md", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(PeriodicalReport, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    html = row.content_html or render_report_html(row.content_md, title=row.title, template="magazine")
    try:
        path = export_all_formats(row.content_md, html, row.title or "报告", fmt)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    suffix = {"md": "md", "html": "html", "pdf": "pdf", "image": "png", "png": "png"}.get(fmt.lower(), "md")
    media = {"md": "text/markdown", "html": "text/html", "pdf": "application/pdf", "png": "image/png"}.get(suffix, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=f"{row.title or 'report'}.{suffix}")


@router.delete("/{item_id}")
def delete(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(PeriodicalReport, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
