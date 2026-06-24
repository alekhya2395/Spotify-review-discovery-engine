"""Start the Next.js frontend (http://localhost:3000).

Auto-starts the backend if it is not already running.

Examples:
    python run_frontend.py
    python run_app.py          # starts backend + frontend together
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="Start Next.js frontend (port 3000)")

BACKEND_PORT = 8001


def _backend_health_url(port: int = BACKEND_PORT) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def _backend_up(port: int = BACKEND_PORT) -> bool:
    try:
        with urllib.request.urlopen(_backend_health_url(port), timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _wait_for_backend(port: int = BACKEND_PORT, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _backend_up(port):
            return True
        time.sleep(1)
    return False


@app.command()
def main(
    port: int = typer.Option(3000, "--port", "-p"),
    backend_port: int = typer.Option(BACKEND_PORT, "--backend-port"),
    install: bool = typer.Option(
        False,
        "--install",
        help="Run npm install before starting.",
    ),
) -> None:
    root = Path(__file__).resolve().parent
    frontend = root / "frontend"
    backend_proc: subprocess.Popen | None = None
    started_backend = False

    if not shutil.which("npm"):
        typer.echo("ERROR: npm not found. Install Node.js from https://nodejs.org")
        raise typer.Exit(1)

    env_local = frontend / ".env.local"
    desired_env = (
        f"NEXT_PUBLIC_API_URL=http://127.0.0.1:{backend_port}\n"
        f"BACKEND_URL=http://127.0.0.1:{backend_port}\n"
    )
    if not env_local.exists():
        env_local.write_text(desired_env, encoding="utf-8")
        typer.echo("Created frontend/.env.local")
    else:
        text = env_local.read_text(encoding="utf-8")
        if "8001" in text or "localhost:8000" in text or f"127.0.0.1:{backend_port}" not in text:
            env_local.write_text(desired_env, encoding="utf-8")
            typer.echo(f"Updated frontend/.env.local -> http://127.0.0.1:{backend_port}")

    if not _backend_up(backend_port):
        typer.echo("Backend not running - starting it now...")
        backend_proc = subprocess.Popen(
            [sys.executable, str(root / "run_backend.py"), "--port", str(backend_port)],
            cwd=root,
        )
        started_backend = True
        if not _wait_for_backend(backend_port):
            if backend_proc:
                backend_proc.terminate()
            typer.echo("ERROR: Backend failed to start. Run: python run_backend.py")
            raise typer.Exit(1)
        typer.echo("Backend ready.")
    else:
        typer.echo("Backend already running.")

    if install or not (frontend / "node_modules").exists():
        typer.echo("Installing npm packages (first time may take a few minutes)...")
        subprocess.run(["npm", "install"], cwd=frontend, check=True, shell=True)

    typer.echo("")
    typer.echo("Starting frontend...")
    typer.echo(f"  Dashboard: http://127.0.0.1:{port}")
    typer.echo(f"  API:       http://127.0.0.1:{backend_port}/api/health")
    typer.echo("  Keep this terminal open. Press Ctrl+C to stop.")
    typer.echo("")

    cmd = ["npm", "run", "dev", "--", "-p", str(port), "-H", "127.0.0.1"]
    npm_env = {**dict(__import__("os").environ), "BACKEND_URL": f"http://127.0.0.1:{backend_port}"}
    try:
        subprocess.run(cmd, cwd=frontend, check=False, shell=True, env=npm_env)
    finally:
        if started_backend and backend_proc:
            typer.echo("Stopping backend...")
            backend_proc.terminate()
            backend_proc.wait(timeout=5)


if __name__ == "__main__":
    app()
