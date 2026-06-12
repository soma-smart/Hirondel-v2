"""
CLI Hirondel — Exploration Dataiku depuis le terminal.

Usage:
  python cli.py projects
  python cli.py datasets MY_PROJECT
  python cli.py flow MY_PROJECT
  python cli.py serve
"""

import json
import os
import sys

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box

load_dotenv()
console = Console()


def _get_client():
    """Instancie et connecte le client Dataiku."""
    from app.client import DataikuClient

    host = os.getenv("DATAIKU_HOST")
    api_key = os.getenv("DATAIKU_API_KEY")

    if not host or not api_key:
        console.print(
            "[bold red]Erreur :[/] Les variables DATAIKU_HOST et DATAIKU_API_KEY "
            "doivent être définies (fichier .env ou variables d'environnement)."
        )
        sys.exit(1)

    return DataikuClient(host=host, api_key=api_key)


@click.group()
def cli():
    """Hirondel — Explorez vos pipelines Dataiku depuis le terminal."""


# ---------------------------------------------------------------------------
# Commande : projects
# ---------------------------------------------------------------------------

@cli.command("projects")
@click.option("--json-output", is_flag=True, default=False, help="Affiche en JSON brut.")
def cmd_projects(json_output: bool):
    """Liste tous les projets Dataiku accessibles."""
    client = _get_client()
    try:
        projects = client.list_projects()
    except Exception as exc:
        console.print(f"[bold red]Erreur :[/] {exc}")
        sys.exit(1)

    if json_output:
        click.echo(json.dumps(projects, indent=2, ensure_ascii=False))
        return

    table = Table(title="Projets Dataiku", box=box.ROUNDED, show_lines=True)
    table.add_column("Clé", style="cyan bold", no_wrap=True)
    table.add_column("Nom", style="white")

    for p in projects:
        table.add_row(p["key"], p["name"])

    console.print(table)
    console.print(f"\n[dim]{len(projects)} projet(s) trouvé(s).[/dim]")


# ---------------------------------------------------------------------------
# Commande : datasets
# ---------------------------------------------------------------------------

@cli.command("datasets")
@click.argument("project_key")
@click.option("--json-output", is_flag=True, default=False, help="Affiche en JSON brut.")
@click.option("--filter", "name_filter", default=None, help="Filtre par nom de dataset.")
def cmd_datasets(project_key: str, json_output: bool, name_filter: str | None):
    """Liste les datasets d'un projet avec leur statut."""
    client = _get_client()
    try:
        with console.status(f"Chargement des datasets du projet [cyan]{project_key}[/cyan]…"):
            datasets = client.list_datasets(project_key)
    except Exception as exc:
        console.print(f"[bold red]Erreur :[/] {exc}")
        sys.exit(1)

    if name_filter:
        datasets = [d for d in datasets if name_filter.lower() in d.name.lower()]

    if json_output:
        click.echo(
            json.dumps(
                [
                    {
                        "name": d.name,
                        "type": d.type,
                        "last_build_status": d.last_build_status,
                        "record_count": d.record_count,
                        "tags": d.tags,
                        "columns": len(d.schema_columns),
                    }
                    for d in datasets
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    STATUS_COLORS = {
        "DONE": "green",
        "SUCCESS": "green",
        "RUNNING": "yellow",
        "FAILED": "red",
        "ABORTED": "red",
        "UNKNOWN": "dim",
    }

    table = Table(
        title=f"Datasets — {project_key}",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Nom", style="cyan", no_wrap=True)
    table.add_column("Type", style="white")
    table.add_column("Dernier build", no_wrap=True)
    table.add_column("Lignes", justify="right")
    table.add_column("Colonnes", justify="right")
    table.add_column("Tags")

    for d in datasets:
        color = STATUS_COLORS.get(d.last_build_status.upper(), "dim")
        table.add_row(
            d.name,
            d.type,
            f"[{color}]{d.last_build_status}[/{color}]",
            str(d.record_count) if d.record_count is not None else "—",
            str(len(d.schema_columns)),
            ", ".join(d.tags) if d.tags else "—",
        )

    console.print(table)
    console.print(f"\n[dim]{len(datasets)} dataset(s).[/dim]")


# ---------------------------------------------------------------------------
# Commande : flow
# ---------------------------------------------------------------------------

@cli.command("flow")
@click.argument("project_key")
@click.option("--json-output", is_flag=True, default=False, help="Affiche en JSON brut.")
@click.option("--type", "node_type", default=None, help="Filtre les nœuds par type (ex: DATASET, RECIPE).")
def cmd_flow(project_key: str, json_output: bool, node_type: str | None):
    """Affiche le graphe de flux d'un projet."""
    client = _get_client()
    try:
        with console.status(f"Chargement du flow du projet [cyan]{project_key}[/cyan]…"):
            graph = client.get_flow_graph(project_key)
    except Exception as exc:
        console.print(f"[bold red]Erreur :[/] {exc}")
        sys.exit(1)

    nodes = graph.nodes
    if node_type:
        nodes = [n for n in nodes if n.type.upper() == node_type.upper()]

    if json_output:
        click.echo(
            json.dumps(
                {
                    "project_key": graph.project_key,
                    "nodes": [{"id": n.id, "name": n.name, "type": n.type, "zone": n.zone} for n in nodes],
                    "edges": [{"source": e.source, "target": e.target} for e in graph.edges],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    # Résumé
    console.print(f"\n[bold]Flow — {project_key}[/bold]")
    console.print(f"  Nœuds    : [cyan]{len(graph.nodes)}[/cyan]")
    console.print(f"  Arêtes   : [cyan]{len(graph.edges)}[/cyan]")
    datasets_count = sum(1 for n in graph.nodes if n.type == "DATASET")
    recipes_count = len(graph.nodes) - datasets_count
    console.print(f"  Datasets : [blue]{datasets_count}[/blue] | Recettes : [yellow]{recipes_count}[/yellow]\n")

    TYPE_COLORS = {"DATASET": "blue", "RECIPE": "yellow", "STREAMING_ENDPOINT": "magenta"}

    table = Table(title="Nœuds du flow", box=box.ROUNDED, show_lines=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Nom", style="white")
    table.add_column("Type", no_wrap=True)
    table.add_column("Zone")

    for n in nodes:
        color = TYPE_COLORS.get(n.type, "white")
        table.add_row(n.id, n.name, f"[{color}]{n.type}[/{color}]", n.zone or "—")

    console.print(table)


# ---------------------------------------------------------------------------
# Commande : serve (lance le serveur web)
# ---------------------------------------------------------------------------

@cli.command("serve")
@click.option("--host", default=None, help="Adresse d'écoute (défaut: APP_HOST ou 0.0.0.0).")
@click.option("--port", default=None, type=int, help="Port (défaut: APP_PORT ou 8000).")
@click.option("--reload", is_flag=True, default=False, help="Rechargement automatique (dev).")
def cmd_serve(host: str | None, port: int | None, reload: bool):
    """Lance le serveur web FastAPI."""
    import uvicorn

    _host = host or os.getenv("APP_HOST", "0.0.0.0")
    _port = port or int(os.getenv("APP_PORT", "8000"))

    console.print(f"[bold green]Démarrage du serveur[/bold green] sur http://{_host}:{_port}")
    uvicorn.run("app.main:app", host=_host, port=_port, reload=reload)


if __name__ == "__main__":
    cli()
