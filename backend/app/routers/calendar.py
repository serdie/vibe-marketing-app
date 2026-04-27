from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Asset, Campaign

router = APIRouter(prefix="/api/projects/{pid}/calendar", tags=["calendar"])


class ScheduleAsset(BaseModel):
    asset_id: str
    when: str  # ISO


@router.get("")
def calendar(pid: str, db: Session = Depends(get_db)):
    camps = db.query(Campaign).filter(Campaign.project_id == pid).all()
    items = []
    for c in camps:
        for a in c.assets:
            items.append({
                "campaign_id": c.id,
                "campaign_name": c.name,
                "asset_id": a.id,
                "kind": a.kind,
                "title": a.title,
                "approved": a.approved,
                "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            })
    items.sort(key=lambda x: x.get("scheduled_at") or "")
    return items


@router.post("/schedule")
def schedule(pid: str, body: ScheduleAsset, db: Session = Depends(get_db)):
    a = db.get(Asset, body.asset_id)
    if not a:
        raise HTTPException(404)
    a.scheduled_at = dt.datetime.fromisoformat(body.when.replace("Z", "+00:00"))
    db.flush()
    return {"ok": True}
