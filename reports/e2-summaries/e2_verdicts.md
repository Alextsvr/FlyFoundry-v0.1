## E2 verdicts (island model vs single pool)

100 paired repeats; 10 islands x pop P vs one pool of 10P; 60 generations; migration every 10 gens, 3 elites per event. Metric `final_qd` judged once on the `final` contexts. Rules fixed in docs/V0_2_SPEC.md before the run.

| Arm | Condition | final_qd [95% CI] | winner's-curse gap [95% CI] | evals |
|---|---|---|---|---|
| B_evolved_ann | islands_mig | 0.367 [0.365, 0.369] | +0.008 [+0.005, +0.011] | 60000 |
| B_evolved_ann | islands_nomig | 0.368 [0.366, 0.370] | +0.011 [+0.007, +0.015] | 60000 |
| B_evolved_ann | single_pool | 0.370 [0.368, 0.372] | +0.010 [+0.006, +0.014] | 60000 |
| C_genetic | islands_mig | 0.406 [0.404, 0.408] | +0.018 [+0.015, +0.021] | 60000 |
| C_genetic | islands_nomig | 0.405 [0.403, 0.407] | +0.019 [+0.016, +0.021] | 60000 |
| C_genetic | single_pool | 0.391 [0.388, 0.393] | +0.017 [+0.013, +0.020] | 60000 |

| Test | Arm | Contrast (metric) | Diff [CI] | Kind | Verdict |
|---|---|---|---|---|---|
| E2-H1 | B_evolved_ann | islands_mig - single_pool (final_qd) | -0.0038 [-0.0069, -0.0009] (97.5% CI) | primary | **REFUTED** |
| E2-H2 | B_evolved_ann | islands_mig - islands_nomig (final_qd) | -0.0014 [-0.0040, +0.0012] (95.0% CI) | exploratory | **INCONCLUSIVE** |
| E2-H3 | B_evolved_ann | islands_nomig - single_pool (final_qd) | -0.0024 [-0.0055, +0.0007] (95.0% CI) | exploratory | **INCONCLUSIVE** |
| E2-H4 | B_evolved_ann | islands_mig - single_pool (gap) | -0.0018 [-0.0069, +0.0033] (95.0% CI) | exploratory | **INCONCLUSIVE** |
| E2-H1 | C_genetic | islands_mig - single_pool (final_qd) | +0.0153 [+0.0117, +0.0192] (97.5% CI) | primary | **SUPPORTED** |
| E2-H2 | C_genetic | islands_mig - islands_nomig (final_qd) | +0.0014 [-0.0008, +0.0038] (95.0% CI) | exploratory | **INCONCLUSIVE** |
| E2-H3 | C_genetic | islands_nomig - single_pool (final_qd) | +0.0139 [+0.0104, +0.0173] (95.0% CI) | exploratory | **SUPPORTED** |
| E2-H4 | C_genetic | islands_mig - single_pool (gap) | +0.0010 [-0.0038, +0.0059] (95.0% CI) | exploratory | **INCONCLUSIVE** |
