from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import providers
from ..db import get_db
from ..models import Lead, Project
from ..scraping import extract_contacts, fetch

router = APIRouter(prefix="/api/projects/{pid}/leads", tags=["leads"])


class LeadSearchRequest(BaseModel):
    query: str | None = None
    sector: str | None = None
    location: str | None = None
    limit: int = 12
    enrich_with_scrape: bool = True


@router.get("")
def list_leads(pid: str, db: Session = Depends(get_db)):
    return [_lead_dict(l) for l in db.query(Lead).filter(Lead.project_id == pid).all()]


@router.post("/search")
def search_leads(pid: str, body: LeadSearchRequest, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    icp = p.icp or {}
    profile = (p.research or {}).get("profile") or {}
    personas = p.personas or []
    sector = body.sector or icp.get("sector_principal") or profile.get("sector") or ""
    loc_obj = profile.get("ubicacion")
    if isinstance(loc_obj, dict):
        loc_str_default = ", ".join([str(v) for v in [loc_obj.get("ciudad"), loc_obj.get("provincia"), loc_obj.get("pais")] if v])
    else:
        loc_str_default = loc_obj or ""
    location = body.location or icp.get("geo") or loc_str_default
    sectores_sec = icp.get("sectores_secundarios") or []
    persona_summary = "; ".join([f"{(pe.get('nombre') or pe.get('rol') or '?')}: {pe.get('rol','')}" for pe in personas[:3]])

    seed_query = body.query or (
        f"empresas/negocios/autónomos del sector \"{sector}\" "
        f"(también de sectores afines: {', '.join(sectores_sec) if sectores_sec else 'sin definir'}) "
        f"ubicados en {location or 'cualquier zona'}, "
        f"que serían **clientes potenciales** del propietario \"{p.full_name or p.name}\" "
        f"para sus productos/servicios: " + ", ".join([pp.get("name", "") for pp in (p.products or [])])
        + (f". Buyer personas objetivo: {persona_summary}" if persona_summary else "")
    )

    prompt = (
        "Encuentra clientes potenciales **reales** (negocios concretos, no genéricos) que cumplan: "
        f"{seed_query}\n\n"
        f"Devuelve {body.limit} resultados. Para cada uno: "
        "{name, website (URL real verificada), email, phone, address, city, country, sector, "
        "score (0-100 prob. de compra), por_que_encaja (2-3 frases concretas), "
        "buyer_persona_match (cuál de las personas le encaja), canal_recomendado_para_contactar}. "
        "Si no conoces el email/phone exactos, deja null. "
        "NUNCA inventes negocios; si no tienes 10, devuelve menos. "
        "Devuelve JSON {leads: [...]}. JSON válido sin markdown."
    )
    out = providers.call_json(prompt, grounded=True, system="Encuentra negocios reales con su web pública. No mezcles con otros nombres parecidos.")
    data = out.get("data") or {}
    raw_leads = data.get("leads") if isinstance(data, dict) else []
    if not raw_leads and isinstance(data, list):
        raw_leads = data

    saved: list[Lead] = []
    for item in raw_leads[: body.limit]:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or item.get("nombre") or "").strip()
        if not name:
            continue
        website = item.get("website") or item.get("web") or ""
        email = item.get("email")
        phone = item.get("phone") or item.get("telefono")
        address = item.get("address") or item.get("direccion")
        city = item.get("city") or item.get("ciudad")
        country = item.get("country") or item.get("pais")
        sector_l = item.get("sector")
        score = float(item.get("score", 50) or 50)
        notes = item.get("por_que_encaja") or item.get("notes")
        extra = {"raw": item}

        # enrich con scrape
        if body.enrich_with_scrape and website:
            status, html = fetch(website)
            if status and html:
                ec = extract_contacts(html, base_url=website)
                email = email or (ec["emails"][0] if ec["emails"] else None)
                phone = phone or (ec["phones"][0] if ec["phones"] else None)
                extra["socials"] = ec.get("socials")
                extra["site_title"] = ec.get("title")
                extra["site_description"] = ec.get("description")

        l = Lead(
            project_id=pid, name=name, website=website or None, email=email, phone=phone,
            address=address, city=city, country=country, sector=sector_l, score=score,
            notes=notes, extra=extra,
        )
        db.add(l)
        db.flush()
        saved.append(l)

    return {
        "leads": [_lead_dict(x) for x in saved],
        "sources": out.get("grounded_sources", []),
        "degraded": out.get("degraded", False),
        "model": out.get("model"),
    }


@router.delete("/{lid}")
def delete_lead(pid: str, lid: str, db: Session = Depends(get_db)):
    l = db.get(Lead, lid)
    if not l or l.project_id != pid:
        raise HTTPException(404)
    db.delete(l)
    return {"ok": True}


@router.get("/export.csv")
def export_csv(pid: str, db: Session = Depends(get_db)):
    rows = db.query(Lead).filter(Lead.project_id == pid).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "website", "email", "phone", "address", "city", "country", "sector", "score", "notes"])
    for l in rows:
        w.writerow([l.id, l.name, l.website or "", l.email or "", l.phone or "",
                    l.address or "", l.city or "", l.country or "", l.sector or "",
                    l.score, (l.notes or "").replace("\n", " ")])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leads_{pid}.csv"},
    )


def _lead_dict(l: Lead) -> dict[str, Any]:
    return {
        "id": l.id, "name": l.name, "website": l.website, "email": l.email,
        "phone": l.phone, "address": l.address, "city": l.city, "country": l.country,
        "sector": l.sector, "score": l.score, "notes": l.notes, "extra": l.extra,
    }
