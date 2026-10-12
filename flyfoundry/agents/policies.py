"""Evolved ANN controller (arm B): one tanh hidden layer, parameter budget matched to the MB model."""
from __future__ import annotations

import numpy as np

from ..config import ExperimentConfig


class MLPPolicy:
    plastic_capable = False

    def __init__(self, cfg: ExperimentConfig, target_params: int):
        self.cfg = cfg
        self.n_in, self.n_out = cfg.n_ctx, cfg.n_dims
        # (n_in+1)*h + (h+1)*n_out ~= target_params  ->  h
        self.h = max(1, round((target_params - self.n_out) / (self.n_in + 1 + self.n_out)))
        self.n_params = (self.n_in + 1) * self.h + (self.h + 1) * self.n_out
        s1 = np.full((self.n_in + 1) * self.h, 1.0 / np.sqrt(self.n_in))
        s2 = np.full((self.h + 1) * self.n_out, 1.0 / np.sqrt(self.h))
        self.init_scale = np.concatenate([s1, s2]).astype(np.float32)

    def init_params(self, rng, n):
        return (rng.standard_normal((n, self.n_params)) * self.init_scale).astype(np.float32)

    def _split(self, p):
        n, h, i, o = p.shape[0], self.h, self.n_in, self.n_out
        a = i * h
        W1 = p[:, :a].reshape(n, i, h)
        b1 = p[:, a:a + h]
        c = a + h
        W2 = p[:, c:c + h * o].reshape(n, h, o)
        b2 = p[:, c + h * o:]
        return W1, b1, W2, b2

    def forward(self, params, ctx, eps):
        W1, b1, W2, b2 = self._split(params)
        hid = np.tanh(np.einsum("ni,nih->nh", ctx.astype(np.float32), W1) + b1)
        pre = np.einsum("nh,nho->no", hid, W2) + b2 + eps
        return 1.0 / (1.0 + np.exp(-pre)), None

    def model_card(self) -> dict:
        return {"model_type": "feed-forward ANN (tanh), evolved", "hidden_units": int(self.h),
                "trainable_parameters": int(self.n_params), "learning_rule": "none (evolution only)"}
