"""Versioned, integrity-checked checkpoints with safe recovery.

Layout of a state directory::

    state/manifest.json            list of checkpoints + sha256 of each file
    state/ckpt_000007.json.gz      gzip(JSON{schema, payload, payload_sha256})

Rules: a missing checkpoint is never silently turned into a fresh start (the
caller must pass ``allow_fresh``); a corrupt newest checkpoint falls back to
the newest *valid* older one and the recovery is reported loudly; if none is
valid the load fails.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .serialize import dumps_gz, loads_gz, state_hash

CKPT_SCHEMA = 1
CKPT_RE = re.compile(r"^ckpt_(\d{6})\.json\.gz$")


class CheckpointError(Exception):
    exit_code = 3


class CheckpointMissing(CheckpointError):
    exit_code = 4


class CheckpointCorrupt(CheckpointError):
    exit_code = 3


class ConfigMismatch(CheckpointError):
    exit_code = 5


@dataclass
class LoadResult:
    payload: dict[str, Any]
    entry: dict[str, Any]
    problems: list[str] = field(default_factory=list)  # problems with NEWER checkpoints

    @property
    def recovered(self) -> bool:
        return bool(self.problems)


@dataclass
class ValidationReport:
    ok: bool
    checkpoints: list[dict[str, Any]]
    messages: list[str]

    def to_dict(self):
        return {"ok": self.ok, "checkpoints": self.checkpoints, "messages": self.messages}


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class CheckpointStore:
    def __init__(self, directory: str | Path, keep: int = 3):
        self.dir = Path(directory)
        self.keep = keep

    @property
    def manifest_path(self) -> Path:
        return self.dir / "manifest.json"

    # ------------------------------------------------------------------ manifest
    def _read_manifest(self) -> tuple[list[dict], list[str]]:
        msgs: list[str] = []
        if self.manifest_path.exists():
            try:
                m = json.loads(self.manifest_path.read_text())
                body = m["checkpoints"]
                expect = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
                if m.get("manifest_sha256") != expect:
                    raise ValueError("manifest hash mismatch")
                return list(body), msgs
            except Exception as e:  # noqa: BLE001
                msgs.append(f"manifest unreadable ({e}); rediscovering checkpoint files")
        # rediscovery from files (self-describing via embedded hash)
        entries = []
        for p in sorted(self.dir.glob("ckpt_*.json.gz")) if self.dir.exists() else []:
            m = CKPT_RE.match(p.name)
            if m:
                entries.append({"version": int(m.group(1)), "file": p.name, "sha256": None})
        return entries, msgs

    def _write_manifest(self, entries: list[dict], extra: dict | None = None) -> None:
        doc = {"checkpoints": entries,
               "manifest_sha256": hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()}
        doc.update(extra or {})
        _atomic_write(self.manifest_path, json.dumps(doc, indent=1, sort_keys=True).encode())

    def read_manifest_extra(self) -> dict:
        try:
            m = json.loads(self.manifest_path.read_text())
            return m.get("extra", {})
        except Exception:  # noqa: BLE001
            return {}

    def exists(self) -> bool:
        return self.manifest_path.exists() or (
            self.dir.exists() and any(CKPT_RE.match(p.name) for p in self.dir.iterdir()))

    # ---------------------------------------------------------------------- save
    def save(self, payload: dict[str, Any], meta: dict[str, Any], extra: dict | None = None) -> dict:
        entries, _ = self._read_manifest()
        version = max([e["version"] for e in entries], default=0) + 1
        doc = {"schema": CKPT_SCHEMA, "payload": payload, "payload_sha256": state_hash(payload)}
        blob = dumps_gz(doc)
        name = f"ckpt_{version:06d}.json.gz"
        _atomic_write(self.dir / name, blob)
        entry = {"version": version, "file": name, "sha256": hashlib.sha256(blob).hexdigest(),
                 "bytes": len(blob), "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 **meta}
        entries.append(entry)
        # prune oldest, keeping `keep`
        entries.sort(key=lambda e: e["version"])
        while len(entries) > self.keep:
            old = entries.pop(0)
            try:
                (self.dir / old["file"]).unlink()
            except FileNotFoundError:
                pass
        old_extra = self.read_manifest_extra()
        old_extra.update(extra or {})
        self._write_manifest(entries, {"extra": old_extra})
        # read-back verification
        self._load_entry(entry)
        return entry

    # ---------------------------------------------------------------------- load
    def _load_entry(self, entry: dict) -> dict[str, Any]:
        p = self.dir / entry["file"]
        if not p.exists():
            raise CheckpointCorrupt(f"{entry['file']}: file missing")
        blob = p.read_bytes()
        if entry.get("sha256") and hashlib.sha256(blob).hexdigest() != entry["sha256"]:
            raise CheckpointCorrupt(f"{entry['file']}: sha256 mismatch with manifest")
        try:
            doc = loads_gz(blob)
        except Exception as e:  # noqa: BLE001
            raise CheckpointCorrupt(f"{entry['file']}: cannot decode ({e})") from e
        if doc.get("schema") != CKPT_SCHEMA:
            raise CheckpointCorrupt(f"{entry['file']}: unsupported schema {doc.get('schema')}")
        if state_hash(doc["payload"]) != doc.get("payload_sha256"):
            raise CheckpointCorrupt(f"{entry['file']}: embedded payload hash mismatch")
        return doc["payload"]

    def load_latest(self) -> LoadResult:
        if not self.exists():
            raise CheckpointMissing(f"no checkpoint found in {self.dir}")
        entries, msgs = self._read_manifest()
        if not entries:
            raise CheckpointMissing(f"manifest in {self.dir} lists no checkpoints")
        problems = list(msgs)
        for e in sorted(entries, key=lambda e: -e["version"]):
            try:
                payload = self._load_entry(e)
                return LoadResult(payload, e, problems)
            except CheckpointCorrupt as err:
                problems.append(str(err))
        raise CheckpointCorrupt("no valid checkpoint: " + "; ".join(problems))

    def validate(self) -> ValidationReport:
        if not self.exists():
            return ValidationReport(False, [], [f"no checkpoint found in {self.dir}"])
        entries, msgs = self._read_manifest()
        out, ok_any = [], False
        for e in sorted(entries, key=lambda e: e["version"]):
            try:
                payload = self._load_entry(e)
                out.append({"file": e["file"], "version": e["version"], "valid": True,
                            "generation": payload.get("meta", {}).get("generation"),
                            "total_evals": payload.get("meta", {}).get("total_evals")})
                ok_any = True
            except CheckpointCorrupt as err:
                out.append({"file": e["file"], "version": e["version"], "valid": False, "error": str(err)})
        newest_valid = bool(out) and out[-1]["valid"]
        if not newest_valid:
            msgs.append("newest checkpoint is NOT valid")
        return ValidationReport(ok_any and newest_valid and not msgs, out, msgs)
