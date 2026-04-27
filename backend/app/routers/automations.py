from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import providers
from ..db import get_db
from ..models import Asset, Automation, Campaign, Project

router = APIRouter(prefix="/api/projects/{pid}/automations", tags=["automations"])


class AutomationCreate(BaseModel):
    name: str
    trigger_kind: str  # schedule | comment | like | new_lead
    trigger_config: dict[str, Any] = {}
    action_kind: str  # publish_post | reply_comment | send_email | tag_lead
    action_config: dict[str, Any] = {}
    enabled: bool = True


@router.get("")
def list_automations(pid: str, db: Session = Depends(get_db)):
    rows = db.query(Automation).filter(Automation.project_id == pid).all()
    return [_a(a) for a in rows]


@router.post("")
def create_automation(pid: str, body: AutomationCreate, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    a = Automation(project_id=pid, **body.model_dump())
    db.add(a)
    db.flush()
    return _a(a)


@router.put("/{aid}")
def update_automation(pid: str, aid: str, body: AutomationCreate, db: Session = Depends(get_db)):
    a = db.get(Automation, aid)
    if not a or a.project_id != pid:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    db.flush()
    return _a(a)


@router.delete("/{aid}")
def del_automation(pid: str, aid: str, db: Session = Depends(get_db)):
    a = db.get(Automation, aid)
    if not a or a.project_id != pid:
        raise HTTPException(404)
    db.delete(a)
    return {"ok": True}


@router.post("/{aid}/run")
def run_automation(pid: str, aid: str, db: Session = Depends(get_db)):
    """Ejecuta una automatización (simulada). Devuelve evento generado."""
    a = db.get(Automation, aid)
    if not a or a.project_id != pid:
        raise HTTPException(404)

    runs = list(a.runs or [])
    event: dict[str, Any] = {"at": dt.datetime.utcnow().isoformat()}

    if a.action_kind == "publish_post":
        # publicar = marcar asset como publicado
        asset_id = (a.action_config or {}).get("asset_id")
        if asset_id:
            ast = db.get(Asset, asset_id)
            if ast:
                ast.published_at = dt.datetime.utcnow()
                event["published_asset"] = asset_id
        event["status"] = "published" if event.get("published_asset") else "skipped"
    elif a.action_kind == "reply_comment":
        # genera respuesta a un comentario simulado o real
        comment = (a.action_config or {}).get("comment_text") or "Genial, me encanta!"
        out = providers.call_text(
            f"Responde como community manager amable y de marca al comentario: '{comment}'. Máx 200 chars.",
        )
        event["reply_text"] = out.get("text")
        event["status"] = "replied"
    elif a.action_kind == "tag_lead":
        event["status"] = "tagged"
        event["lead_id"] = (a.action_config or {}).get("lead_id")
    elif a.action_kind == "send_email":
        event["status"] = "queued"
    else:
        event["status"] = "noop"

    runs.append(event)
    a.runs = runs
    a.last_run = dt.datetime.utcnow()
    db.flush()
    return event


@router.post("/{aid}/sentiment")
def sentiment_analysis(pid: str, aid: str, body: dict, db: Session = Depends(get_db)):
    """Analiza sentimiento de comentarios (simulado, IA)."""
    comments = body.get("comments") or []
    out = providers.call_json(
        "Analiza estos comentarios y devuelve JSON [{texto, sentimiento: 'positivo|neutro|negativo', score, sugerencia_respuesta}]:\n"
        + "\n".join(f"- {c}" for c in comments[:30]),
    )
    return out.get("data") or {}


def _a(a: Automation) -> dict:
    return {
        "id": a.id, "name": a.name, "trigger_kind": a.trigger_kind,
        "trigger_config": a.trigger_config, "action_kind": a.action_kind,
        "action_config": a.action_config, "enabled": a.enabled,
        "last_run": a.last_run.isoformat() if a.last_run else None,
        "runs": a.runs or [],
    }
