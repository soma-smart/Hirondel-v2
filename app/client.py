"""
Client Dataiku — appels directs à l'API REST DSS via httpx.
Aucune dépendance à dataikuapi.
"""

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Modèles de données
# ---------------------------------------------------------------------------

@dataclass
class DatasetInfo:
    name: str
    project_key: str
    type: str
    schema_columns: list[dict] = field(default_factory=list)
    last_build_status: str = "UNKNOWN"
    record_count: int | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class FlowNode:
    id: str
    name: str
    type: str          # DATASET, RECIPE, STREAMING_ENDPOINT…
    zone: str | None = None


@dataclass
class FlowEdge:
    source: str
    target: str


@dataclass
class FlowGraph:
    project_key: str
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class DataikuClient:
    """Client HTTP direct contre l'API REST Dataiku DSS."""

    def __init__(
        self,
        host: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.host = (host or os.environ["DATAIKU_HOST"]).rstrip("/")
        self.api_key = api_key or os.environ["DATAIKU_API_KEY"]
        self._http: httpx.Client | None = None

    # ------------------------------------------------------------------
    # HTTP interne
    # ------------------------------------------------------------------

    @property
    def http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                base_url=self.host,
                auth=(self.api_key, ""),
                timeout=30.0,
                verify=False,          # certains DSS ont des certs internes
            )
        return self._http

    # Préfixe de l'API REST Dataiku DSS
    _API = "/public/api"

    def _get(self, path: str, **params: Any) -> Any:
        resp = self.http.get(self._API + path, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: Any = None) -> Any:
        resp = self.http.post(self._API + path, json=json)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Vérification de connexion
    # ------------------------------------------------------------------

    def check_connection(self) -> dict:
        """Vérifie la connexion et retourne les infos d'instance."""
        return self._get("/projects/")

    # ------------------------------------------------------------------
    # Projets
    # ------------------------------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        """Retourne la liste des projets accessibles."""
        raw = self._get("/projects/")
        return [
            {
                "key": p["projectKey"],
                "name": p.get("name", p["projectKey"]),
            }
            for p in raw
        ]

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    def list_datasets(self, project_key: str) -> list[DatasetInfo]:
        """Retourne tous les datasets d'un projet avec leurs métadonnées."""
        raw_list = self._get(f"/projects/{project_key}/datasets/")
        datasets: list[DatasetInfo] = []

        for ds_raw in raw_list:
            name = ds_raw["name"]

            # Schéma
            schema_columns = ds_raw.get("schema", {}).get("columns", [])

            # Statut du dernier build (via les jobs)
            last_build_status = _resolve_build_status(self, project_key, name)

            # Nombre de lignes via les métriques (optionnel)
            record_count = _resolve_record_count(self, project_key, name)

            datasets.append(
                DatasetInfo(
                    name=name,
                    project_key=project_key,
                    type=ds_raw.get("type", "UNKNOWN"),
                    schema_columns=schema_columns,
                    last_build_status=last_build_status,
                    record_count=record_count,
                    tags=ds_raw.get("tags", []),
                )
            )

        return datasets

    def get_dataset(self, project_key: str, dataset_name: str) -> DatasetInfo:
        """Retourne les détails d'un dataset précis."""
        raw_list = self._get(f"/projects/{project_key}/datasets/")
        for ds_raw in raw_list:
            if ds_raw["name"] == dataset_name:
                schema_columns = ds_raw.get("schema", {}).get("columns", [])
                return DatasetInfo(
                    name=dataset_name,
                    project_key=project_key,
                    type=ds_raw.get("type", "UNKNOWN"),
                    schema_columns=schema_columns,
                    last_build_status=_resolve_build_status(self, project_key, dataset_name),
                    record_count=_resolve_record_count(self, project_key, dataset_name),
                    tags=ds_raw.get("tags", []),
                )
        raise ValueError(f"Dataset '{dataset_name}' introuvable dans le projet '{project_key}'.")

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------

    def get_flow_graph(self, project_key: str) -> FlowGraph:
        """Retourne le graphe de flux d'un projet."""
        raw = self._get(f"/projects/{project_key}/flow/zones/")

        nodes: list[FlowNode] = []
        edges: list[FlowEdge] = []
        seen_ids: set[str] = set()

        # L'API retourne les zones ; chaque zone contient des items
        zones = raw if isinstance(raw, list) else raw.get("zones", [])

        for zone in zones:
            zone_id = zone.get("id")
            for item in zone.get("items", []):
                ref = item.get("ref", "")
                item_type = item.get("type", "UNKNOWN")
                item_name = item.get("data", {}).get("name", ref)

                if ref and ref not in seen_ids:
                    seen_ids.add(ref)
                    nodes.append(FlowNode(id=ref, name=item_name, type=item_type, zone=zone_id))

                # Connexions sortantes
                for output_ref in item.get("data", {}).get("outputs", []):
                    if isinstance(output_ref, str):
                        edges.append(FlowEdge(source=ref, target=output_ref))

        # Fallback : si le endpoint /flow/zones/ ne renvoie rien, essayer /datasets + /recipes
        if not nodes:
            nodes, edges = _build_graph_from_datasets_recipes(self, project_key)

        return FlowGraph(project_key=project_key, nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------

def _resolve_build_status(client: DataikuClient, project_key: str, dataset_name: str) -> str:
    """Déduit le statut du dernier build depuis les jobs récents."""
    try:
        jobs = client._get(f"/projects/{project_key}/jobs/", limit=50)
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs", [])
        for job in sorted(jobs, key=lambda j: j.get("def", {}).get("startTime", 0), reverse=True):
            outputs = job.get("def", {}).get("outputs", [])
            for output in outputs:
                if output.get("ref") == dataset_name:
                    return job.get("baseStatus", "UNKNOWN")
    except Exception:
        pass
    return "UNKNOWN"


def _resolve_record_count(client: DataikuClient, project_key: str, dataset_name: str) -> int | None:
    """Tente de récupérer le nombre de lignes via les métriques."""
    try:
        metrics = client._get(
            f"/projects/{project_key}/datasets/{dataset_name}/metrics/last"
        )
        for entry in metrics.get("result", {}).get("computed", []):
            metric = entry.get("metric", {})
            if metric.get("id") == "records:COUNT_RECORDS":
                return int(entry.get("value", 0))
    except Exception:
        pass
    return None


def _build_graph_from_datasets_recipes(
    client: DataikuClient, project_key: str
) -> tuple[list[FlowNode], list[FlowEdge]]:
    """Construit un graphe minimal depuis les datasets et recettes."""
    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []

    try:
        datasets = client._get(f"/projects/{project_key}/datasets/")
        for ds in datasets:
            nodes.append(FlowNode(id=ds["name"], name=ds["name"], type="DATASET"))
    except Exception:
        pass

    try:
        recipes = client._get(f"/projects/{project_key}/recipes/")
        if isinstance(recipes, dict):
            recipes = recipes.get("recipes", [])
        for recipe in recipes:
            name = recipe.get("name", "")
            nodes.append(FlowNode(id=name, name=name, type=recipe.get("type", "RECIPE")))
            for inp in recipe.get("inputs", {}).values():
                for item in inp if isinstance(inp, list) else inp.get("items", []):
                    ref = item if isinstance(item, str) else item.get("ref", "")
                    if ref:
                        edges.append(FlowEdge(source=ref, target=name))
            for out in recipe.get("outputs", {}).values():
                for item in out if isinstance(out, list) else out.get("items", []):
                    ref = item if isinstance(item, str) else item.get("ref", "")
                    if ref:
                        edges.append(FlowEdge(source=name, target=ref))
    except Exception:
        pass

    return nodes, edges
