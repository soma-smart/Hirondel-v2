# Hirondel v2 — Dataiku Pipeline Explorer

Interface web + CLI pour explorer les **Flows** et **Datasets** d'un DSS Dataiku.

## Prérequis

- Python 3.11+
- Accès à une instance Dataiku DSS avec une clé API

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copiez `.env.example` en `.env` et renseignez vos credentials :

```bash
cp .env.example .env
```

```env
DATAIKU_HOST=https://your-dataiku.example.com
DATAIKU_API_KEY=your-api-key-here
DATAIKU_DEFAULT_PROJECT=MY_PROJECT   # optionnel
```

---

## Interface web

Démarrez le serveur :

```bash
python cli.py serve
# ou
python -m app.main
```

Ouvrez [http://localhost:8000](http://localhost:8000).

| URL | Description |
|-----|-------------|
| `/` | Liste des projets |
| `/projects/{key}/flow` | Visualisation du flow (graphe interactif) |
| `/projects/{key}/datasets` | Tableau des datasets avec filtre |

### API JSON

| URL | Description |
|-----|-------------|
| `/api/projects` | Liste des projets (JSON) |
| `/projects/{key}/flow/api` | Graphe de flux (JSON) |
| `/projects/{key}/datasets/api` | Datasets (JSON) |
| `/projects/{key}/datasets/{name}/api` | Détails d'un dataset (JSON) |

---

## CLI

```bash
# Lister les projets
python cli.py projects

# Lister les datasets d'un projet
python cli.py datasets MY_PROJECT
python cli.py datasets MY_PROJECT --filter sales
python cli.py datasets MY_PROJECT --json-output

# Explorer le flow
python cli.py flow MY_PROJECT
python cli.py flow MY_PROJECT --type DATASET
python cli.py flow MY_PROJECT --json-output

# Lancer le serveur web
python cli.py serve --port 8080 --reload
```

---

## Structure du projet

```
.
├── app/
│   ├── main.py          # Application FastAPI
│   ├── client.py        # Client Dataiku (dataikuapi)
│   ├── routes/
│   │   ├── datasets.py  # Routes /datasets
│   │   └── flows.py     # Routes /flow
│   ├── templates/       # Templates HTML (Jinja2)
│   └── static/          # CSS
├── cli.py               # Interface ligne de commande
├── requirements.txt
└── .env.example
```
Nouvelle version d’Hirondelle, un projet permettant la migration automatique, industrialisée et supervisée des pipelines de données.
