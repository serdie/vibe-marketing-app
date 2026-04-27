from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import providers
from ..db import get_db
from ..models import Project
from ..scraping import basic_seo_audit, extract_contacts, fetch

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    owner_type: str = "empresa"  # empresa | autonomo | particular
    website: str | None = None
    full_name: str | None = None
    cv_text: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    owner_type: str | None = None
    website: str | None = None
    full_name: str | None = None
    cv_text: str | None = None
    brand_kit: dict | None = None


class GapsRequest(BaseModel):
    extra_context: str | None = None


class ProductDefine(BaseModel):
    products: list[dict]  # [{name, description, price, category}]
    notes: str | None = None


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    rows = db.query(Project).order_by(Project.updated_at.desc()).all()
    return [_to_summary(p) for p in rows]


@router.post("")
def create_project(p: ProjectCreate, db: Session = Depends(get_db)):
    proj = Project(**p.model_dump())
    db.add(proj)
    db.flush()
    return _to_full(proj)


@router.get("/{pid}")
def get_project(pid: str, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    return _to_full(p)


@router.put("/{pid}")
def update_project(pid: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.flush()
    return _to_full(p)


@router.delete("/{pid}")
def delete_project(pid: str, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    db.delete(p)
    return {"ok": True}


# ---------------- MÓDULO 1: Research del propietario (deep search) ----------------

@router.post("/{pid}/research")
def research_owner(pid: str, db: Session = Depends(get_db)):
    """
    Investigación profunda en 3 pasadas:
    1. Scraping directo de la web (contactos, SEO técnico, redes detectadas, texto)
    2. Búsqueda grounded #1: identidad y hechos verificables (qué es, dónde, cuándo, quiénes)
    3. Búsqueda grounded #2: actividad digital y reputación (redes, reseñas, menciones, noticias)
    4. Síntesis JSON estructurada usando todo lo anterior + CV/notas del propietario.
    """
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)

    # ----- 1) Scrape directo de la web -----
    web_data: dict[str, Any] = {}
    seo: dict[str, Any] = {}
    if p.website:
        status, html = fetch(p.website)
        if status and html:
            web_data = extract_contacts(html, base_url=p.website)
            seo = basic_seo_audit(html)
        else:
            web_data = {"error": f"No se pudo descargar {p.website} (status {status})"}

    # ----- 2) Pasada grounded: identidad ------
    base_id = []
    if p.full_name:
        base_id.append(f"Nombre/razón social: {p.full_name}")
    if p.website:
        base_id.append(f"Web: {p.website}")
    base_id.append(f"Tipo: {p.owner_type}")
    if p.cv_text:
        base_id.append(f"CV/notas del propio interesado:\n{p.cv_text[:3000]}")
    if web_data.get("text_excerpt"):
        base_id.append(f"Texto extraído directamente de la web del propietario:\n{web_data['text_excerpt'][:2500]}")
    if web_data.get("emails"):
        base_id.append(f"Emails detectados en la web: {', '.join(list(web_data['emails'])[:5])}")
    if web_data.get("phones"):
        base_id.append(f"Teléfonos detectados: {', '.join(list(web_data['phones'])[:5])}")
    if web_data.get("socials"):
        base_id.append(f"Redes sociales detectadas en la web: {web_data['socials']}")

    base_block = "\n".join(base_id)

    identity_q = (
        "Investiga en internet con búsquedas concretas y devuelve hechos verificables sobre el propietario.\n"
        "DATOS DE PARTIDA (úsalos al pie de la letra, no inventes):\n"
        f"{base_block}\n\n"
        "Quiero hechos concretos: actividad real, ubicación exacta (ciudad, país), año "
        "aproximado de fundación o trayectoria, dimensiones (nº empleados estimado, ámbito local/nacional/internacional), "
        "productos/servicios reales que comercializa, sectores en los que opera, "
        "cargo/perfil del responsable o equipo conocido, presencia geográfica, idiomas en los que opera. "
        "Cita las fuentes exactas. Si no encuentras dato, indícalo como 'desconocido'. NUNCA mezcles con otros negocios "
        "de nombre parecido."
    )
    identity_out = providers.call_text(identity_q, grounded=True)

    # ----- 3) Pasada grounded: actividad digital y reputación -----
    digital_q = (
        "Sobre el MISMO propietario que en la consulta anterior, busca su actividad digital y reputación:\n"
        f"{base_block}\n\n"
        "Cubre: \n"
        "- Cuentas oficiales en redes (instagram, facebook, linkedin, tiktok, youtube, x/twitter): URL, "
        "nº seguidores aproximado, frecuencia y tipo de publicaciones.\n"
        "- Reseñas en Google Maps / Trustpilot / TripAdvisor / Glassdoor si aplica: nota media, nº reseñas, temas frecuentes positivos y negativos.\n"
        "- Menciones en prensa, blogs o directorios sectoriales (con URL y fecha si la hay).\n"
        "- Apariciones en foros, podcasts, YouTube, etc.\n"
        "- Posicionamiento aparente (qué le diferencia o no del resto del sector).\n"
        "Si un dato no existe o no es público, ponlo como 'no encontrado'. Cita fuentes."
    )
    digital_out = providers.call_text(digital_q, grounded=True)

    # ----- 4) Síntesis JSON estructurada -----
    synth_prompt = (
        "Eres analista senior de inteligencia de mercado. Estructura toda la información investigada en un JSON "
        "muy completo. Usa SOLO los datos proporcionados, no inventes; si un dato falta, déjalo vacío o como 'desconocido'.\n\n"
        f"### DATOS DE ENTRADA DEL PROPIETARIO ###\n{base_block}\n\n"
        f"### INVESTIGACIÓN DE IDENTIDAD ###\n{(identity_out.get('text') or '')[:6000]}\n\n"
        f"### INVESTIGACIÓN DIGITAL Y REPUTACIÓN ###\n{(digital_out.get('text') or '')[:6000]}\n\n"
        f"### AUDITORÍA SEO TÉCNICA DE LA WEB ###\nscore={seo.get('score', '?')} / 100\n"
        f"issues={seo.get('issues', [])}\n\n"
        "Devuelve **JSON estricto** con esta forma exacta (no añadas markdown, no envuelvas en ``` ni en texto):\n"
        "{\n"
        '  "summary": "resumen ejecutivo de 4-6 frases sobre quién es y qué hace, basado en hechos",\n'
        '  "sector": "sector principal con detalle (no genérico)",\n'
        '  "subsectores": ["lista corta"],\n'
        '  "actividad_principal": "qué hace exactamente",\n'
        '  "productos_servicios": [{"nombre":"", "descripcion":"", "precio_aprox":"", "publico":""}],\n'
        '  "publicos_objetivo": ["B2B/B2C/etc con detalle"],\n'
        '  "ubicacion": {"ciudad":"", "provincia":"", "pais":"", "ambito":"local|nacional|internacional"},\n'
        '  "año_fundacion": "",\n'
        '  "tamano": "estimado (nº empleados o autónomo individual)",\n'
        '  "tono_marca": "tono de comunicación",\n'
        '  "idiomas": [],\n'
        '  "propuesta_valor": "diferenciación clara en 1-2 frases",\n'
        '  "ventajas_competitivas": ["3-5 puntos"],\n'
        '  "presencia_digital": {\n'
        '    "web": {"url":"", "puntuacion_seo":0, "principales_problemas":[]},\n'
        '    "redes": [{"plataforma":"instagram", "url":"", "seguidores_aprox":"", "frecuencia":"", "calidad":"alta|media|baja"}]\n'
        '  },\n'
        '  "reputacion": {"google_maps":{"nota":"", "nº_reseñas":"", "temas_positivos":[], "temas_negativos":[]}, "otras_plataformas":[]},\n'
        '  "fortalezas": [],\n'
        '  "debilidades": [],\n'
        '  "riesgos": [],\n'
        '  "oportunidades_inmediatas": ["3-5 acciones que se podrían ejecutar esta semana"],\n'
        '  "keywords_seo_recomendadas": [],\n'
        '  "noticias_recientes": [{"titulo":"", "url":"", "fecha":""}],\n'
        '  "competidores_inicial": [{"nombre":"", "web":""}]\n'
        "}\n"
        "JSON válido y nada más."
    )
    synth = providers.call_json(synth_prompt, system="Analista riguroso de inteligencia de mercado. Solo hechos.")

    research = synth.get("data") or {}
    if isinstance(research, dict):
        # mezcla fuentes y metadatos
        srcs = []
        for o in (identity_out, digital_out):
            for s in o.get("grounded_sources") or []:
                if s and s not in srcs:
                    srcs.append(s)
        research["sources"] = srcs
        research["model"] = synth.get("model")
        research["degraded"] = bool(
            (identity_out.get("degraded") and digital_out.get("degraded")) or synth.get("degraded")
        )
        research["raw_identity"] = (identity_out.get("text") or "")[:4000]
        research["raw_digital"] = (digital_out.get("text") or "")[:4000]

    p.research = {
        "profile": research,
        "web_scrape": web_data,
        "seo_audit": seo,
    }
    db.flush()
    return p.research


# ---------------- MÓDULO 2: Gaps + Competencia ----------------

@router.post("/{pid}/gaps")
def gaps_analyze(pid: str, body: GapsRequest, db: Session = Depends(get_db)):
    """
    Análisis profundo de carencias en 3 pasadas:
    1. Grounded #1: identificación de 5 competidores reales con datos (web, ubicación, productos, redes).
    2. Grounded #2: comparativa cuantificada en 10 ejes vs propietario.
    3. Síntesis: SWOT, 8-12 carencias clasificadas, plan de 8 acciones priorizadas.
    """
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    profile = (p.research or {}).get("profile") or {}
    web_scrape = (p.research or {}).get("web_scrape") or {}
    seo = (p.research or {}).get("seo_audit") or {}

    sector = profile.get("sector") or ""
    subsectores = profile.get("subsectores") or []
    actividad = profile.get("actividad_principal") or ""
    productos_serv = profile.get("productos_servicios") or []
    location_obj = profile.get("ubicacion") or {}
    if isinstance(location_obj, str):
        location_str = location_obj
    else:
        location_str = ", ".join([str(v) for v in [location_obj.get("ciudad"), location_obj.get("provincia"), location_obj.get("pais")] if v])
    name = p.full_name or p.name
    initial_competitors = profile.get("competidores_inicial") or []
    presencia = profile.get("presencia_digital") or {}
    reputacion = profile.get("reputacion") or {}

    summary_block = (
        f"Propietario: {name}\n"
        f"Tipo: {p.owner_type}\n"
        f"Sector: {sector}\n"
        f"Subsectores: {', '.join(subsectores) if isinstance(subsectores, list) else subsectores}\n"
        f"Actividad principal: {actividad}\n"
        f"Ubicación: {location_str}\n"
        f"Web: {p.website or 'N/A'} | SEO score: {seo.get('score','?')} (issues: {(seo.get('issues') or [])[:5]})\n"
        f"Productos/servicios: {productos_serv[:6]}\n"
        f"Redes detectadas en web: {web_scrape.get('socials', {})}\n"
        f"Presencia digital declarada: {presencia}\n"
        f"Reputación: {reputacion}\n"
        f"Competidores iniciales sugeridos: {initial_competitors[:5]}\n"
        f"{('Contexto extra del usuario: ' + body.extra_context) if body.extra_context else ''}"
    )

    # Pasada 1: competidores reales con grounding
    comp_q = (
        "Eres consultor experto. Identifica 5 EMPRESAS COMPETIDORAS REALES y operativas (no genéricas) del propietario "
        "descrito a continuación, en su mismo sector y, cuando sea posible, misma zona geográfica.\n"
        f"\n{summary_block}\n\n"
        "Para CADA competidor devuelve:\n"
        "- nombre comercial real\n"
        "- web (URL real verificada)\n"
        "- ubicación (ciudad/país)\n"
        "- productos/servicios principales\n"
        "- canales digitales activos (web/blog, redes con nombre y URL si conoces, marketplaces)\n"
        "- reseñas Google/Trustpilot (nota y nº si conoces)\n"
        "- precio aproximado o gama de precios\n"
        "- ventaja diferencial percibida\n"
        "- por qué compite con el propietario\n"
        "Cita las fuentes (URLs)."
    )
    comp_out = providers.call_text(comp_q, grounded=True)

    # Pasada 2: comparativa en 10 ejes
    comp_axes_q = (
        "Sobre los competidores que acabas de identificar y el propietario, hazme una comparativa "
        "cuantificada eje por eje. Si no hay dato, marca 'desconocido'. No inventes:\n"
        f"{summary_block}\n\n"
        "Investigación previa de competidores:\n"
        f"{(comp_out.get('text') or '')[:6000]}\n\n"
        "Ejes a evaluar (puntúa 1-10 cuando sea posible y explica brevemente):\n"
        "1. Calidad de la web (UX, velocidad, claridad)\n"
        "2. SEO técnico (metas, performance, crawlable)\n"
        "3. Blog / contenidos propios (frecuencia, profundidad)\n"
        "4. Presencia en redes sociales y nº seguidores estimados\n"
        "5. Calidad y consistencia visual de la marca\n"
        "6. Atención al cliente (canales, tiempos)\n"
        "7. Reputación online (reseñas, ratings)\n"
        "8. Propuesta de valor diferenciada\n"
        "9. Política de precios visibles\n"
        "10. Programa de fidelización / contenidos descargables / lead magnets\n"
        "Para cada eje y cada competidor da nota_propietario, nota_competidor, brecha (-N a +N) y comentario."
    )
    axes_out = providers.call_text(comp_axes_q, grounded=True)

    # Pasada 3: síntesis JSON
    synth_q = (
        "Estructura todo lo anterior en JSON estricto. NO inventes datos: si algo no se conoce, ponlo como 'desconocido'.\n\n"
        f"### PROPIETARIO ###\n{summary_block}\n\n"
        f"### INVESTIGACIÓN COMPETIDORES ###\n{(comp_out.get('text') or '')[:6000]}\n\n"
        f"### COMPARATIVA POR EJES ###\n{(axes_out.get('text') or '')[:6000]}\n\n"
        "Devuelve JSON con esta forma EXACTA y nada más:\n"
        "{\n"
        '  "competidores": [{"nombre":"", "web":"", "ubicacion":"", "productos":[], "canales":[], "resenas":"", "precio_aprox":"", "ventaja_diferencial":"", "por_que_compite":"", "fortalezas":[], "debilidades":[]}],\n'
        '  "comparativa": [{"eje":"", "nota_propietario":0, "nota_lider":0, "brecha":0, "comentario":""}],\n'
        '  "swot_propietario": {"fortalezas":[], "debilidades":[], "oportunidades":[], "amenazas":[]},\n'
        '  "carencias": [{"area":"", "descripcion":"", "evidencia":"", "prioridad":"alta|media|baja", "impacto":"alto|medio|bajo", "esfuerzo":"alto|medio|bajo"}],\n'
        '  "plan_accion": [{"tarea":"", "objetivo":"", "responsable_sugerido":"", "kpi":"", "esfuerzo":"alto|medio|bajo", "impacto":"alto|medio|bajo", "coste_estimado_eur":0, "plazo_dias":0}],\n'
        '  "redes_recomendadas": [{"plataforma":"", "razon":"", "primer_post_idea":""}],\n'
        '  "quick_wins_30_dias": ["3-5 acciones concretas inmediatas"],\n'
        '  "tesis_estrategica": "1-2 párrafos sobre cómo posicionarse contra la competencia"\n'
        "}\n"
        "Mínimo 5 competidores, 8 carencias, 8 acciones en plan_accion. JSON válido sin markdown."
    )
    synth = providers.call_json(synth_q, system="Consultor senior de marketing. Riguroso, sin invenciones.")
    data = synth.get("data") or {}
    if isinstance(data, dict):
        srcs = []
        for o in (comp_out, axes_out):
            for s in o.get("grounded_sources") or []:
                if s and s not in srcs:
                    srcs.append(s)
        data["sources"] = srcs
        data["model"] = synth.get("model")
        data["degraded"] = bool((comp_out.get("degraded") and axes_out.get("degraded")) or synth.get("degraded"))
        data["raw_competitors_research"] = (comp_out.get("text") or "")[:4000]
        data["raw_axes_research"] = (axes_out.get("text") or "")[:4000]
    p.gaps = data
    p.competitors = data.get("competidores") if isinstance(data, dict) else None
    db.flush()
    return data


# ---------------- MÓDULO 3: Producto + ICP / Personas ----------------

@router.post("/{pid}/product")
def product_define(pid: str, body: ProductDefine, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    profile = (p.research or {}).get("profile") or {}

    p.products = body.products

    prompt = (
        f"Eres estratega de marketing. Para los productos siguientes y el propietario dado, "
        f"genera el **cliente ideal (ICP)** y 3 buyer personas detalladas.\n\n"
        f"Propietario: {p.full_name or p.name} | Sector: {profile.get('sector','')} | "
        f"Ubicación: {profile.get('ubicacion','')}.\n"
        f"Productos:\n" + "\n".join([f"- {pp.get('name')}: {pp.get('description','')}" for pp in body.products]) +
        f"\nNotas extra: {body.notes or ''}\n\n"
        "Devuelve JSON con keys:\n"
        "  icp: {sector_principal, sectores_secundarios[], tamano_empresa, geo, "
        "presupuesto_compra, momento_compra, criterios_decision[], canales_donde_buscan[]},\n"
        "  buyer_personas: [{nombre, rol, edad, perfil_personal, jobs_to_be_done[], "
        "dolores[], objeciones[], objetivos[], mensajes_clave[], canales_preferidos[]}],\n"
        "  productos_match: [{producto, persona, por_que_encaja}].\n"
        "Sin markdown, JSON válido."
    )
    out = providers.call_json(prompt, system="Genera ICPs realistas y específicos.")
    data = out.get("data") or {}
    if isinstance(data, dict):
        p.icp = data.get("icp")
        p.personas = data.get("buyer_personas") or []
    db.flush()
    return data


# ---------------- BRAND KIT ----------------

class BrandKitBody(BaseModel):
    colores: list[str] | None = None  # hex
    fuentes: list[str] | None = None
    logo_b64: str | None = None
    tono: str | None = None
    claims: list[str] | None = None
    palabras_prohibidas: list[str] | None = None


@router.put("/{pid}/brand-kit")
def set_brand_kit(pid: str, body: BrandKitBody, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    p.brand_kit = body.model_dump(exclude_none=True)
    db.flush()
    return p.brand_kit


@router.post("/{pid}/brand-kit/auto")
def auto_brand_kit(pid: str, db: Session = Depends(get_db)):
    """Sugiere brand kit basado en el research del propietario."""
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404)
    profile = (p.research or {}).get("profile") or {}
    prompt = (
        f"Sugiere un brand kit para: {p.full_name or p.name}, sector {profile.get('sector','')}.\n"
        f"Tono actual detectado: {profile.get('tono_marca','')}.\n"
        "Devuelve JSON: {colores: [4 hex], fuentes: [2], tono: '...', "
        "claims: [3 lemas cortos], palabras_prohibidas: [...]}. JSON válido."
    )
    out = providers.call_json(prompt)
    data = out.get("data") or {}
    if isinstance(data, dict):
        p.brand_kit = data
    db.flush()
    return data


# ---------------- helpers ----------------

def _to_summary(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "owner_type": p.owner_type,
        "website": p.website,
        "full_name": p.full_name,
        "has_research": bool(p.research),
        "has_gaps": bool(p.gaps),
        "has_products": bool(p.products),
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _to_full(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "owner_type": p.owner_type,
        "website": p.website,
        "full_name": p.full_name,
        "cv_text": p.cv_text,
        "research": p.research,
        "gaps": p.gaps,
        "competitors": p.competitors,
        "products": p.products,
        "icp": p.icp,
        "personas": p.personas,
        "brand_kit": p.brand_kit,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
