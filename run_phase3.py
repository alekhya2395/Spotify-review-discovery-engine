"""Phase 3 CLI entry point — Topic Modeling & Clustering.

Examples:
    python run_phase3.py                              # use settings from .env
    python run_phase3.py --discovery-only             # cluster only discovery_related insights
    python run_phase3.py --min-cluster-size 10        # finer-grained topics
    python run_phase3.py --no-llm-labels              # keyword-only labels (no Groq call)
    python run_phase3.py --rebuild                    # force re-embedding from scratch
    python run_phase3.py --json                       # machine-readable summary
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.phase3_clustering import ClusteringPipeline
from src.phase3_clustering.clusterer import Clusterer
from src.phase3_clustering.embedder import Embedder
from src.phase3_clustering.labeler import TopicLabeler

app = typer.Typer(add_completion=False, help="Phase 3 — Topic Modeling & Clustering (BERTopic)")
console = Console()


@app.command()
def main(
    discovery_only: bool = typer.Option(
        False, "--discovery-only/--all", help="Cluster only discovery_related insights."
    ),
    min_cluster_size: Optional[int] = typer.Option(
        None, "--min-cluster-size", "-m",
        help="HDBSCAN min_cluster_size. Lower = more / smaller topics.",
    ),
    n_components: Optional[int] = typer.Option(
        None, "--n-components", help="UMAP target dimensionality (default 5)."
    ),
    n_neighbors: Optional[int] = typer.Option(
        None, "--n-neighbors", help="UMAP n_neighbors (default 15)."
    ),
    embed_model: Optional[str] = typer.Option(
        None, "--embed-model", help="Override the sentence-transformers model id."
    ),
    embed_batch_size: Optional[int] = typer.Option(
        None, "--embed-batch-size", help="Embedder mini-batch size."
    ),
    no_llm_labels: bool = typer.Option(
        False, "--no-llm-labels",
        help="Skip Groq; use top-keyword labels instead (faster, no API quota).",
    ),
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Ignore cached embeddings and recompute from scratch."
    ),
    json_summary: bool = typer.Option(
        False, "--json", help="Print the summary as JSON instead of a table."
    ),
) -> None:
    """Run the Phase 3 clustering pipeline against `data/processed/insights.csv`."""

    embedder = Embedder(model_name=embed_model, batch_size=embed_batch_size)
    clusterer = Clusterer(
        min_cluster_size=min_cluster_size,
        n_components=n_components,
        n_neighbors=n_neighbors,
    )
    labeler = TopicLabeler(use_llm=not no_llm_labels)

    pipeline = ClusteringPipeline(
        embedder=embedder,
        clusterer=clusterer,
        labeler=labeler,
        discovery_only=discovery_only if discovery_only else None,
        use_llm_labels=not no_llm_labels,
        force_rebuild_embeddings=rebuild,
    )
    summary = pipeline.run()
    payload = ClusteringPipeline.summary_to_dict(summary)

    if json_summary:
        console.print_json(json.dumps(payload, default=str))
        return

    table = Table(title="Phase 3 — Clustering Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Insights considered", str(payload["insights_considered"]))
    table.add_row("Clustered into topics", f"[green]{payload['insights_clustered']}[/green]")
    table.add_row("Noise (unclustered)", str(payload["insights_noise"]))
    table.add_row("Number of topics", f"[bold green]{payload['n_topics']}[/bold green]")
    table.add_row("Embedding model", payload["embedding_model"])
    table.add_row("Embeddings cached?", "yes" if payload["embedding_cache_hit"] else "no (computed)")
    table.add_row("Discovery-only filter", "yes" if payload["cluster_discovery_only"] else "no")
    table.add_row("Duration (sec)", f"{payload['duration_seconds']:.1f}")
    table.add_row("Topics CSV", payload["topics_csv"])
    table.add_row("Insights+topics CSV", payload["insights_with_topics_csv"])
    table.add_row("Embeddings (npy)", payload["embeddings_npy"])

    console.print(table)


if __name__ == "__main__":
    app()
