"""Wrapper sobre Google Gemini (texto, imagen, grounding) y fallback Qwen.

Diseño: si no hay GEMINI_API_KEY, devolvemos respuestas deterministas/heurísticas
para que la app siga siendo demostrable, y marcamos `degraded=True` en la respuesta.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

from .config import get_settings

log = logging.getLogger("ai")
_settings = get_settings()

try:
    from google import genai
    from google.genai import types as gtypes
    _GENAI_OK = True
except Exception as e:  # pragma: no cover
    log.warning("google-genai not importable: %s", e)
    genai = None  # type: ignore
    gtypes = None  # type: ignore
    _GENAI_OK = False


def _client():
    if not _GENAI_OK or not _settings.gemini_api_key:
        return None
    try:
        return genai.Client(api_key=_settings.gemini_api_key)
    except Exception as e:
        log.warning("Cannot init genai client: %s", e)
        return None


def has_ai() -> bool:
    return _client() is not None


def gen_text(
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = False,
    grounded: bool = False,
    model: str | None = None,
    max_retries: int = 2,
) -> dict:
    """Genera texto con Gemini. Retorna {text, raw, grounded_sources, degraded}."""
    cli = _client()
    used_model = model or (_settings.pro_model if grounded else _settings.text_model)
    if cli is None:
        return {
            "text": _fallback_text(prompt, json_mode=json_mode),
            "grounded_sources": [],
            "degraded": True,
            "model": "fallback",
        }

    cfg_kwargs: dict[str, Any] = {}
    if system:
        cfg_kwargs["system_instruction"] = system
    if json_mode:
        cfg_kwargs["response_mime_type"] = "application/json"
    if grounded:
        cfg_kwargs["tools"] = [gtypes.Tool(google_search=gtypes.GoogleSearch())]

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = cli.models.generate_content(
                model=used_model,
                contents=prompt,
                config=gtypes.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None,
            )
            text = resp.text or ""
            sources: list[dict] = []
            try:
                for c in resp.candidates or []:
                    gm = getattr(c, "grounding_metadata", None)
                    if not gm:
                        continue
                    for chunk in getattr(gm, "grounding_chunks", []) or []:
                        web = getattr(chunk, "web", None)
                        if web:
                            sources.append(
                                {"title": getattr(web, "title", ""), "uri": getattr(web, "uri", "")}
                            )
            except Exception:
                pass
            return {
                "text": text,
                "grounded_sources": sources,
                "degraded": False,
                "model": used_model,
            }
        except Exception as e:
            last_err = e
            log.warning("Gemini error (attempt %d): %s", attempt, e)
            time.sleep(0.6 * (attempt + 1))
    return {
        "text": _fallback_text(prompt, json_mode=json_mode),
        "grounded_sources": [],
        "degraded": True,
        "model": "fallback",
        "error": str(last_err) if last_err else None,
    }


def gen_json(prompt: str, *, system: str | None = None, grounded: bool = False, model: str | None = None) -> dict:
    """Llama a gen_text en json_mode y parsea. Si falla, intenta extraer JSON del texto."""
    out = gen_text(prompt, system=system, json_mode=True, grounded=grounded, model=model)
    txt = (out.get("text") or "").strip()
    data: Any = None
    if txt:
        try:
            data = json.loads(txt)
        except Exception:
            # buscar el primer { ... } balanceado
            try:
                start = txt.find("{")
                if start == -1:
                    start = txt.find("[")
                if start >= 0:
                    data = json.loads(txt[start:])
            except Exception:
                data = None
    return {
        "data": data if data is not None else {"raw": txt},
        "grounded_sources": out.get("grounded_sources", []),
        "degraded": out.get("degraded", False),
        "model": out.get("model"),
        "error": out.get("error"),
    }


def gen_image(prompt: str, *, n: int = 1, aspect: str = "1:1") -> list[str]:
    """Genera imágenes. Devuelve lista de strings base64 (PNG). Fallback: SVG placeholder en base64."""
    cli = _client()
    if cli is None:
        return [_placeholder_png_b64(prompt) for _ in range(n)]
    try:
        resp = cli.models.generate_images(
            model=_settings.image_model,
            prompt=prompt,
            config=gtypes.GenerateImagesConfig(
                number_of_images=n,
                aspect_ratio=aspect,
            ),
        )
        out: list[str] = []
        for img in (resp.generated_images or [])[:n]:
            data = getattr(img.image, "image_bytes", None)
            if data:
                out.append(base64.b64encode(data).decode("ascii"))
        if not out:
            return [_placeholder_png_b64(prompt) for _ in range(n)]
        return out
    except Exception as e:
        log.warning("Image gen failed: %s — using placeholder", e)
        return [_placeholder_png_b64(prompt) for _ in range(n)]


def _fallback_text(prompt: str, *, json_mode: bool) -> str:
    """Heurística mínima cuando no hay API. Mantiene la app funcional sin clave."""
    if json_mode:
        return json.dumps(
            {
                "note": "Respuesta demo sin GEMINI_API_KEY. Configura la clave para resultados reales.",
                "echo": prompt[:240],
            },
            ensure_ascii=False,
        )
    return (
        "[MODO DEMO - sin Gemini configurado]\n"
        "Prompt recibido: " + prompt[:600] + "\n"
        "Configura GEMINI_API_KEY (https://aistudio.google.com/apikey) para resultados reales."
    )


def _placeholder_png_b64(prompt: str) -> str:
    """PNG 600x400 con texto del prompt (placeholder). Pillow ya lo tenemos en deps."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        img = Image.new("RGB", (1024, 1024), (245, 245, 250))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except Exception:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
        d.rectangle([(40, 40), (984, 984)], outline=(60, 80, 200), width=8)
        d.text((80, 80), "VIBE MARKETING", fill=(60, 80, 200), font=font)
        d.text((80, 140), "(imagen demo - sin API)", fill=(120, 120, 120), font=font_small)
        # word-wrap
        words = prompt.split()
        line = ""
        y = 220
        for w in words:
            cand = (line + " " + w).strip()
            if len(cand) > 36:
                d.text((80, y), line, fill=(30, 30, 30), font=font_small)
                y += 32
                line = w
            else:
                line = cand
            if y > 920:
                break
        if line and y <= 920:
            d.text((80, y), line, fill=(30, 30, 30), font=font_small)
        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        # 1x1 transparent PNG
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
