from __future__ import annotations

import datetime as dt
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import providers
from ..config import get_settings
from ..db import get_db
from ..email_sender import EmailProviderMissing, EmailSendError, send_email
from ..models import Asset, Campaign, EmailSend, Lead, Project
from ..providers import ProviderUnavailable


def _safe_images(prompt: str, n: int = 1, aspect: str = "1:1") -> tuple[list[str], str | None]:
    """Genera imágenes; si no hay proveedor, devuelve lista vacía + nota informativa."""
    try:
        return providers.call_image(prompt, n=n, aspect=aspect), None
    except ProviderUnavailable as e:
        return [], str(e)
    except Exception as e:
        return [], f"Error generando imagen: {e}"

router = APIRouter(prefix="/api/projects/{pid}/campaigns", tags=["campaigns"])

ASSET_KINDS = [
    "slogan", "logo", "brochure", "newsletter", "banner",
    "post", "video", "infographic", "email", "ideas",
]


class CampaignCreate(BaseModel):
    name: str
    goal: str | None = None
    brief: str | None = None
    selectors: dict[str, Any]
    # Selectors expected keys:
    #   ideas: bool
    #   slogan: bool
    #   logo: bool
    #   brochure: bool
    #   newsletter: bool
    #   banner: bool
    #   posts: list[{platform, kind: text|image|video|infographic, prompt?}]
    channels: list[str] | None = None


class PredictRequest(BaseModel):
    audience_size: int = 1000
    budget_eur: float = 0
    duration_days: int = 30
    channels: list[str] | None = None


class RoiRequest(BaseModel):
    cost_per_unit_eur: float
    selling_price_eur: float
    expected_units: int | None = None
    fixed_costs_eur: float = 0
    other_variable_costs_eur: float = 0
    audience_size: int = 1000
    duration_days: int = 30
    channels: list[str] | None = None


class EmailBatchRequest(BaseModel):
    subject_template: str | None = None
    body_template: str | None = None
    use_ai: bool = True
    ab_test: bool = True
    send: bool = True  # si False sólo prepara (con tracking) sin enviar
    test_mode: bool = False  # si True envía todos los emails a override_to
    override_to: str | None = None  # email donde mandar todo cuando test_mode=True


@router.get("")
def list_campaigns(pid: str, db: Session = Depends(get_db)):
    rows = db.query(Campaign).filter(Campaign.project_id == pid).order_by(Campaign.created_at.desc()).all()
    return [_camp_dict(c, with_assets=False) for c in rows]


