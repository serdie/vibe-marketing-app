from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Asset, Automation, Campaign, EmailSend, Lead, Project

router = APIRouter(prefix="/api", tags=["kpis"])


@router.get("/kpis/{pid}")
def kpis(pid: str, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        return {"error": "no project"}
    leads = db.query(Lead).filter(Lead.project_id == pid).count()
    camps = db.query(Campaign).filter(Campaign.project_id == pid).all()
    camp_ids = [c.id for c in camps]
    assets = db.query(Asset).filter(Asset.campaign_id.in_(camp_ids or [""])).all()
    sends = db.query(EmailSend).filter(EmailSend.campaign_id.in_(camp_ids or [""])).all()
    autos = db.query(Automation).filter(Automation.project_id == pid).count()

    total_sent = len(sends)
    opens = sum(1 for s in sends if s.open_count > 0)
    clicks = sum(1 for s in sends if s.click_count > 0)
    estimated_revenue = sum((c.roi or {}).get("revenue_eur", 0) for c in camps)
    estimated_profit = sum((c.roi or {}).get("profit_eur", 0) for c in camps)

    return {
        "leads": leads,
        "campaigns": len(camps),
        "assets": len(assets),
        "approved_assets": sum(1 for a in assets if a.approved),
        "scheduled_assets": sum(1 for a in assets if a.scheduled_at),
        "automations": autos,
        "emails_sent": total_sent,
        "open_rate_pct": round(opens / total_sent * 100, 1) if total_sent else 0,
        "click_rate_pct": round(clicks / total_sent * 100, 1) if total_sent else 0,
        "estimated_revenue_eur": round(estimated_revenue, 2),
        "estimated_profit_eur": round(estimated_profit, 2),
    }
