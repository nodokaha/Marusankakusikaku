#!/usr/bin/env python3
"""Return healthy only when every configured Basis world answers its health endpoint."""
import os
import sys
import urllib.request
from pathlib import Path

world_file = Path(os.environ.get("WORLD_CONFIG", "/etc/basis/worlds.conf"))
if not world_file.is_file():
    sys.exit(1)
worlds = []
for raw in world_file.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].strip()
    if line:
        fields = line.split(None, 3)
        if len(fields) == 4:
            worlds.append(fields)
if not worlds:
    sys.exit(1)
for index, _ in enumerate(worlds):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{10666 + index}/health", timeout=3) as response:
            if response.status != 200:
                sys.exit(1)
    except Exception:
        sys.exit(1)
sys.exit(0)
