"""Multi-provider AI abstraction.

Soporta proveedores configurables en runtime desde la UI. Cada proveedor
implementa subset de capacidades: text, image, video. La clave se guarda en
la BD (tabla provider_keys) y/o env. La selección por tarea se controla con
``ProviderRegistry.choose(task)``.

Capacidades:
- text: chat / generación de texto (con json_mode opcional)
- image: generación de imágenes (devuelve base64 PNG)
- video: generación de vídeo (devuelve URL o base64) — solo proveedores que lo soporten
- grounded: búsqueda + cita de fuentes (solo Gemini hoy)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

log = logging.getLogger("providers")


# ---------- Catálogo estático de proveedores que la UI muestra ----------

PROVIDER_CATALOG: list[dict] = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "env": "GEMINI_API_KEY",
        "needs_base_url": False,
        "tasks": ["text", "image", "grounded"],
        "default_models": {
            "text": "gemini-2.5-flash-lite",
            "image": "imagen-3.0-generate-002",
            "grounded": "gemini-2.5-flash",
        },
        "models": [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "imagen-3.0-generate-002",
            "imagen-4.0-generate-001",
        ],
        "docs": "https://aistudio.google.com/apikey",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "tasks": ["text", "image"],
        "default_models": {"text": "gpt-4o-mini", "image": "gpt-image-1"},
        "models": [
            "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini",
            "gpt-image-1", "dall-e-3",
        ],
        "docs": "https://platform.openai.com/api-keys",
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "tasks": ["text"],
        "default_models": {"text": "claude-3-5-sonnet-latest"},
        "models": [
            "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest",
        ],
        "docs": "https://console.anthropic.com/settings/keys",
    },
    {
        "id": "dashscope",
        "name": "Alibaba DashScope (Qwen)",
        "env": "DASHSCOPE_API_KEY",
        "needs_base_url": False,
        "tasks": ["text", "image"],
        "default_models": {"text": "qwen-plus", "image": "wanx-v1"},
        "models": [
            "qwen-max", "qwen-plus", "qwen-turbo", "qwen2.5-72b-instruct",
            "wanx-v1", "wanx2.1-t2i-turbo",
        ],
        "docs": "https://dashscope.console.aliyun.com/",
    },
    {
        "id": "mistral",
        "name": "Mistral AI",
        "env": "MISTRAL_API_KEY",
        "needs_base_url": False,
        "tasks": ["text"],
        "default_models": {"text": "mistral-large-latest"},
        "models": ["mistral-large-latest", "mistral-small-latest", "open-mistral-nemo"],
        "docs": "https://console.mistral.ai/api-keys",
    },
    {
        "id": "groq",
        "name": "Groq (ultra-rápido)",
        "env": "GROQ_API_KEY",
        "needs_base_url": False,
        "tasks": ["text"],
        "default_models": {"text": "llama-3.3-70b-versatile"},
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "docs": "https://console.groq.com/keys",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "env": "DEEPSEEK_API_KEY",
        "needs_base_url": False,
        "tasks": ["text"],
        "default_models": {"text": "deepseek-chat"},
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "docs": "https://platform.deepseek.com/api_keys",
    },
    {
        "id": "together",
        "name": "Together AI (open-source)",
        "env": "TOGETHER_API_KEY",
        "needs_base_url": False,
        "tasks": ["text", "image"],
        "default_models": {
            "text": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "image": "black-forest-labs/FLUX.1-schnell-Free",
        },
        "models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-V3",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "black-forest-labs/FLUX.1-schnell-Free",
            "black-forest-labs/FLUX.1-dev",
        ],
        "docs": "https://api.together.ai/settings/api-keys",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (router multi-modelo)",
        "env": "OPENROUTER_API_KEY",
        "needs_base_url": False,
        "tasks": ["text"],
        "default_models": {"text": "openai/gpt-4o-mini"},
        "models": [
            "openai/gpt-4o-mini", "openai/gpt-4o", "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-chat",
        ],
        "docs": "https://openrouter.ai/keys",
    },
    {
        "id": "replicate",
        "name": "Replicate (imagen + vídeo)",
        "env": "REPLICATE_API_TOKEN",
        "needs_base_url": False,
        "tasks": ["image", "video"],
        "default_models": {
            "image": "black-forest-labs/flux-schnell",
            "video": "minimax/video-01",
        },
        "models": [
            "black-forest-labs/flux-schnell",
            "black-forest-labs/flux-1.1-pro",
            "stability-ai/sdxl",
            "minimax/video-01",
            "luma/ray",
        ],
        "docs": "https://replicate.com/account/api-tokens",
    },
    {
        "id": "elevenlabs",
        "name": "ElevenLabs (voz)",
        "env": "ELEVENLABS_API_KEY",
        "needs_base_url": False,
        "tasks": ["audio"],
        "default_models": {"audio": "eleven_multilingual_v2"},
        "models": ["eleven_multilingual_v2", "eleven_turbo_v2_5"],
        "docs": "https://elevenlabs.io/app/settings/api-keys",
    },
    {
        "id": "huggingface",
        "name": "Hugging Face Inference",
        "env": "HF_TOKEN",
        "needs_base_url": False,
        "tasks": ["text", "image"],
        "default_models": {
            "text": "meta-llama/Meta-Llama-3-8B-Instruct",
            "image": "stabilityai/stable-diffusion-xl-base-1.0",
        },
        "models": [
            "meta-llama/Meta-Llama-3-8B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
            "stabilityai/stable-diffusion-xl-base-1.0",
            "black-forest-labs/FLUX.1-schnell",
        ],
        "docs": "https://huggingface.co/settings/tokens",
    },
    {
        "id": "openai_compatible",
        "name": "OpenAI-compatible (Ollama / LM Studio / Azure / custom)",
        "env": None,
        "needs_base_url": True,
        "tasks": ["text"],
        "default_models": {"text": "gpt-4o-mini"},
        "models": [],
        "docs": "https://platform.openai.com/docs/api-reference",
    },
]


CATALOG_BY_ID = {p["id"]: p for p in PROVIDER_CATALOG}


@dataclass
class ProviderConfig:
    id: str
    api_key: str
    base_url: str | None = None
    models: dict[str, str] | None = None  # task -> model override
    enabled: bool = True


# ---------- Registry global (en memoria, hidratado desde DB al arrancar) ----------

class ProviderRegistry:
    def __init__(self) -> None:
        self._configs: dict[str, ProviderConfig] = {}
        # task -> provider_id (preferencia)
        self._preference: dict[str, str] = {}
        self._load_from_env()

    def _load_from_env(self) -> None:
        for p in PROVIDER_CATALOG:
            env = p.get("env")
            if env and os.getenv(env):
                self._configs[p["id"]] = ProviderConfig(
                    id=p["id"], api_key=os.getenv(env, ""), models=dict(p["default_models"])
                )
        # default preferences
        for task in ("text", "image", "video", "grounded", "audio"):
            for pid, cfg in self._configs.items():
                if task in CATALOG_BY_ID[pid]["tasks"]:
                    self._preference.setdefault(task, pid)
                    break

    def upsert(self, cfg: ProviderConfig) -> None:
        self._configs[cfg.id] = cfg
        # asegurar preferencia si no había
        for task in CATALOG_BY_ID[cfg.id]["tasks"]:
            self._preference.setdefault(task, cfg.id)

    def remove(self, pid: str) -> None:
        self._configs.pop(pid, None)
        for task, p in list(self._preference.items()):
            if p == pid:
                self._preference.pop(task, None)

    def set_preference(self, task: str, pid: str) -> None:
        self._preference[task] = pid

    def list_configured(self) -> list[dict]:
        out = []
        for pid, cfg in self._configs.items():
            cat = CATALOG_BY_ID.get(pid, {})
            out.append({
                "id": pid,
                "name": cat.get("name", pid),
                "tasks": cat.get("tasks", []),
                "models": cfg.models or cat.get("default_models", {}),
                "base_url": cfg.base_url,
                "enabled": cfg.enabled,
                "has_key": bool(cfg.api_key),
            })
        return out

    def preferences(self) -> dict[str, str]:
        return dict(self._preference)

    def choose(self, task: str) -> ProviderConfig | None:
        pid = self._preference.get(task)
        if pid and pid in self._configs and self._configs[pid].enabled:
            return self._configs[pid]
        # fallback: cualquier provider configurado que soporte la tarea
        for pid2, cfg in self._configs.items():
            if not cfg.enabled:
                continue
            if task in CATALOG_BY_ID.get(pid2, {}).get("tasks", []):
                return cfg
        return None

    def get(self, pid: str) -> ProviderConfig | None:
        return self._configs.get(pid)


registry = ProviderRegistry()


# ---------- Adaptadores: cada función toma un ProviderConfig + params ----------

def _model_for(cfg: ProviderConfig, task: str) -> str:
    if cfg.models and cfg.models.get(task):
        return cfg.models[task]
    return CATALOG_BY_ID.get(cfg.id, {}).get("default_models", {}).get(task, "")


def call_text(prompt: str, *, system: str | None = None, json_mode: bool = False,
              grounded: bool = False, provider_id: str | None = None,
              max_retries: int = 1) -> dict:
    """Genera texto con el proveedor preferido (o el indicado)."""
    if grounded:
        cfg = registry.get(provider_id) if provider_id else registry.choose("grounded")
    else:
        cfg = registry.get(provider_id) if provider_id else registry.choose("text")
    if cfg is None:
        return {
            "text": _demo_text(prompt, json_mode),
            "provider": "demo",
            "model": "fallback",
            "degraded": True,
            "grounded_sources": [],
        }
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            if cfg.id == "gemini":
                return _gemini_text(cfg, prompt, system=system, json_mode=json_mode, grounded=grounded)
            if cfg.id in ("openai", "openrouter", "openai_compatible", "groq", "deepseek", "together", "mistral"):
                return _openai_text(cfg, prompt, system=system, json_mode=json_mode)
            if cfg.id == "anthropic":
                return _anthropic_text(cfg, prompt, system=system, json_mode=json_mode)
            if cfg.id == "dashscope":
                return _dashscope_text(cfg, prompt, system=system, json_mode=json_mode)
            if cfg.id == "huggingface":
                return _hf_text(cfg, prompt, system=system, json_mode=json_mode)
        except Exception as e:
            last_err = e
            log.warning("text provider %s error attempt %d: %s", cfg.id, attempt, e)
            time.sleep(0.5 * (attempt + 1))
    return {
        "text": _demo_text(prompt, json_mode),
        "provider": cfg.id if cfg else "demo",
        "model": "fallback",
        "degraded": True,
        "grounded_sources": [],
        "error": str(last_err) if last_err else None,
    }


def call_json(prompt: str, *, system: str | None = None, grounded: bool = False, provider_id: str | None = None) -> dict:
    out = call_text(prompt, system=system, json_mode=True, grounded=grounded, provider_id=provider_id)
    txt = (out.get("text") or "").strip()
    data: Any = None
    if txt:
        try:
            data = json.loads(txt)
        except Exception:
            for opener, closer in (("{", "}"), ("[", "]")):
                try:
                    s = txt.find(opener)
                    e = txt.rfind(closer)
                    if s >= 0 and e > s:
                        data = json.loads(txt[s : e + 1])
                        break
                except Exception:
                    pass
    return {
        **out,
        "data": data if data is not None else {"raw": txt[:1500]},
    }


def call_image(prompt: str, *, n: int = 1, aspect: str = "1:1", provider_id: str | None = None) -> list[str]:
    cfg = registry.get(provider_id) if provider_id else registry.choose("image")
    if cfg is None:
        from .ai import _placeholder_png_b64  # type: ignore
        return [_placeholder_png_b64(prompt) for _ in range(n)]
    try:
        if cfg.id == "gemini":
            return _gemini_image(cfg, prompt, n=n, aspect=aspect)
        if cfg.id in ("openai", "openrouter"):
            return _openai_image(cfg, prompt, n=n, aspect=aspect)
        if cfg.id == "dashscope":
            return _dashscope_image(cfg, prompt, n=n, aspect=aspect)
        if cfg.id == "together":
            return _together_image(cfg, prompt, n=n, aspect=aspect)
        if cfg.id == "replicate":
            return _replicate_image(cfg, prompt, n=n, aspect=aspect)
        if cfg.id == "huggingface":
            return _hf_image(cfg, prompt, n=n, aspect=aspect)
    except Exception as e:
        log.warning("image provider %s failed: %s", cfg.id, e)
    from .ai import _placeholder_png_b64  # type: ignore
    return [_placeholder_png_b64(prompt) for _ in range(n)]


def call_video(prompt: str, *, provider_id: str | None = None) -> dict:
    cfg = registry.get(provider_id) if provider_id else registry.choose("video")
    if cfg is None:
        return {"url": None, "degraded": True, "note": "Sin proveedor de vídeo configurado."}
    try:
        if cfg.id == "replicate":
            return _replicate_video(cfg, prompt)
    except Exception as e:
        return {"url": None, "degraded": True, "error": str(e)}
    return {"url": None, "degraded": True, "note": f"Proveedor {cfg.id} no soporta vídeo aún."}


def test_connection(provider_id: str) -> dict:
    cfg = registry.get(provider_id)
    if cfg is None:
        return {"ok": False, "error": "Proveedor no configurado"}
    try:
        out = call_text("Responde solo: OK", provider_id=provider_id)
        return {"ok": not out.get("degraded"), "provider": provider_id, "model": out.get("model"), "sample": (out.get("text") or "")[:200], "error": out.get("error")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------- Implementaciones concretas (HTTP directo, sin SDKs salvo Gemini) ----------

def _gemini_text(cfg: ProviderConfig, prompt: str, *, system: str | None, json_mode: bool, grounded: bool) -> dict:
    try:
        from google import genai
        from google.genai import types as gtypes
    except Exception:
        # fallback HTTP directo
        return _gemini_text_http(cfg, prompt, system=system, json_mode=json_mode, grounded=grounded)
    cli = genai.Client(api_key=cfg.api_key)
    model = _model_for(cfg, "grounded" if grounded else "text")
    cfg_kwargs: dict[str, Any] = {}
    if system:
        cfg_kwargs["system_instruction"] = system
    if json_mode and not grounded:  # grounded + json no se soportan a la vez
        cfg_kwargs["response_mime_type"] = "application/json"
    if grounded:
        cfg_kwargs["tools"] = [gtypes.Tool(google_search=gtypes.GoogleSearch())]
    resp = cli.models.generate_content(
        model=model,
        contents=prompt,
        config=gtypes.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None,
    )
    sources: list[dict] = []
    try:
        for c in resp.candidates or []:
            gm = getattr(c, "grounding_metadata", None)
            if not gm:
                continue
            for chunk in getattr(gm, "grounding_chunks", []) or []:
                web = getattr(chunk, "web", None)
                if web:
                    sources.append({"title": getattr(web, "title", ""), "uri": getattr(web, "uri", "")})
    except Exception:
        pass
    return {
        "text": resp.text or "",
        "provider": "gemini",
        "model": model,
        "grounded_sources": sources,
        "degraded": False,
    }


def _gemini_text_http(cfg: ProviderConfig, prompt: str, *, system: str | None, json_mode: bool, grounded: bool) -> dict:
    model = _model_for(cfg, "grounded" if grounded else "text")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={cfg.api_key}"
    body: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    if grounded:
        body["tools"] = [{"google_search": {}}]
    with httpx.Client(timeout=60) as c:
        r = c.post(url, json=body)
        r.raise_for_status()
        data = r.json()
    text = ""
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass
    return {"text": text, "provider": "gemini", "model": model, "grounded_sources": [], "degraded": False}


def _gemini_image(cfg: ProviderConfig, prompt: str, *, n: int, aspect: str) -> list[str]:
    try:
        from google import genai
        from google.genai import types as gtypes
    except Exception:
        return []
    cli = genai.Client(api_key=cfg.api_key)
    model = _model_for(cfg, "image")
    resp = cli.models.generate_images(
        model=model,
        prompt=prompt,
        config=gtypes.GenerateImagesConfig(number_of_images=n, aspect_ratio=aspect),
    )
    out: list[str] = []
    for img in (resp.generated_images or [])[:n]:
        data = getattr(img.image, "image_bytes", None)
        if data:
            out.append(base64.b64encode(data).decode("ascii"))
    return out


# Endpoints OpenAI-compatibles (OpenAI, OpenRouter, Groq, DeepSeek, Together, Mistral, custom)
def _openai_base(cfg: ProviderConfig) -> str:
    if cfg.base_url:
        return cfg.base_url.rstrip("/")
    return {
        "openai": "https://api.openai.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "groq": "https://api.groq.com/openai/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "together": "https://api.together.xyz/v1",
        "mistral": "https://api.mistral.ai/v1",
    }.get(cfg.id, "https://api.openai.com/v1")


def _openai_text(cfg: ProviderConfig, prompt: str, *, system: str | None, json_mode: bool) -> dict:
    base = _openai_base(cfg)
    model = _model_for(cfg, "text")
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body: dict[str, Any] = {"model": model, "messages": msgs}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    if cfg.id == "openrouter":
        headers["HTTP-Referer"] = "https://vibe-marketing-app.devinapps.com"
        headers["X-Title"] = "Vibe Marketing App"
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{base}/chat/completions", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = data["choices"][0]["message"]["content"] or ""
    return {"text": text, "provider": cfg.id, "model": model, "grounded_sources": [], "degraded": False}


def _openai_image(cfg: ProviderConfig, prompt: str, *, n: int, aspect: str) -> list[str]:
    base = _openai_base(cfg)
    model = _model_for(cfg, "image")
    size = {"1:1": "1024x1024", "16:9": "1536x1024", "9:16": "1024x1536"}.get(aspect, "1024x1024")
    body = {"model": model, "prompt": prompt, "n": n, "size": size, "response_format": "b64_json"}
    if model == "gpt-image-1":
        body.pop("response_format", None)
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    with httpx.Client(timeout=180) as c:
        r = c.post(f"{base}/images/generations", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    out: list[str] = []
    for img in data.get("data", [])[:n]:
        if "b64_json" in img:
            out.append(img["b64_json"])
        elif "url" in img:
            out.append(_url_to_b64(img["url"]))
    return out


def _anthropic_text(cfg: ProviderConfig, prompt: str, *, system: str | None, json_mode: bool) -> dict:
    model = _model_for(cfg, "text")
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt + ("\n\nResponde solo JSON válido." if json_mode else "")}],
    }
    if system:
        body["system"] = system
    headers = {"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"}
    with httpx.Client(timeout=120) as c:
        r = c.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", []))
    return {"text": text, "provider": "anthropic", "model": model, "grounded_sources": [], "degraded": False}


def _dashscope_text(cfg: ProviderConfig, prompt: str, *, system: str | None, json_mode: bool) -> dict:
    model = _model_for(cfg, "text")
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt + ("\n\nResponde solo JSON válido." if json_mode else "")})
    body = {"model": model, "input": {"messages": msgs}, "parameters": {"result_format": "message"}}
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120) as c:
        r = c.post("https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                   json=body, headers=headers)
        if r.status_code >= 400:
            # probar endpoint regional CN
            r = c.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                       json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = ""
    try:
        text = data["output"]["choices"][0]["message"]["content"]
    except Exception:
        text = data.get("output", {}).get("text", "")
    return {"text": text, "provider": "dashscope", "model": model, "grounded_sources": [], "degraded": False}


def _dashscope_image(cfg: ProviderConfig, prompt: str, *, n: int, aspect: str) -> list[str]:
    model = _model_for(cfg, "image")
    size = {"1:1": "1024*1024", "16:9": "1280*720", "9:16": "720*1280"}.get(aspect, "1024*1024")
    body = {"model": model, "input": {"prompt": prompt}, "parameters": {"n": n, "size": size}}
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json", "X-DashScope-Async": "enable"}
    with httpx.Client(timeout=180) as c:
        r = c.post("https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                   json=body, headers=headers)
        if r.status_code >= 400:
            r = c.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                       json=body, headers=headers)
        r.raise_for_status()
        task_id = r.json().get("output", {}).get("task_id")
        if not task_id:
            return []
        status_url = f"https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}"
        deadline = time.time() + 120
        urls: list[str] = []
        while time.time() < deadline:
            time.sleep(2)
            sr = c.get(status_url, headers={"Authorization": f"Bearer {cfg.api_key}"})
            if sr.status_code >= 400:
                break
            sd = sr.json()
            st = sd.get("output", {}).get("task_status")
            if st == "SUCCEEDED":
                for it in sd.get("output", {}).get("results", []):
                    if it.get("url"):
                        urls.append(it["url"])
                break
            if st in ("FAILED", "CANCELED"):
                break
        return [_url_to_b64(u) for u in urls]


def _together_image(cfg: ProviderConfig, prompt: str, *, n: int, aspect: str) -> list[str]:
    model = _model_for(cfg, "image")
    w, h = {"1:1": (1024, 1024), "16:9": (1344, 768), "9:16": (768, 1344)}.get(aspect, (1024, 1024))
    body = {"model": model, "prompt": prompt, "n": n, "width": w, "height": h, "response_format": "b64_json"}
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    with httpx.Client(timeout=180) as c:
        r = c.post("https://api.together.xyz/v1/images/generations", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    out = []
    for it in data.get("data", [])[:n]:
        if it.get("b64_json"):
            out.append(it["b64_json"])
        elif it.get("url"):
            out.append(_url_to_b64(it["url"]))
    return out


def _replicate_image(cfg: ProviderConfig, prompt: str, *, n: int, aspect: str) -> list[str]:
    model = _model_for(cfg, "image")
    headers = {"Authorization": f"Token {cfg.api_key}", "Content-Type": "application/json", "Prefer": "wait"}
    body = {"input": {"prompt": prompt, "num_outputs": n, "aspect_ratio": aspect}}
    with httpx.Client(timeout=300) as c:
        r = c.post(f"https://api.replicate.com/v1/models/{model}/predictions", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
        urls = data.get("output") or []
        if isinstance(urls, str):
            urls = [urls]
    return [_url_to_b64(u) for u in urls[:n]]


def _replicate_video(cfg: ProviderConfig, prompt: str) -> dict:
    model = _model_for(cfg, "video")
    headers = {"Authorization": f"Token {cfg.api_key}", "Content-Type": "application/json", "Prefer": "wait=120"}
    body = {"input": {"prompt": prompt}}
    with httpx.Client(timeout=300) as c:
        r = c.post(f"https://api.replicate.com/v1/models/{model}/predictions", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    out = data.get("output")
    url = out if isinstance(out, str) else (out[0] if isinstance(out, list) and out else None)
    return {"url": url, "provider": "replicate", "model": model, "degraded": not url}


def _hf_text(cfg: ProviderConfig, prompt: str, *, system: str | None, json_mode: bool) -> dict:
    model = _model_for(cfg, "text")
    full = (system + "\n\n" if system else "") + prompt
    body = {"inputs": full, "parameters": {"max_new_tokens": 1024, "return_full_text": False}}
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    with httpx.Client(timeout=120) as c:
        r = c.post(f"https://api-inference.huggingface.co/models/{model}", json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = data[0].get("generated_text", "") if isinstance(data, list) and data else str(data)
    return {"text": text, "provider": "huggingface", "model": model, "grounded_sources": [], "degraded": False}


def _hf_image(cfg: ProviderConfig, prompt: str, *, n: int, aspect: str) -> list[str]:
    model = _model_for(cfg, "image")
    out: list[str] = []
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Accept": "image/png"}
    for _ in range(n):
        with httpx.Client(timeout=180) as c:
            r = c.post(f"https://api-inference.huggingface.co/models/{model}", json={"inputs": prompt}, headers=headers)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                out.append(base64.b64encode(r.content).decode("ascii"))
    return out


def _url_to_b64(url: str) -> str:
    try:
        with httpx.Client(timeout=60) as c:
            r = c.get(url)
            r.raise_for_status()
            return base64.b64encode(r.content).decode("ascii")
    except Exception:
        from .ai import _placeholder_png_b64  # type: ignore
        return _placeholder_png_b64(url)


def _demo_text(prompt: str, json_mode: bool) -> str:
    if json_mode:
        return json.dumps({"note": "demo mode - configura un proveedor de IA", "echo": prompt[:200]}, ensure_ascii=False)
    return "[DEMO] Configura un proveedor de IA en Ajustes → Proveedores. Prompt: " + prompt[:300]
