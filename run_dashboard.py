"""Launch the Phase 6 Streamlit dashboard.

Examples:
    python run_dashboard.py
    python run_dashboard.py --port 8502
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="Phase 6 — PM Dashboard (Streamlit)")


@app.command()
def main(
    port: int = typer.Option(8501, "--port", "-p", help="Streamlit server port."),
    host: str = typer.Option("localhost", "--host", help="Bind address."),
) -> None:
    """Start the Review Discovery dashboard."""
    root = Path(__file__).resolve().parent
    target = root / "src" / "phase6_dashboard" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(target),
        "--server.port",
        str(port),
        "--server.address",
        host,
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    typer.echo(f"Starting dashboard at http://{host}:{port}")
    raise typer.Exit(subprocess.call(cmd))


if __name__ == "__main__":
    app()
