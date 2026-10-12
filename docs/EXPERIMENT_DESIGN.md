# Experiment design

Genome dimensions: 0 customer, 1 problem, 2 solution, 3 revenue mechanism (8 bins each, synthetic taxonomy), 4 capital, 5 effort,
6 evidence strength, 7 differentiation, 8 claimed demand, 9 channel, 10 automation, 11 risk.

Training fitness of candidate x in context z: `max_p v_p * exp(-||x - c_p(z)|| / 0.5) - capital_pen - effort_pen - unsupported_pen + N(0, 0.03)`,
clipped to [-1, 1]. `c_p(z) = clip(c_p + S_p (z - 0.5))`. Penalties: `2*max(0, x4-0.25)`, `1*max(0, x5-0.5)`, `1*max(0, x8-x6-0.15)`.
Duplicates: Goldberg fitness sharing (sigma 0.35) divides reward among agents crowding one location.

Held-out metrics (noise-free, 16 unseen contexts, archive elites only): `heldout_qd` = Σ over real peaks of the best net score in the archive,
normalised by Σ values; `heldout_best` = best net score of any elite; `heldout_discovery` = fraction of real peaks with an elite within radius 0.35
and net ≥ 50% of the peak value. `heldout_qd` gives distance-based partial credit, so it is lenient; discovery rate is stricter.

Budget: every arm, every generation: exactly `pop_size` evaluations. Seeds: seed index s uses RNG streams derived from `seed_base + s`; the
environment stream (scenario choice and observation noise) depends only on s, so arms are paired.

Evolution: A/B: truncation (30 survivors incl. 5 elites, survivors persist and keep learned weights), 70 offspring from tournament(3) or
archive elites (30%), uniform crossover (50%), Gaussian mutation (10% of genes, sigma 0.3x init scale); learned weights are not inherited.
C: tournament(3), uniform crossover, per-gene Gaussian mutation, 5 elites, 5% immigrants. D: fresh uniform samples each generation.
