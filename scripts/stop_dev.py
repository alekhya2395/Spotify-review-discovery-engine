"""Kill stale Spotify project dev servers on Windows (ports 3000, 3001, 8000)."""

from __future__ import annotations

import subprocess
import sys

PORTS = (3000, 3001, 8000)


def _pids_on_port(port: int) -> set[int]:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except subprocess.CalledProcessError:
        return set()
    pids: set[int] = set()
    needle = f":{port}"
    for line in out.splitlines():
        if "LISTENING" not in line or needle not in line:
            continue
        parts = line.split()
        if parts:
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                pass
    return pids


def main() -> None:
    killed: set[int] = set()
    for port in PORTS:
        for pid in _pids_on_port(port):
            if pid in killed or pid <= 0:
                continue
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            killed.add(pid)
            print(f"Stopped PID {pid} (port {port})")
    if not killed:
        print("No stale dev servers found.")


if __name__ == "__main__":
    main()
