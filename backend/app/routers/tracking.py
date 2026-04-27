from __future__ import annotations

import base64
import datetime as dt

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import EmailEvent, EmailSend

router = APIRouter(prefix="/api/track", tags=["tracking"])

# 1x1 PNG transparente
_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@router.get("/open/{send_id}.png")
def open_pixel(send_id: str, request: Request, db: Session = Depends(get_db)):
    s = db.get(EmailSend, send_id)
    if s:
        s.open_count += 1
        if not s.opened_at:
            s.opened_at = dt.datetime.utcnow()
        db.add(EmailEvent(
            send_id=send_id, kind="open",
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        ))
        db.flush()
    return Response(content=_PIXEL, media_type="image/png", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    })


@router.get("/click/{send_id}")
def click_redirect(send_id: str, u: str, request: Request, db: Session = Depends(get_db)):
    s = db.get(EmailSend, send_id)
    if s:
        s.click_count += 1
        s.last_click_at = dt.datetime.utcnow()
        db.add(EmailEvent(
            send_id=send_id, kind="click", url=u,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        ))
        db.flush()
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return RedirectResponse(u, status_code=302)


@router.get("/unsub/{send_id}", response_class=HTMLResponse)
def unsubscribe(send_id: str, db: Session = Depends(get_db)):
    s = db.get(EmailSend, send_id)
    if s:
        s.unsubscribed = True
        db.add(EmailEvent(send_id=send_id, kind="unsubscribe"))
        db.flush()
    return HTMLResponse(
        "<html><body style='font-family: system-ui; padding: 2rem;'>"
        "<h1>Baja confirmada</h1><p>No recibirás más emails de esta lista.</p>"
        "</body></html>"
    )


@router.get("/dashboard/{campaign_id}")
def dashboard(campaign_id: str, db: Session = Depends(get_db)):
    sends = db.query(EmailSend).filter(EmailSend.campaign_id == campaign_id).all()
    total = len(sends)
    opens = sum(1 for s in sends if s.open_count > 0)
    clicks = sum(1 for s in sends if s.click_count > 0)
    unsub = sum(1 for s in sends if s.unsubscribed)
    by_variant: dict[str, dict[str, int]] = {}
    for s in sends:
        v = by_variant.setdefault(s.variant, {"sent": 0, "open": 0, "click": 0})
        v["sent"] += 1
        v["open"] += 1 if s.open_count > 0 else 0
        v["click"] += 1 if s.click_count > 0 else 0
    return {
        "total_sent": total,
        "open_rate_pct": round(opens / total * 100, 1) if total else 0,
        "click_rate_pct": round(clicks / total * 100, 1) if total else 0,
        "unsubscribe_rate_pct": round(unsub / total * 100, 1) if total else 0,
        "by_variant": by_variant,
        "sends": [{
            "id": s.id, "to": s.to_email, "subject": s.subject, "variant": s.variant,
            "opens": s.open_count, "clicks": s.click_count,
            "opened_at": s.opened_at.isoformat() if s.opened_at else None,
            "last_click_at": s.last_click_at.isoformat() if s.last_click_at else None,
            "unsubscribed": s.unsubscribed,
            "sent_at": s.sent_at.isoformat() if s.sent_at else None,
        } for s in sends],
    }
