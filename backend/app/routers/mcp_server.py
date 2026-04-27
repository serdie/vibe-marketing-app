"""Servidor MCP HTTP minimalista (JSON-RPC) para conectar Claude/ChatGPT/Cursor.

Implementación pragmática que cumple el subset usado por la mayoría de clientes:
- POST /api/mcp con un JSON-RPC 2.0 body (initialize, tools/list, tools/call).
- GET  /api/mcp para introspección rápida (lista de tools en JSON plano).

Las herramientas exponen los mismos endpoints internos del backend, pero pensados
para ser llamados por agentes externos.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Campaign, Lead, Project
from .. import providers

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

TOOLS: list[dict] = [
    {
        "name": "list_projects",
        "description": "Lista los proyectos de marketing creados.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_project",
        "description": "Devuelve detalle completo de un proyecto.",
        "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
    },
    {
        "name": "list_leads",
        "description": "Lista leads de un proyecto.",
        "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
    },
    {
        "name": "list_campaigns",
        "description": "Lista campañas de un proyecto.",
        "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
    },
    {
        "name": "generate_text",
        "description": "Genera texto con el proveedor de IA por defecto del backend.",
        "inputSchema": {"type": "object", "properties": {
            "prompt": {"type": "string"},
            "system": {"type": "string"},
            "json_mode": {"type": "boolean"},
        }, "required": ["prompt"]},
    },
    {
        "name": "generate_image",
        "description": "Genera una imagen y la devuelve como base64 PNG.",
        "inputSchema": {"type": "object", "properties": {
            "prompt": {"type": "string"},
            "aspect": {"type": "string"},
        }, "required": ["prompt"]},
    },
]


@router.get("")
def mcp_info():
    return {
        "name": "vibe-marketing-mcp",
        "version": "0.1.0",
        "tools": TOOLS,
        "transport": "http",
        "rpc_endpoint": "/api/mcp",
    }


@router.post("")
async def mcp_rpc(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    method = body.get("method")
    rid = body.get("id")
    params = body.get("params") or {}

    def ok(result: Any) -> dict:
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def err(code: int, msg: str) -> dict:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "vibe-marketing-mcp", "version": "0.1.0"},
        })
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = _dispatch(name, args, db)
            return ok({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)[:50000]}]})
        except Exception as e:
            return err(-32000, str(e))
    return err(-32601, f"Method not found: {method}")


def _dispatch(name: str, args: dict, db: Session) -> Any:
    if name == "list_projects":
        return [{"id": p.id, "name": p.name, "owner_type": p.owner_type, "website": p.website}
                for p in db.query(Project).all()]
    if name == "get_project":
        p = db.get(Project, args.get("project_id"))
        if not p:
            return {"error": "not found"}
        return {
            "id": p.id, "name": p.name, "research": p.research, "gaps": p.gaps,
            "products": p.products, "icp": p.icp, "personas": p.personas, "brand_kit": p.brand_kit,
        }
    if name == "list_leads":
        rows = db.query(Lead).filter(Lead.project_id == args.get("project_id")).all()
        return [{"id": l.id, "name": l.name, "email": l.email, "phone": l.phone, "website": l.website} for l in rows]
    if name == "list_campaigns":
        rows = db.query(Campaign).filter(Campaign.project_id == args.get("project_id")).all()
        return [{"id": c.id, "name": c.name, "status": c.status} for c in rows]
    if name == "generate_text":
        return providers.call_text(args["prompt"], system=args.get("system"), json_mode=bool(args.get("json_mode")))
    if name == "generate_image":
        b64 = providers.call_image(args["prompt"], aspect=args.get("aspect", "1:1"))
        return {"images_b64": b64}
    raise ValueError(f"Unknown tool: {name}")
