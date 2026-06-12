"""
Routes FastAPI — Datasets
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.client import DataikuClient

router = APIRouter(prefix="/projects/{project_key}/datasets", tags=["datasets"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_datasets_page(request: Request, project_key: str):
    client = DataikuClient()
    try:
        datasets = client.list_datasets(project_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return templates.TemplateResponse(
        "datasets.html",
        {
            "request": request,
            "project_key": project_key,
            "datasets": datasets,
        },
    )


@router.get("/api", tags=["datasets-api"])
async def list_datasets_api(project_key: str):
    """Endpoint JSON — liste des datasets d'un projet."""
    client = DataikuClient()
    try:
        datasets = client.list_datasets(project_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [
        {
            "name": d.name,
            "type": d.type,
            "last_build_status": d.last_build_status,
            "record_count": d.record_count,
            "tags": d.tags,
            "schema_columns": d.schema_columns,
        }
        for d in datasets
    ]


@router.get("/{dataset_name}/api", tags=["datasets-api"])
async def get_dataset_api(project_key: str, dataset_name: str):
    """Endpoint JSON — détails d'un dataset."""
    client = DataikuClient()
    try:
        dataset = client.get_dataset(project_key, dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "name": dataset.name,
        "type": dataset.type,
        "last_build_status": dataset.last_build_status,
        "record_count": dataset.record_count,
        "tags": dataset.tags,
        "schema_columns": dataset.schema_columns,
    }
