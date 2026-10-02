"""周报 / 月报：周期概览、分板块汇总、趋势变化、角色建议、上期对比、自动推送与存档。

对应文档 5.9。
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import processing
from ..models import Article, PeriodicalReport, Report
from ..push import PushMessage, dispatch
from ..report import render_report_html
from ..utils.text import truncate

logger = logging.getLogger("morning_insight.periodical")


def period_bounds(period_type: str, ref: date | None = None) -> tuple[date, date, str]:
    """返回 (起始日, 结束日, 展示标签)。

    - weekly：覆盖到 ref 为止的 7 天（默认在周一生成，覆盖上一周）
    - monthly：覆盖 ref 所在月份（默认在 1 号生成，覆盖上一自然月）
    """
    ref = ref or datetime.now(timezone.utc).astimezone().date()
    if period_type == "monthly":
        first = ref.replace(day=1)
        end = first - timedelta(days=1)  # 上一自然月最后一天
        start = end.replace(day=1)
        label = f"{start.year} 年 {start.month} 月"
    else:
        end = ref - timedelta(days=1) if ref.weekday() == 0 else ref
        start = end - timedelta(days=6)
        label = f"{start.isoformat()} ~ {end.isoformat()}"
    return start, end, label


def previous_period(db: Session, user_id: int, period_type: str, before: date) -> PeriodicalReport | None:
    return db.scalars(
        select(PeriodicalReport)
        .where(
            PeriodicalReport.user_id == user_id,
            PeriodicalReport.period_type == period_type,
            PeriodicalReport.period_start < before.isoformat(),
        )
        .order_by(PeriodicalReport.period_start.desc())
        .limit(1)
    ).first()


def generate(
    db: Session,
    user_id: int,
    cfg: dict,
    period_type: str = "weekly",
    *,
    start: date | None = None,
    end: date | None = None,
    push: bool = True,
    use_ai: bool = True,
) -> PeriodicalReport:
    """生成一份周报/月报（含上期对比）。"""
    if start is None or end is None:
        auto_start, auto_end, label = period_bounds(period_type)
        start = start or auto_start
        end = end or auto_end
    else:
        label = f"{start.isoformat()} ~ {end.isoformat()}"

    reports = list(db.scalars(
        select(Report)
        .where(Report.user_id == user_id, Report.report_date >= start.isoformat(),
               Report.report_date <= end.isoformat())
        .order_by(Report.report_date)
    ).all())
    articles = list(db.scalars(
        select(Article)
        .where(Article.user_id == user_id, Article.fetched_at >= datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc))
        .order_by(Article.id.desc())
        .limit(400)
    ).all())
    article_dicts = [
        {"title": a.title, "url": a.url, "source": a.source, "summary": a.summary,
         "published_at": a.published_at}
        for a in articles
    ]

    ai_cfg = dict(cfg.get("ai_config") or {})
    ai_cfg["report_language"] = cfg.get("report_language") or "zh"
    ai_cfg["focus_points"] = cfg.get("focus_points") or []
    ai_cfg["roles"] = cfg.get("roles") or []

    content_md = ""
    error = ""
    if use_ai:
        try:
            prev = previous_period(db, user_id, period_type, start)
            if prev:
                reports_payload = [
                    {"report_date": r.report_date, "title": r.title, "content_md": r.content_md} for r in reports[-7:]
                ]
                reports_payload.append({
                    "report_date": f"上期{period_type == 'weekly' and '周报' or '月报'}结论",
                    "title": "上一周期结论（用于对比）",
                    "content_md": truncate(prev.content_md, 3000),
                })
            else:
                reports_payload = [
                    {"report_date": r.report_date, "title": r.title, "content_md": r.content_md} for r in reports[-7:]
                ]
            content_md = processing.generate_periodical(
                ai_cfg, period_type, label, reports_payload, article_dicts, db=db, user_id=user_id,
            )
        except Exception as exc:
            error = str(exc)
            logger.warning("周月报 AI 生成失败：%s", exc)

    if not content_md:
        name = "周报" if period_type == "weekly" else "月报"
        lines = [f"# {label} 行业分析{name}", "", "## 周期概览",
                 f"本周期共生成 {len(reports)} 份晨报，覆盖素材 {len(article_dicts)} 条。",
                 ""]
        if error:
            lines += [f"> AI 生成未完成：{error}", ""]
        for r in reports:
            lines.append(f"## {r.report_date}")
            lines.append(truncate(r.content_md, 1200))
            lines.append("")
        content_md = "\n".join(lines)

    name = "周报" if period_type == "weekly" else "月报"
    title = f"{label} {name}"
    first_heading = next((ln for ln in content_md.splitlines() if ln.strip().startswith("# ")), "")
    if first_heading:
        title = first_heading[2:].strip() or title

    content_html = render_report_html(content_md, title=title, template=cfg.get("template") or "magazine",
                                      meta={"report_date": label})

    stats = {
        "reports": len(reports),
        "articles": len(article_dicts),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "by_source": _count_by(article_dicts, "source", top=10),
        "by_category": _count_by([{"category": f.get("name")} for f in (cfg.get("focus_points") or [])], "category", top=10),
    }

    item = PeriodicalReport(
        user_id=user_id, period_type=period_type,
        period_start=start.isoformat(), period_end=end.isoformat(),
        title=title[:500], content_md=content_md, content_html=content_html,
        stats=stats, sources_used=[a.url for a in articles[:200]],
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # 自动入库到知识库
    try:
        from . import knowledge

        knowledge.ingest_periodical(db, user_id, item, cfg)
    except Exception as exc:
        logger.warning("周月报入库失败：%s", exc)

    if push:
        msg = PushMessage(
            title=title, content_md=content_md, content_html=content_html, kind="periodical",
        )
        dispatch(db, user_id, cfg.get("push_config") or {}, msg, periodical_id=item.id)
    return item


def _count_by(items: list[dict], key: str, top: int = 10) -> list[dict]:
    counts: dict[str, int] = {}
    for it in items:
        value = str(it.get(key) or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda x: -x[1])[:top]
    return [{"name": k, "count": v} for k, v in ordered]


def list_periodicals(db: Session, user_id: int, period_type: str = "", limit: int = 30) -> list[dict]:
    stmt = select(PeriodicalReport).where(PeriodicalReport.user_id == user_id)
    if period_type:
        stmt = stmt.where(PeriodicalReport.period_type == period_type)
    rows = db.scalars(stmt.order_by(PeriodicalReport.id.desc()).limit(min(limit, 100))).all()
    return [
        {"id": r.id, "period_type": r.period_type, "title": r.title,
         "period_start": r.period_start, "period_end": r.period_end,
         "stats": r.stats, "created_at": r.created_at.isoformat() if r.created_at else ""}
        for r in rows
    ]
