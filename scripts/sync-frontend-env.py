"""Ensure frontend/.env.local points BACKEND_URL at the local API (port 8000)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "frontend" / ".env.local"
LOCAL_BACKEND = "http://127.0.0.1:8000"
KEYS = {
    "BACKEND_URL": LOCAL_BACKEND,
    "NEXT_PUBLIC_API_URL": LOCAL_BACKEND,
}

lines: list[str] = []
if ENV.exists():
    lines = ENV.read_text(encoding="utf-8").splitlines()

out: list[str] = []
seen: set[str] = set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if key in KEYS:
        out.append(f"{key}={KEYS[key]}")
        seen.add(key)
    else:
        out.append(line)

for key, value in KEYS.items():
    if key not in seen:
        out.append(f"{key}={value}")

ENV.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
print(f"Updated {ENV} (BACKEND_URL -> {LOCAL_BACKEND})")
