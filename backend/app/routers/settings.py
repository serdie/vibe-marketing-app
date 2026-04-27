from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProviderKey, TaskPreference
from ..providers import (
    CATALOG_BY_ID,
    PROVIDER_CATALOG,
    ProviderConfig,
    registry,
    test_connection,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ProviderUpsert(BaseModel):
    id: str
    api_key: str
    base_url: str | None = None
    models: dict[str, str] | None = None
    enabled: bool = True
    extra: dict | None = None  # from_email, smtp_user, smtp_starttls, etc.


class PreferenceSet(BaseModel):
    task: str
    provider_id: str


@router.get("/providers/catalog")
def catalog():
    return {"providers": PROVIDER_CATALOG}


@router.get("/providers")
def list_configured():
    return {
        "configured": registry.list_configured(),
        "preferences": registry.preferences(),
    }


@router.post("/providers")
def upsert_provider(p: ProviderUpsert, db: Session = Depends(get_db)):
    if p.id not in CATALOG_BY_ID:
        raise HTTPException(400, f"Proveedor desconocido: {p.id}")
    models = p.models or dict(CATALOG_BY_ID[p.id]["default_models"])
    registry.upsert(ProviderConfig(
        id=p.id, api_key=p.api_key, base_url=p.base_url,
        models=models, enabled=p.enabled, extra=p.extra,
    ))
    row = db.get(ProviderKey, p.id)
    if row is None:
        row = ProviderKey(id=p.id)
        db.add(row)
    row.api_key = p.api_key
    row.base_url = p.base_url
    row.models = models
    row.enabled = p.enabled
    row.extra = p.extra
    db.flush()
    return {"ok": True, "configured": registry.list_configured()}


@router.delete("/providers/{pid}")
def remove_provider(pid: str, db: Session = Depends(get_db)):
    registry.remove(pid)
    row = db.get(ProviderKey, pid)
    if row:
        db.delete(row)
    return {"ok": True}


@router.post("/providers/{pid}/test")
def test_provider(pid: str):
    return test_connection(pid)


@router.post("/providers/preference")
def set_pref(p: PreferenceSet, db: Session = Depends(get_db)):
    registry.set_preference(p.task, p.provider_id)
    row = db.get(TaskPreference, p.task)
    if row is None:
        row = TaskPreference(task=p.task, provider_id=p.provider_id)
        db.add(row)
    else:
        row.provider_id = p.provider_id
    db.flush()
    return {"ok": True, "preferences": registry.preferences()}