@router.post("")
def create_campaign(pid: str, body: CampaignCreate, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)

    c = Campaign(
        project_id=pid,
        name=body.name,
        goal=body.goal,
        brief=body.brief,
        selectors=body.selectors,
        channels=body.channels or [],
        status="draft",
    )
    db.add(c)
    db.flush()

    profile = (p.research or {}).get("profile") or {}
    brand = p.brand_kit or {}
    personas = p.personas or []
    products = p.products or []
    ctx = (
        f"Marca: {p.full_name or p.name}\n"
        f"Sector: {profile.get('sector','')}\n"
        f"Tono: {brand.get('tono','')}\n"
        f"Claims: {brand.get('claims', [])}\n"
        f"Colores: {brand.get('colores', [])}\n"
        f"Personas: {[(pp.get('nombre'), pp.get('jobs_to_be_done')) for pp in personas[:2]]}\n"
        f"Productos: {[pp.get('name') for pp in products]}\n"
        f"Brief: {body.brief or ''}\n"
        f"Objetivo: {body.goal or ''}\n"
    )

    sel = body.selectors or {}

    # 1) Ideas / informe completo
    if sel.get("ideas"):
        out = providers.call_json(
            ctx + "\nGenera 8 ideas creativas de campaña con: titulo, idea, formato, canales, kpi, presupuesto_estimado_eur. "
                  "Devuelve JSON {ideas: [...]}.",
            system="Eres director creativo.",
        )
        _save_asset(db, c, kind="ideas", title="Ideas de campaña", text=str(out.get("data")), meta={"raw": out.get("data")})

    # 2) Eslogan
    if sel.get("slogan"):
        out = providers.call_json(
            ctx + "\nGenera 5 eslóganes cortos (máx 8 palabras) en español. JSON {slogans: [{texto, racional}]}.",
        )
        slogans = (out.get("data") or {}).get("slogans") or []
        for s in slogans:
            _save_asset(db, c, kind="slogan", title=s.get("texto"), text=s.get("racional"), meta=s)

    # 3) Logo
    if sel.get("logo"):
        prompt = (
            f"Logo profesional para {p.full_name or p.name}. Sector: {profile.get('sector','')}. "
            f"Tono: {brand.get('tono','')}. Estilo limpio, vectorial, fondo blanco, alto contraste. "
            f"Sin texto si es difícil de renderizar."
        )
        imgs, img_err = _safe_images(prompt, n=2, aspect="1:1")
        for i, b64 in enumerate(imgs):
            _save_asset(db, c, kind="logo", title=f"Logo opción {i+1}", image_data=b64, meta={"prompt": prompt})
        if img_err and not imgs:
            _save_asset(db, c, kind="logo", title="Logo (pendiente)", text=img_err, meta={"prompt": prompt, "error": img_err})

    # 4) Folleto (brochure) — texto + imagen banner
    if sel.get("brochure"):
        out = providers.call_json(
            ctx + "\nCrea un folleto comercial A4 con secciones (titular, subtitular, beneficios, "
                  "casos de éxito breves, llamada a acción, contacto). Devuelve JSON {brochure: {...}}.",
        )
        b64, img_err = _safe_images(
            f"Folleto A4 vertical para {p.full_name or p.name} sector {profile.get('sector','')}, "
            f"colores {brand.get('colores', ['#0EA5E9','#111827'])}, estilo moderno, espacio para texto.",
            n=1, aspect="9:16",
        )
        _save_asset(db, c, kind="brochure", title="Folleto",
                    text=str((out.get("data") or {}).get("brochure")),
                    image_data=b64[0] if b64 else None,
                    meta={"raw": out.get("data"), "image_error": img_err})

    # 5) Newsletter
    if sel.get("newsletter"):
        out = providers.call_json(
            ctx + "\nRedacta una newsletter HTML completa para {audiencia: ICP} con: pre-header, "
                  "asunto (2 variantes A/B), saludo, 3 secciones, CTA, P.D., footer con baja. "
                  "JSON {asunto_a, asunto_b, preheader, html_body}.",
        )
        nd = out.get("data") or {}
        _save_asset(db, c, kind="newsletter", title=nd.get("asunto_a") or "Newsletter",
                    text=nd.get("html_body"), meta=nd)

    # 6) Banner
    if sel.get("banner"):
        prompt = (
            f"Banner publicitario web 16:9 para {p.full_name or p.name}, "
            f"colores {brand.get('colores', ['#0EA5E9','#111827'])}, claim '{(brand.get('claims') or ['Calidad y confianza'])[0]}', "
            f"estilo moderno, espacio para logo arriba a la izquierda."
        )
        imgs, img_err = _safe_images(prompt, n=1, aspect="16:9")
        for i, b64 in enumerate(imgs):
            _save_asset(db, c, kind="banner", title=f"Banner {i+1}", image_data=b64, meta={"prompt": prompt})
        if img_err and not imgs:
            _save_asset(db, c, kind="banner", title="Banner (pendiente)", text=img_err, meta={"prompt": prompt, "error": img_err})

    # 7) Posts redes sociales
    posts_spec = sel.get("posts") or []
    for spec in posts_spec:
        platform = spec.get("platform", "instagram")
        kind = spec.get("kind", "text+image")
        custom_prompt = spec.get("prompt") or ""

        copy_out = providers.call_json(
            ctx
            + f"\nCrea un post para {platform}. Tipo: {kind}. {custom_prompt}\n"
              f"Devuelve JSON {{texto, hashtags:[...], cta, alt_text, prompt_imagen}}.",
        )
        cd = copy_out.get("data") or {}
        text = cd.get("texto") or ""
        hashtags = " ".join(cd.get("hashtags") or [])
        body_text = (text + "\n\n" + hashtags).strip()

        if "image" in kind or "infographic" in kind or "text+image" in kind:
            img_prompt = cd.get("prompt_imagen") or f"Imagen para post {platform} de {p.full_name or p.name}"
            aspect = "1:1" if platform in ("instagram", "facebook") else "9:16" if platform == "tiktok" else "16:9"
            imgs, img_err = _safe_images(img_prompt, n=1, aspect=aspect)
            _save_asset(
                db, c, kind="post", title=f"Post {platform}",
                text=body_text, image_data=imgs[0] if imgs else None,
                meta={"platform": platform, "kind": kind, "prompt_imagen": img_prompt, "alt_text": cd.get("alt_text"), "image_error": img_err},
            )
        elif kind == "video":
            vid = providers.call_video(cd.get("prompt_imagen") or text)
            _save_asset(
                db, c, kind="video", title=f"Vídeo {platform}",
                text=body_text, meta={"platform": platform, "video_url": vid.get("url"), "raw": vid},
            )
        elif kind == "infographic":
            img_prompt = f"Infografía vertical sobre: {text[:200]}"
            imgs, img_err = _safe_images(img_prompt, n=1, aspect="9:16")
            _save_asset(
                db, c, kind="infographic", title=f"Infografía {platform}",
                text=body_text, image_data=imgs[0] if imgs else None,
                meta={"platform": platform, "prompt_imagen": img_prompt, "image_error": img_err},
            )
        else:  # solo texto
            _save_asset(db, c, kind="post", title=f"Post {platform}", text=body_text,
                        meta={"platform": platform, "kind": "text"})

    db.flush()
    return _camp_dict(c, with_assets=True)


