"""Code / environment / dataset provenance."""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]


def code_revision() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


def taxonomy_path() -> Path:
    return REPO_ROOT / "data" / "taxonomy.json"


def taxonomy_hash() -> str:
    p = taxonomy_path()
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"


def environment_info() -> dict:
    return {"python": sys.version.split()[0], "numpy": np.__version__, "platform": platform.platform(),
            "cpu_count": os.cpu_count(), "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_url": (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
                               f"/actions/runs/{os.environ['GITHUB_RUN_ID']}")
            if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_REPOSITORY") else None}
