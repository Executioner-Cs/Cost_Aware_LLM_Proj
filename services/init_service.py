"""
orchestrator init — sets up ~/.orchestrator directory, SQLite tables,
Qdrant collection, and warms up the embedding model.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from db.session import create_all_tables, get_session
from utils.console import console, print_success


DEFAULT_CONFIG = """\
[routing]
default_quality = "balanced"
prefer_cheapest = true
fallback_enabled = true

[cache]
enabled = true
ttl_seconds = 86400
similarity_threshold = 0.92
task_thresholds.json_extract = 0.95
task_thresholds.reasoning = 0.93
embedding_model = "all-MiniLM-L6-v2"

[cost]
warn_above_usd = 0.01
monthly_budget_usd = 0

[display]
show_cost = true
show_tokens = true
show_route_reason = true
show_cache_similarity = true
"""


def get_home() -> Path:
    return Path(os.environ.get("ORCHESTRATOR_HOME", Path.home() / ".orchestrator"))


def run_init(home: Path | None = None) -> None:
    if home is None:
        home = get_home()

    home.mkdir(parents=True, exist_ok=True)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:

        # 1. Write default config if absent
        t = progress.add_task("Writing config.toml…")
        config_path = home / "config.toml"
        if not config_path.exists():
            config_path.write_text(DEFAULT_CONFIG)
        progress.update(t, completed=True)

        # 2. Create SQLite tables
        progress.update(t, description="Creating SQLite tables…")
        db_path = home / "orchestrator.db"
        create_all_tables(db_path)
        progress.update(t, completed=True)

        # 3. Create Qdrant collection
        progress.update(t, description="Initialising Qdrant vector store…")
        qdrant_path = home / "qdrant"
        _ensure_qdrant_collection(qdrant_path)
        progress.update(t, completed=True)

        # 4. Warm up embedding model
        progress.update(t, description="Warming up embedding model (first run downloads ~22 MB)…")
        _warmup_embedder()
        progress.update(t, completed=True)

    print_success(f"Orchestrator initialised at [bold]{home}[/bold]")
    console.print(f"  Config  : {home / 'config.toml'}")
    console.print(f"  Database: {home / 'orchestrator.db'}")
    console.print(f"  Vectors : {home / 'qdrant'}")


def _ensure_qdrant_collection(qdrant_path: Path) -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    qdrant_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(qdrant_path))
    collections = {c.name for c in client.get_collections().collections}
    if "semantic_cache" not in collections:
        client.create_collection(
            collection_name="semantic_cache",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    client.close()


def _warmup_embedder() -> None:
    from embeddings.embedder import embed
    embed("warmup")


def load_config(home: Path | None = None) -> dict:
    if home is None:
        home = get_home()
    config_path = home / "config.toml"
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)
