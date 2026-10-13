## E3 plumbing backtest (NOT validation)

30 repeats, 60 generations, GA over 13 criterion weights. Train weight sets: base, equal, money_first; judged once on: automation_first, risk_averse.

**Verdict: PASS** - 100% of repeats satisfy all of: Spearman >= 0.8 on both final sets, top-2 = {H07, H01}, last = H03 (pass needs >= 90%).

| Final weight set | Spearman mean [95% CI] |
|---|---|
| automation_first | 0.965 [0.965, 0.965] |
| risk_averse | 0.930 [0.930, 0.930] |

Baselines (no search): equal_weights: automation_first=0.935, risk_averse=0.963, top2=['H07', 'H01'], last=H03; mean_of_train_weight_sets: automation_first=0.944, risk_averse=0.951, top2=['H07', 'H01'], last=H03
Random weights: mean Spearman automation_first=0.922, risk_averse=0.928; share of random weight vectors passing all criteria: 95.5%.

Mandatory caveat: the inputs are the same scores that define the reference ranking, so a pass shows that the machinery (plugin interface, search, train/final split) works - not that the swarm can find good businesses.
