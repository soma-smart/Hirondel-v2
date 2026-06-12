"""
Application FastAPI principale — Hirondel v2
Connexion Dataiku : Flows & Datasets
"""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from app.client import DataikuClient
from app.routes.datasets import router as datasets_router
from app.routes.flows import router as flows_router

load_dotenv()

app = FastAPI(
    title="Hirondel — Dataiku Pipeline Explorer",
    description="Interface web pour explorer les Flows et Datasets d'un DSS Dataiku.",
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(datasets_router)
app.include_router(flows_router)


# ---------------------------------------------------------------------------
# Page d'accueil
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    client = DataikuClient()
    projects = []
    error = None
    try:
        projects = client.list_projects()
    except Exception as exc:
        error = str(exc)

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "projects": projects, "error": error},
    )


# ---------------------------------------------------------------------------
# API : liste des projets
# ---------------------------------------------------------------------------

@app.get("/api/projects", tags=["projects"])
async def list_projects_api():
    """Retourne la liste de tous les projets Dataiku accessibles."""
    client = DataikuClient()
    try:
        return client.list_projects()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Point d'entrée direct
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True,
    )
