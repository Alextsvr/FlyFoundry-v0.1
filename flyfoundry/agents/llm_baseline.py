"""Arm E: conventional LLM research baseline (adapter only; NOT RUN unless a real endpoint exists).

No LLM responses are ever simulated. ``availability()`` reports NOT RUN with a
reason when no OpenAI-compatible endpoint is configured through environment
variables:

    FLYFOUNDRY_LLM_ENDPOINT   e.g. https://<host>/v1/chat/completions
    FLYFOUNDRY_LLM_MODEL      model name understood by that endpoint
    FLYFOUNDRY_LLM_API_KEY    bearer token (read from env only, never stored)

The adapter proposes 12-number candidates for a given market context and
parses them with ``parse_candidates``. Every proposal would be scored by the
same ``Evaluator`` (same budget accounting) as the other arms.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

import numpy as np

STATUS_NOT_RUN = "NOT RUN"


def availability() -> tuple[bool, str]:
    if not os.environ.get("FLYFOUNDRY_LLM_ENDPOINT"):
        return False, "NOT RUN: FLYFOUNDRY_LLM_ENDPOINT is not set (no free LLM endpoint configured in this environment)"
    if not os.environ.get("FLYFOUNDRY_LLM_MODEL"):
        return False, "NOT RUN: FLYFOUNDRY_LLM_MODEL is not set"
    return True, "endpoint configured"


def build_prompt(ctx: np.ndarray, n: int, n_dims: int) -> str:
    return (
        "You are proposing synthetic benchmark candidates for business-opportunity discovery.\n"
        f"Market context vector (4 numbers in [0,1]): {np.round(ctx, 3).tolist()}\n"
        f"Return ONLY a JSON list of {n} lists, each with exactly {n_dims} numbers in [0,1].\n"
        "Dims: 0 customer,1 problem,2 solution,3 revenue mechanism,4 capital (low is better),"
        "5 effort (low is better),6 evidence strength,7 differentiation,8 claimed demand,"
        "9 channel,10 automation,11 risk."
    )


def parse_candidates(text: str, n_dims: int) -> np.ndarray:
    """Extract a JSON list of candidate vectors from model text; invalid rows are dropped."""
    m = re.search(r"\[\s*\[.*\]\s*\]", text, re.S)
    if not m:
        return np.zeros((0, n_dims))
    try:
        rows = json.loads(m.group(0))
    except json.JSONDecodeError:
        return np.zeros((0, n_dims))
    good = [r for r in rows if isinstance(r, list) and len(r) == n_dims
            and all(isinstance(v, (int, float)) for v in r)]
    if not good:
        return np.zeros((0, n_dims))
    return np.clip(np.asarray(good, dtype=float), 0.0, 1.0)


class LLMBaselineAdapter:
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    def propose(self, ctx: np.ndarray, n: int, n_dims: int) -> np.ndarray:
        ok, reason = availability()
        if not ok:
            raise RuntimeError(reason)
        body = json.dumps({
            "model": os.environ["FLYFOUNDRY_LLM_MODEL"],
            "messages": [{"role": "user", "content": build_prompt(ctx, n, n_dims)}],
            "temperature": 0.8,
        }).encode()
        headers = {"Content-Type": "application/json"}
        key = os.environ.get("FLYFOUNDRY_LLM_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(os.environ["FLYFOUNDRY_LLM_ENDPOINT"], data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
            payload = json.loads(r.read())
        text = payload["choices"][0]["message"]["content"]
        return parse_candidates(text, n_dims)