@router.get("/{cid}")
def get_campaign(pid: str, cid: str, db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c or c.project_id != pid:
        raise HTTPException(404)
    return _camp_dict(c, with_assets=True)


@router.post("/{cid}/assets/{aid}/approve")
def approve_asset(pid: str, cid: str, aid: str, db: Session = Depends(get_db)):
    a = db.get(Asset, aid)
    if not a or a.campaign_id != cid:
        raise HTTPException(404)
    a.approved = True
    db.flush()
    return {"ok": True}


# ---------------- Predicción ----------------

@router.post("/{cid}/predict")
def predict(pid: str, cid: str, body: PredictRequest, db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c or c.project_id != pid:
        raise HTTPException(404)

    p = db.get(Project, pid)
    profile = (p.research or {}).get("profile") or {}
    channels = body.channels or c.channels or ["email", "instagram", "facebook"]
    benchmarks = {
        "email": {"open": 0.22, "ctr": 0.025, "conv": 0.012},
        "instagram": {"engagement": 0.018, "ctr": 0.006, "conv": 0.005},
        "facebook": {"engagement": 0.012, "ctr": 0.009, "conv": 0.007},
        "linkedin": {"engagement": 0.020, "ctr": 0.004, "conv": 0.008},
        "tiktok": {"engagement": 0.054, "ctr": 0.010, "conv": 0.004},
        "twitter": {"engagement": 0.009, "ctr": 0.003, "conv": 0.002},
        "google_ads": {"ctr": 0.039, "conv": 0.038},
    }

    rows = []
    total_conv = 0
    for ch in channels:
        b = benchmarks.get(ch, {"ctr": 0.01, "conv": 0.01})
        size = body.audience_size
        clicks = int(size * b.get("ctr", 0.01))
        convs = int(size * b.get("conv", 0.005))
        total_conv += convs
        rows.append({
            "channel": ch,
            "audiencia": size,
            "clicks_estimados": clicks,
            "conversiones_estimadas": convs,
            "engagement_pct": round(b.get("engagement", b.get("open", 0)) * 100, 2),
            "ctr_pct": round(b.get("ctr", 0) * 100, 2),
            "conv_pct": round(b.get("conv", 0) * 100, 2),
        })

    # Refinar con IA si hay
    ai_out = providers.call_json(
        f"Sector: {profile.get('sector','')}. Audiencia: {body.audience_size}. Presupuesto: {body.budget_eur}€. "
        f"Duración: {body.duration_days} días. Canales: {channels}. "
        "Estima resultados realistas y un rango de confianza. JSON {summary, rango_conversiones:[min,max], "
        "rango_alcance:[min,max], riesgos:[...], oportunidades:[...]}.",
    )
    ai_data = ai_out.get("data") or {}

    result = {
        "channels": rows,
        "total_conversiones_estimadas": total_conv,
        "ai_refinement": ai_data,
        "degraded": ai_out.get("degraded", False),
    }
    c.prediction = result
    db.flush()
    return result


# ---------------- ROI ----------------

@router.post("/{cid}/roi")
def roi_calc(pid: str, cid: str, body: RoiRequest, db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c or c.project_id != pid:
        raise HTTPException(404)
    expected_units = body.expected_units
    if expected_units is None:
        # estimar desde la predicción si existe
        pred = c.prediction or {}
        expected_units = int(pred.get("total_conversiones_estimadas", 0)) or max(1, body.audience_size // 100)

    revenue = expected_units * body.selling_price_eur
    variable_costs = expected_units * body.cost_per_unit_eur + body.other_variable_costs_eur
    total_cost = body.fixed_costs_eur + variable_costs
    profit = revenue - total_cost
    roi_pct = (profit / total_cost * 100) if total_cost else 0
    breakeven_units = (body.fixed_costs_eur / max(body.selling_price_eur - body.cost_per_unit_eur, 0.01)) if body.selling_price_eur > body.cost_per_unit_eur else None
    cac = (total_cost / expected_units) if expected_units else None

    # Atribución multicanal naive: reparte profit proporcional a CTR/Conv del benchmark si hay channels
    attribution = []
    if c.prediction and c.prediction.get("channels"):
        total_conv = sum(x.get("conversiones_estimadas", 0) for x in c.prediction["channels"]) or 1
        for ch in c.prediction["channels"]:
            share = ch.get("conversiones_estimadas", 0) / total_conv
            attribution.append({
                "channel": ch["channel"],
                "share_pct": round(share * 100, 1),
                "estimated_revenue_eur": round(revenue * share, 2),
                "estimated_profit_eur": round(profit * share, 2),
            })

    result = {
        "revenue_eur": round(revenue, 2),
        "total_cost_eur": round(total_cost, 2),
        "profit_eur": round(profit, 2),
        "roi_pct": round(roi_pct, 1),
        "breakeven_units": round(breakeven_units, 1) if breakeven_units else None,
        "cac_eur": round(cac, 2) if cac else None,
        "expected_units": expected_units,
        "attribution_per_channel": attribution,
    }
    c.roi = result
    db.flush()
    return result


# ---------------- Email batch (módulo 4 / 9) ----------------

@router.post("/{cid}/email-batch")
def email_batch(pid: str, cid: str, body: EmailBatchRequest, db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c or c.project_id != pid:
        raise HTTPException(404)
    p = db.get(Project, pid)
    leads = db.query(Lead).filter(Lead.project_id == pid).all()
    if not leads:
        raise HTTPException(400, "No hay leads. Genera leads en el módulo 4 primero.")

    settings = get_settings()
    base_track = settings.public_backend_url.rstrip("/")

    sends_out = []
    for i, lead in enumerate(leads):
        if not lead.email:
            continue
        variant = "A" if (not body.ab_test or i % 2 == 0) else "B"
        if body.use_ai:
            out = providers.call_json(
                f"Marca: {p.full_name or p.name}. Producto/servicio: {[pp.get('name') for pp in (p.products or [])]}. "
                f"Lead: {lead.name}, sector {lead.sector or ''}. "
                f"Variante {variant}. Genera email de prospección personalizado: "
                "JSON {asunto, html_body (con <a href='{{CTA_URL}}'>CTA</a> y {{UNSUBSCRIBE_URL}}), preview_text}.",
            )
            ed = out.get("data") or {}
            subject = ed.get("asunto") or f"Una propuesta para {lead.name}"
            html_body = ed.get("html_body") or f"<p>Hola {lead.name}, queríamos hablarte de nuestros servicios.</p>"
        else:
            subject = (body.subject_template or "Propuesta para {{name}}").replace("{{name}}", lead.name)
            html_body = (body.body_template or "<p>Hola {{name}}, una propuesta para ti.</p>").replace("{{name}}", lead.name)

        send = EmailSend(
            campaign_id=cid, lead_id=lead.id, to_email=lead.email,
            subject=subject, body_html="", variant=variant,
        )
        db.add(send)
        db.flush()

        # Insertar pixel + reescribir links a /track/click/{send.id}?u=...
        cta_default = lead.website or "https://example.com"
        html_body = html_body.replace("{{CTA_URL}}", cta_default)
        html_body = html_body.replace("{{UNSUBSCRIBE_URL}}", f"{base_track}/api/track/unsub/{send.id}")
        html_body = _rewrite_links(html_body, send.id, base_track)
        html_body += f'<img src="{base_track}/api/track/open/{send.id}.png" width="1" height="1" alt=""/>'
        send.body_html = html_body
        db.flush()

        sent_info: dict[str, Any] = {"id": send.id, "to": lead.email, "subject": subject, "variant": variant}
        if body.send:
            to_email = body.override_to if (body.test_mode and body.override_to) else lead.email
            try:
                res = send_email(
                    to=to_email,
                    subject=subject,
                    html=html_body,
                    from_name=(p.full_name or p.name),
                )
                send.sent_at = dt.datetime.utcnow()
                db.flush()
                sent_info["sent"] = True
                sent_info["provider"] = res.get("provider")
                if body.test_mode:
                    sent_info["actually_sent_to"] = to_email
            except EmailProviderMissing as e:
                raise HTTPException(400, str(e))
            except EmailSendError as e:
                sent_info["sent"] = False
                sent_info["error"] = str(e)
        else:
            sent_info["sent"] = False

        sends_out.append(sent_info)

    sent_count = sum(1 for s in sends_out if s.get("sent"))
    failed_count = sum(1 for s in sends_out if s.get("sent") is False and s.get("error"))
    c.status = "sent" if sent_count > 0 else "prepared"
    db.flush()
    note = (
        f"{sent_count} emails enviados realmente; {failed_count} fallaron; "
        f"{len(sends_out) - sent_count - failed_count} preparados sin enviar."
    )
    return {"sends": sends_out, "count": len(sends_out), "sent_count": sent_count, "failed_count": failed_count, "note": note}


def _rewrite_links(html: str, send_id: str, base: str) -> str:
    def repl(m: re.Match) -> str:
        url = m.group(1)
        if "track/" in url or url.startswith("mailto:") or url.startswith("#"):
            return m.group(0)
        return f'href="{base}/api/track/click/{send_id}?u={url}"'
    return re.sub(r'href="([^"]+)"', repl, html)


# ---------------- helpers ----------------

def _save_asset(db: Session, c: Campaign, *, kind: str, title: str | None = None,
                text: str | None = None, image_data: str | None = None, meta: dict | None = None) -> Asset:
    a = Asset(
        campaign_id=c.id, kind=kind, title=title, text=text,
        image_data=image_data, meta=meta or {},
    )
    db.add(a)
    db.flush()
    return a


def _camp_dict(c: Campaign, *, with_assets: bool) -> dict:
    d = {
        "id": c.id, "name": c.name, "goal": c.goal, "brief": c.brief,
        "channels": c.channels, "selectors": c.selectors, "status": c.status,
        "prediction": c.prediction, "roi": c.roi,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    if with_assets:
        d["assets"] = [{
            "id": a.id, "kind": a.kind, "title": a.title, "text": a.text,
            "image_data": a.image_data, "meta": a.meta,
            "approved": a.approved,
            "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
        } for a in c.assets]
    return d
