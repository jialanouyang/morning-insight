"""晨报路由：列表 / 详情 / 生成 / 导出 / 推送 / 语音。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Report, User
from ..push import PushMessage, dispatch, enabled_channels
from ..report import export_all_formats, render_report_html
from ..security import get_current_user
from ..services import tts as tts_service
from ..services import translation as translation_service
from ..services.pipeline import combined_push_config, config_payload, ensure_default_config, run_pipeline

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports(
    q: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 30,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Report).where(Report.user_id == user.id)
    if q:
        stmt = stmt.where(or_(Report.title.contains(q), Report.content_md.contains(q)))
    if date_from:
        stmt = stmt.where(Report.report_date >= date_from)
    if date_to:
        stmt = stmt.where(Report.report_date <= date_to)
    rows = db.scalars(
        stmt.order_by(Report.created_at.desc()).offset(max(offset, 0)).limit(min(limit, 100))
    ).all()
    return [
        {
            "id": r.id,
            "report_date": r.report_date,
            "title": r.title,
            "template": r.template,
            "industry": r.industry,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "source_count": len(r.sources_used or []),
            "meta": r.meta or {},
            "excerpt": (r.content_md or "")[:180],
        }
        for r in rows
    ]


@router.get("/{report_id}")
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="晨报不存在")
    return {
        "id": r.id,
        "report_date": r.report_date,
        "title": r.title,
        "template": r.template,
        "industry": r.industry,
        "content_md": r.content_md,
        "content_html": r.content_html,
        "sources_used": r.sources_used,
        "meta": r.meta or {},
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


class TranslateIn(BaseModel):
    target_lang: str = "zh"  # zh / en，与界面语言一致


@router.post("/{report_id}/translate")
def translate_report(
    report_id: int,
    data: TranslateIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """一键翻译：把整篇晨报翻译为界面语言，保留 Markdown 结构与排版。

    译文按（晨报 × 目标语言）落库缓存，重复请求不重复调用大模型。
    """
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="晨报不存在")
    cfg = ensure_default_config(db, user.id)
    target = (data.target_lang if data else "") or "zh"
    try:
        return translation_service.translate_report(db, cfg, r, target)
    except translation_service.TranslationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"翻译失败：{exc}")


@router.get("/{report_id}/preview", response_class=HTMLResponse)
def preview(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """独立 HTML 预览（用于导出前的浏览器预览）。"""
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="晨报不存在")
    if r.content_html:
        return HTMLResponse(r.content_html)
    return HTMLResponse(render_report_html(
        r.content_md, title=r.title, template=r.template or "brief",
        meta={**(r.meta or {}), "industry": r.industry, "report_date": r.report_date},
    ))


class GenerateIn(BaseModel):
    push: bool = True
    use_ai: bool = True
    tracking: bool = True
    alerts: bool = True
    tts: bool = False


@router.post("/generate")
def generate(data: GenerateIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动立即执行一次完整链路（抓取 → AI 生成 → 入库 → 预警 → 推送 → 语音）。"""
    opts = data or GenerateIn()
    ensure_default_config(db, user.id)
    try:
        report = run_pipeline(
            db, user.id, push=opts.push, use_ai=opts.use_ai,
            tracking=opts.tracking, alerts=opts.alerts, make_tts=opts.tts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败：{exc}")
    return {"ok": True, "report_id": report.id, "title": report.title}


@router.delete("/{report_id}")
def delete_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="晨报不存在")
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.get("/{report_id}/export")
def export(report_id: int, fmt: str = "md", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """导出晨报：fmt = md / html / pdf / image。"""
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="晨报不存在")
    html = r.content_html or render_report_html(
        r.content_md, title=r.title, template=r.template or "brief",
        meta={**(r.meta or {}), "industry": r.industry, "report_date": r.report_date},
    )
    try:
        path = export_all_formats(r.content_md, html, r.title or f"晨报-{r.report_date}", fmt)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导出失败：{exc}")

    suffix = {"md": "md", "html": "html", "htm": "html", "pdf": "pdf", "image": "png", "png": "png"}.get(fmt.lower(), "md")
    media = {"md": "text/markdown", "html": "text/html", "pdf": "application/pdf", "png": "image/png"}.get(suffix, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=f"{r.title or 'report'}.{suffix}")


class PushIn(BaseModel):
    channels: list[str] | None = None


@router.post("/{report_id}/push")
def push_report(report_id: int, data: PushIn | None = None,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """立即推送指定晨报到渠道（不传 channels 则推送到全部已启用渠道）。"""
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="晨报不存在")
    cfg = ensure_default_config(db, user.id)
    push_cfg = combined_push_config(cfg)
    targets = (data.channels if data else None) or None
    if not targets and not enabled_channels(push_cfg):
        raise HTTPException(status_code=400, detail="未启用任何推送渠道，请先在「设置 → 推送渠道」中开启")
    msg = PushMessage(title=r.title, content_md=r.content_md, content_html=r.content_html, kind="report")
    results = dispatch(db, user.id, push_cfg, msg, report_id=r.id, channels=targets)
    return {
        "ok": any(x.ok for x in results),
        "results": [{"channel": x.channel, "ok": x.ok, "detail": x.detail} for x in results],
    }


@router.get("/{report_id}/tts")
def tts_assets(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import TTSAsset

    rows = db.scalars(
        select(TTSAsset).where(TTSAsset.user_id == user.id, TTSAsset.report_id == report_id)
        .order_by(TTSAsset.id.desc())
    ).all()
    return [
        {"id": a.id, "voice": a.voice, "provider": a.provider, "fmt": a.fmt,
         "duration_sec": a.duration_sec, "size_bytes": a.size_bytes,
         "created_at": a.created_at.isoformat() if a.created_at else ""}
        for a in rows
    ]


class TTSIn(BaseModel):
    provider: str = ""
    voice: str = ""
    fmt: str = ""
    push: bool = False


@router.post("/{report_id}/tts")
def make_tts(report_id: int, data: TTSIn | None = None,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """生成（或重新生成）语音晨报。"""
    r = db.get(Report, report_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(status_code=404, detail="晨报不存在")
    cfg = ensure_default_config(db, user.id)
    opts = data or TTSIn()
    payload = config_payload(cfg)
    available, reason = tts_service.is_available(opts.provider or (cfg.tts_config or {}).get("provider") or "edge")
    if not available:
        raise HTTPException(status_code=400, detail=reason)
    try:
        asset = tts_service.full_flow(
            db, user.id, payload, r.content_md, report_id=r.id,
            provider=opts.provider, voice=opts.voice, fmt=opts.fmt,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"语音生成失败：{exc}")
    if opts.push:
        dispatch(
            db, user.id, combined_push_config(cfg),
            PushMessage(title=r.title, content_md=f"语音晨报已生成：{r.title}",
                        attachments=[{"path": asset.path, "name": f"{r.title}.{asset.fmt}"}], kind="report"),
        )
    return {"ok": True, "asset_id": asset.id, "voice": asset.voice, "fmt": asset.fmt,
            "duration_sec": asset.duration_sec, "size_bytes": asset.size_bytes}


@router.get("/tts/assets")
def all_tts_assets(limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return tts_service.list_assets(db, user.id, limit)


@router.get("/tts/audio/{asset_id}")
def get_audio(asset_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import TTSAsset

    asset = db.get(TTSAsset, asset_id)
    if asset is None or asset.user_id != user.id:
        raise HTTPException(status_code=404, detail="音频不存在")
    media = {"mp3": "audio/mpeg", "ogg": "audio/ogg"}.get(asset.fmt, "application/octet-stream")
    return FileResponse(asset.path, media_type=media)
