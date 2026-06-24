"""Start backend + frontend together (recommended for local dev).

    python run_app.py

Opens:
    Frontend  http://127.0.0.1:3000
    Backend   http://127.0.0.1:8000
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


def _wait_for_backend(url: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(1)
    return False


@app.command()
def main(
    port: int = typer.Option(8001, "--backend-port"),
    frontend_port: int = typer.Option(3000, "--frontend-port"),
    clean: bool = typer.Option(True, "--clean/--no-clean", help="Stop stale servers first."),
) -> None:
    root = Path(__file__).resolve().parent
    backend_url = f"http://127.0.0.1:{port}/api/health"

    if clean:
        typer.echo("Stopping stale dev servers...")
        subprocess.run([sys.executable, str(root / "scripts" / "stop_dev.py")], cwd=root, check=False)

    typer.echo("Starting backend...")
    backend_proc = subprocess.Popen(
        [sys.executable, str(root / "run_backend.py"), "--port", str(port)],
        cwd=root,
    )

    typer.echo(f"Waiting for backend at {backend_url} ...")
    if not _wait_for_backend(backend_url):
        backend_proc.terminate()
        typer.echo("ERROR: Backend did not start in time.")
        raise typer.Exit(1)

    typer.echo("Backend is ready.")
    typer.echo("")
    typer.echo(f"Starting frontend at http://127.0.0.1:{frontend_port}")
    typer.echo("Press Ctrl+C to stop both servers.")
    typer.echo("")

    frontend_proc = subprocess.Popen(
        [sys.executable, str(root / "run_frontend.py"), "--port", str(frontend_port)],
        cwd=root,
    )

    try:
        frontend_proc.wait()
    except KeyboardInterrupt:
        typer.echo("\nStopping...")
    finally:
        frontend_proc.terminate()
        backend_proc.terminate()
        frontend_proc.wait(timeout=5)
        backend_proc.wait(timeout=5)


if __name__ == "__main__":
    app()
