"""定时调度：每个用户独立的晨报任务 + 周报 / 月报任务。

支持 每天 / 工作日 / 每周指定日 / 自定义 cron（文档 5.1「推送时间与频次」）。
多用户互不干扰；单用户任务失败不影响其他用户。
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..database import SessionLocal
from ..models import UserConfig
from ..settings import TIMEZONE
from . import periodical as periodical_service
from .pipeline import ensure_default_config, run_pipeline

logger = logging.getLogger("morning_insight.scheduler")

scheduler = BackgroundScheduler(timezone=TIMEZONE)

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _run_for_user(user_id: int) -> None:
    db = SessionLocal()
    try:
        run_pipeline(db, user_id, push=True)
    except Exception as exc:
        logger.warning("用户 %s 的定时晨报执行失败：%s", user_id, exc)
    finally:
        db.close()


def _run_periodical(user_id: int, period_type: str) -> None:
    db = SessionLocal()
    try:
        cfg = ensure_default_config(db, user_id)
        from .pipeline import config_payload

        periodical_service.generate(db, user_id, config_payload(cfg), period_type, push=True)
    except Exception as exc:
        logger.warning("用户 %s 的%s生成失败：%s", user_id, "周报" if period_type == "weekly" else "月报", exc)
    finally:
        db.close()


def _build_trigger(schedule: dict):
    time_str = schedule.get("time") or "07:30"
    try:
        hour, minute = (int(x) for x in str(time_str).split(":")[:2])
    except (ValueError, TypeError):
        hour, minute = 7, 30

    days = (schedule.get("days") or "daily").lower()
    if days == "custom":
        expr = (schedule.get("cron") or "").strip()
        if expr:
            try:
                return CronTrigger.from_crontab(expr, timezone=schedule.get("timezone") or TIMEZONE)
            except ValueError as exc:
                logger.warning("自定义 cron 解析失败（%s）：%s，已回退为每天", expr, exc)
        return CronTrigger(hour=hour, minute=minute, day_of_week="mon-sun")
    if days == "weekday":
        day_of_week = "mon-fri"
    elif days == "weekly":
        idx = int(schedule.get("weekday") or 1)
        day_of_week = WEEKDAY_NAMES[min(max(idx - 1, 0), 6)]
    else:
        day_of_week = "mon-sun"
    return CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week)


def _sync_jobs() -> None:
    """全量重建定时任务（用户量级小，重建成本可忽略）。"""
    db = SessionLocal()
    try:
        scheduler.remove_all_jobs()
        for cfg in db.query(UserConfig).all():
            schedule = cfg.schedule or {}
            if schedule.get("enabled"):
                try:
                    scheduler.add_job(
                        _run_for_user, _build_trigger(schedule), args=[cfg.user_id],
                        id=f"report-{cfg.user_id}", replace_existing=True, misfire_grace_time=3600,
                    )
                except Exception as exc:
                    logger.warning("为用户 %s 注册晨报任务失败：%s", cfg.user_id, exc)

            periodical = schedule.get("periodical") or {}
            weekly = periodical.get("weekly") or {}
            if weekly.get("enabled"):
                try:
                    hour, minute = (int(x) for x in str(weekly.get("time") or "08:30").split(":")[:2])
                    idx = int(weekly.get("weekday") or 1)
                    scheduler.add_job(
                        _run_periodical,
                        CronTrigger(hour=hour, minute=minute, day_of_week=WEEKDAY_NAMES[min(max(idx - 1, 0), 6)]),
                        args=[cfg.user_id, "weekly"], id=f"weekly-{cfg.user_id}",
                        replace_existing=True, misfire_grace_time=7200,
                    )
                except Exception as exc:
                    logger.warning("为用户 %s 注册周报任务失败：%s", cfg.user_id, exc)

            monthly = periodical.get("monthly") or {}
            if monthly.get("enabled"):
                try:
                    hour, minute = (int(x) for x in str(monthly.get("time") or "08:30").split(":")[:2])
                    day = min(max(int(monthly.get("day") or 1), 1), 28)  # 避开 29-31 号缺日
                    scheduler.add_job(
                        _run_periodical, CronTrigger(hour=hour, minute=minute, day=day),
                        args=[cfg.user_id, "monthly"], id=f"monthly-{cfg.user_id}",
                        replace_existing=True, misfire_grace_time=7200,
                    )
                except Exception as exc:
                    logger.warning("为用户 %s 注册月报任务失败：%s", cfg.user_id, exc)
    finally:
        db.close()


def start_scheduler() -> None:
    scheduler.add_job(_sync_jobs, "interval", minutes=5, id="sync-jobs", replace_existing=True)
    _sync_jobs()
    if not scheduler.running:
        scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def job_overview() -> list[dict]:
    """当前已注册任务（管理员页展示）。"""
    return [
        {"id": job.id, "next_run": job.next_run_time.isoformat() if job.next_run_time else ""}
        for job in scheduler.get_jobs()
        if job.id != "sync-jobs"
    ]
