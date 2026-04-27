from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .models import init_db
from .providers import ProviderUnavailable
from .routers import (
    automations,
    calendar,
    campaigns,
    kpis,
    leads,
    mcp_server,
    projects,
    settings as settings_router,
    tracking,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")
_settings = get_settings()

app = FastAPI(title="Vibe Marketing App", version="0.1.0")

cors_origins = [o.strip() for o in (_settings.cors_origins or "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()
    log.info("DB initialized at %s", _settings.database_url)
    # Hydrate provider registry from DB
    from . import providers as _p
    from .db import session_scope
    from .models import ProviderKey, TaskPreference
    try:
        with session_scope() as s:
            for row in s.query(ProviderKey).all():
                _p.registry.upsert(_p.ProviderConfig(
                    id=row.id, api_key=row.api_key, base_url=row.base_url,
                    models=row.models, enabled=row.enabled,
                    extra=getattr(row, "extra", None),
                ))
            for tp in s.query(TaskPreference).all():
                _p.registry.set_preference(tp.task, tp.provider_id)
    except Exception as e:
        log.warning("Provider hydration failed: %s", e)
    # Arranca scheduler real de automatizaciones
    try:
        from . import scheduler
        scheduler.start()
        log.info("Scheduler started")
    except Exception as e:
        log.warning("Scheduler start failed: %s", e)


@app.on_event("shutdown")
def _shutdown():
    try:
        from . import scheduler
        scheduler.stop()
    except Exception:
        pass


@app.exception_handler(ProviderUnavailable)
async def _provider_unavailable(_req: Request, exc: ProviderUnavailable):
    return JSONResponse(
        status_code=503,
        content={"error": "provider_unavailable", "message": str(exc), "degraded": True},
    )


@app.get("/healthz")
def healthz():
    from . import providers as _p
    return {
        "ok": True,
        "providers_configured": _p.registry.list_configured(),
        "preferences": _p.registry.preferences(),
    }


app.include_router(settings_router.router)
app.include_router(projects.router)
app.include_router(leads.router)
app.include_router(campaigns.router)
app.include_router(automations.router)
app.include_router(calendar.router)
app.include_router(kpis.router)
app.include_router(tracking.router)
app.include_router(mcp_server.router)


@app.get("/")
def root():
    return {
        "app": "Vibe Marketing App",
        "version": "0.1.0",
        "docs": "/docs",
        "mcp": "/api/mcp",
    }
