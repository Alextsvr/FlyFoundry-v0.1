"""Mushroom-body-INSPIRED sparse controller (NOT a FlyWire connectome).

Model card (also emitted into every checkpoint / report via ``model_card``):

* Circuit motif: projection neurons (PN) -> Kenyon cells (KC) -> output neurons
  (MBON), with a global inhibitory (APL-like) feedback that keeps only the
  top-k KCs active (sparse coding), and a reward-modulated (dopamine-like)
  three-factor plasticity rule on KC->MBON synapses.
* Wiring: a seeded, synthetic PN->KC pattern with ``kc_claws`` inputs per KC
  (fly KCs have a handful of claws). The intact variant is *modality-biased*
  (several claws from the same context channel) which is a modelling
  hypothesis, not a measurement. The shuffled ablation permutes edge
  endpoints while preserving every KC in-degree.
* NO real connectivity data is used. It must not be called a connectome.
* Plasticity (per agent, per evaluation), with reward R, running baseline b,
  dopamine-like error d = R - b, exploration noise eps ~ N(0, sigma^2) added to
  the MBON pre-activation, KC activity k in {0,1}:
      dW[o,j] = eta * d * (eps[o] / sigma) * k[j]
      db[o]   = eta_b * d * (eps[o] / sigma)
      W <- W + weight_decay * (W0 - W);   W <- clip(W, +-weight_clip)
      b <- (1 - beta) * R + beta * b
  This is a node-perturbation / REINFORCE-style rule, a computational
  abstraction of dopamine-gated KC->MBON depression/potentiation.
* Learned weights are NOT inherited (Baldwinian): offspring inherit the evolved
  initial weights W0 only.
"""
from __future__ import annotations

import numpy as np

from ..config import ExperimentConfig


def build_wiring(cfg: ExperimentConfig, seed: int, shuffled: bool) -> np.ndarray:
    """Binary PN->KC matrix of shape (n_pn, n_kc)."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 31337]))
    n_dim, per = cfg.n_ctx, cfg.pn_per_dim
    n_pn, K = n_dim * per, cfg.n_kc
    C = np.zeros((n_pn, K), dtype=np.float32)
    for k in range(K):
        mod = k % n_dim
        same = rng.choice(per, size=min(cfg.kc_same_modality, per), replace=False) + mod * per
        others = [p for p in range(n_pn) if p // per != mod]
        rest = rng.choice(others, size=cfg.kc_claws - len(same), replace=False)
        C[np.concatenate([same, rest]), k] = 1.0
    if shuffled:
        # degree-preserving rewiring: draw each KC's inputs from the pooled multiset of all PN edge endpoints
        edges_pn = list(np.nonzero(C.T)[1])
        deg = C.sum(axis=0).astype(int)
        for _ in range(500):
            pool = list(rng.permutation(edges_pn))
            C2 = np.zeros_like(C)
            ok = True
            for k in rng.permutation(len(deg)):
                chosen = []
                for p in list(pool):
                    if p not in chosen:
                        chosen.append(p)
                        pool.remove(p)
                        if len(chosen) == deg[k]:
                            break
                if len(chosen) != deg[k]:
                    ok = False
                    break
                C2[chosen, k] = 1.0
            if ok:
                return C2
        raise RuntimeError("could not produce a valid shuffled wiring")
    return C


class MushroomBodyPolicy:
    plastic_capable = True

    def __init__(self, cfg: ExperimentConfig, wiring_seed: int, shuffled: bool = False):
        self.cfg = cfg
        self.n_out, self.K = cfg.n_dims, cfg.n_kc
        self.C = build_wiring(cfg, wiring_seed, shuffled)
        self.centers = np.linspace(0.0, 1.0, cfg.pn_per_dim)
        self.n_params = self.n_out * self.K + self.n_out
        self.init_scale = np.concatenate([np.full(self.n_out * self.K, cfg.w_init_std),
                                          np.full(self.n_out, 0.1)]).astype(np.float32)

    # ---------------------------------------------------------------- params
    def init_params(self, rng, n):
        return (rng.standard_normal((n, self.n_params)) * self.init_scale).astype(np.float32)

    def _split(self, params):
        n = params.shape[0]
        W = params[:, : self.n_out * self.K].reshape(n, self.n_out, self.K)
        b = params[:, self.n_out * self.K:]
        return W, b

    # --------------------------------------------------------------- forward
    def pn_activity(self, ctx):
        z = (ctx[:, :, None] - self.centers[None, None, :]) / self.cfg.pn_width
        return np.exp(-z * z).reshape(len(ctx), -1).astype(np.float32)

    def forward(self, params, ctx, eps):
        pn = self.pn_activity(ctx)
        kc_pre = pn @ self.C
        top = np.argpartition(-kc_pre, self.cfg.kc_active - 1, axis=1)[:, : self.cfg.kc_active]
        kc = np.zeros_like(kc_pre)
        np.put_along_axis(kc, top, 1.0, axis=1)  # APL-like winner-take-top-k
        W, b = self._split(params)
        pre = np.einsum("nk,nok->no", kc, W) + b + eps
        return 1.0 / (1.0 + np.exp(-pre)), kc

    # ------------------------------------------------------------ plasticity
    def plastic_update(self, params, genome, cache_kc, eps, delta):
        cfg = self.cfg
        W, b = self._split(params)
        W0, _ = self._split(genome)
        e = (eps / cfg.explore_sigma).astype(np.float32)
        d = delta.astype(np.float32)
        W += cfg.eta * d[:, None, None] * e[:, :, None] * cache_kc[:, None, :]
        b += cfg.eta_bias * d[:, None] * e
        W += cfg.weight_decay * (W0 - W)
        np.clip(W, -cfg.weight_clip, cfg.weight_clip, out=W)

    def model_card(self) -> dict:
        return {
            "model_type": "mushroom-body-inspired sparse network (synthetic wiring)",
            "uses_real_flywire_connectivity": False,
            "n_pn": int(self.C.shape[0]), "n_kc": int(self.K), "n_mbon_outputs": int(self.n_out),
            "fixed_pn_kc_synapses": int(self.C.sum()),
            "plastic_kc_mbon_synapses": int(self.n_out * self.K),
            "trainable_parameters": int(self.n_params),
            "kc_active_k": int(self.cfg.kc_active),
            "learning_rule": "reward-modulated node-perturbation (three-factor), see module docstring",
            "references": [
                "Aso et al. 2014, eLife, The neuronal architecture of the mushroom body (Drosophila).",
                "Caron et al. 2013, Nature, Random convergence of olfactory inputs in the Drosophila mushroom body.",
                "Dorkenwald et al. 2024, Nature, Neuronal wiring diagram of an adult brain (FlyWire).",
            ],
            "biological_limitations": [
                "No FlyWire / hemibrain data is loaded; wiring is synthetic.",
                "Rate-based, no spikes, no neuromodulator dynamics, single learning compartment.",
                "Inputs are 4 abstract market-context numbers, not sensory stimuli.",
                "Outputs are 12 candidate parameters, not behaviour.",
            ],
        }
