"""Exact (bit-preserving) JSON serialization of nested state with numpy arrays."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from typing import Any

import numpy as np


def encode(o: Any) -> Any:
    if isinstance(o, np.ndarray):
        a = np.ascontiguousarray(o)
        return {"__nd__": base64.b64encode(a.tobytes()).decode("ascii"),
                "dtype": str(a.dtype), "shape": list(a.shape)}
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, dict):
        for k in o:
            if not isinstance(k, str):
                raise TypeError(f"state dict keys must be str, got {type(k)}")
        return {k: encode(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [encode(v) for v in o]
    return o


def decode(o: Any) -> Any:
    if isinstance(o, dict):
        if "__nd__" in o:
            raw = base64.b64decode(o["__nd__"])
            return np.frombuffer(raw, dtype=np.dtype(o["dtype"])).reshape(o["shape"]).copy()
        return {k: decode(v) for k, v in o.items()}
    if isinstance(o, list):
        return [decode(v) for v in o]
    return o


def canonical_bytes(o: Any) -> bytes:
    return json.dumps(encode(o), sort_keys=True, separators=(",", ":")).encode()


def state_hash(o: Any) -> str:
    return hashlib.sha256(canonical_bytes(o)).hexdigest()


def dumps_gz(o: Any) -> bytes:
    return gzip.compress(canonical_bytes(o), compresslevel=6, mtime=0)


def loads_gz(b: bytes) -> Any:
    return decode(json.loads(gzip.decompress(b)))
