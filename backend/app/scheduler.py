"""Scheduler real basado en APScheduler. Ejecuta automatizaciones cuyo
trigger_kind == 'schedule' según trigger_config:
  - once: {"kind": "once", "at": ISO-8601}
  - cron: {"kind": "cron", "cron": "0 9 * * *"}
  - interval: {"kind": "interval", "seconds": 3600}
Cada tick re-evalúa la tabla Automation desde la BD.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None


def _run_automation(aid: str) -> None:
    from .db import session_scope
    from .models import Automation
    from .routers.automations import _execute  # import tardío para evitar ciclos
    try:
        with session_scope() as s:
            a = s.get(Automation, aid)
            if not a or not a.enabled:
                return
            event = _execute(a, s)
            runs = list(a.runs or [])
            runs.append(event)
            a.runs = runs
            a.last_run = dt.datetime.utcnow()
            s.flush()
            log.info("Automation %s fired: %s", aid, event.get("status"))
    except Exception:
        log.exception("Failed running automation %s", aid)


def _make_trigger(trigger_config: dict[str, Any]):
    kind = (trigger_config or {}).get("kind", "once")
    if kind == "cron":
        return CronTrigger.from_crontab(trigger_config["cron"])
    if kind == "interval":
        return IntervalTrigger(seconds=int(trigger_config.get("seconds", 3600)))
    if kind == "once":
        at = trigger_config.get("at")
        if at:
            run_at = dt.datetime.fromisoformat(at.replace("Z", "+00:00")) if isinstance(at, str) else at
            return DateTrigger(run_date=run_at)
    return None


def sync_jobs() -> int:
    """Sincroniza los jobs del scheduler con la tabla Automation.
    Se llama al arrancar y cada vez que se crea/actualiza/borra una automatización.
    """
    global _scheduler
    if _scheduler is None:
        return 0
    from .db import session_scope
    from .models import Automation
    count = 0
    with session_scope() as s:
        active_ids = set()
        for a in s.query(Automation).filter(Automation.enabled == True).all():  # noqa: E712
            if a.trigger_kind != "schedule":
                continue
            trig = _make_trigger(a.trigger_config or {})
            if trig is None:
                continue
            job_id = f"auto-{a.id}"
            active_ids.add(job_id)
            _scheduler.add_job(_run_automation, trig, id=job_id, args=[a.id],
                               replace_existing=True, misfire_grace_time=300)
            count += 1
        # Elimina jobs huérfanos
        for j in list(_scheduler.get_jobs()):
            if j.id.startswith("auto-") and j.id not in active_ids:
                _scheduler.remove_job(j.id)
    return count


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.start()
    try:
        sync_jobs()
    except Exception:
        log.exception("sync_jobs initial failed")


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
