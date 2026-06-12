"""
Routes FastAPI — Flows
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.client import DataikuClient

router = APIRouter(prefix="/projects/{project_key}/flow", tags=["flows"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def flow_page(request: Request, project_key: str):
    client = DataikuClient()
    try:
        graph = client.get_flow_graph(project_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return templates.TemplateResponse(
        "flow.html",
        {
            "request": request,
            "project_key": project_key,
            "graph": graph,
        },
    )


@router.get("/api", tags=["flows-api"])
async def flow_graph_api(project_key: str):
    """Endpoint JSON — graphe de flux d'un projet."""
    client = DataikuClient()
    try:
        graph = client.get_flow_graph(project_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "project_key": graph.project_key,
        "nodes": [
            {"id": n.id, "name": n.name, "type": n.type, "zone": n.zone}
            for n in graph.nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target}
            for e in graph.edges
        ],
    }
