"""Start the FastAPI backend for the Next.js dashboard.

Examples:
    python run_backend.py
    python run_backend.py --port 8000
    python run_backend.py --prepare-data
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="Start FastAPI backend (port 8000)")


def _groq_key_from_root(root_env: Path) -> str | None:
    """Return the last non-empty GROQ_API_KEY from the project root .env."""
    if not root_env.exists():
        return None
    found: str | None = None
    for line in root_env.read_text(encoding="utf-8").splitlines():
        if not line.startswith("GROQ_API_KEY="):
            continue
        value = line.split("=", 1)[1].strip().strip('"').strip("'")
        if value:
            found = value
    return found


def _sync_groq_key(root: Path, env_file: Path) -> None:
    """Copy GROQ_API_KEY from project root .env into backend/.env if missing."""
    key = _groq_key_from_root(root / ".env")
    if not key:
        return
    if env_file.exists():
        existing = env_file.read_text(encoding="utf-8")
        for line in existing.splitlines():
            if line.startswith("GROQ_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return
    env_file.parent.mkdir(parents=True, exist_ok=True)
    base = env_file.read_text(encoding="utf-8") if env_file.exists() else (root / "backend" / ".env.example").read_text(encoding="utf-8")
    lines = [ln for ln in base.splitlines() if not ln.startswith("GROQ_API_KEY=")]
    lines.append(f"GROQ_API_KEY={key}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    typer.echo("Synced GROQ_API_KEY from project .env into backend/.env")


@app.command()
def main(
    port: int = typer.Option(8000, "--port", "-p"),
    prepare_data: bool = typer.Option(
        False,
        "--prepare-data",
        help="Run backend/prepare_data.py before starting (refresh deploy CSVs).",
    ),
) -> None:
    root = Path(__file__).resolve().parent
    backend = root / "backend"
    env_example = backend / ".env.example"
    env_file = backend / ".env"

    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
        typer.echo("Created backend/.env from .env.example — add your GROQ_API_KEY for chat.")

    _sync_groq_key(root, env_file)

    data_files = list((backend / "data").glob("insights_*.csv"))
    if not data_files or prepare_data:
        typer.echo("Preparing backend data...")
        subprocess.run([sys.executable, str(backend / "prepare_data.py")], cwd=root, check=True)

    if not list((backend / "data").glob("insights_*.csv")):
        typer.echo("ERROR: No insights CSV in backend/data/. Run: python backend/prepare_data.py")
        raise typer.Exit(1)

    typer.echo(f"Starting backend at http://localhost:{port}")
    typer.echo(f"Health check: http://localhost:{port}/api/health")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    subprocess.run(cmd, cwd=backend, check=False)


if __name__ == "__main__":
    app()
