# data/

`h01_h12_scores.csv` and `h01_h12_weights.csv` are transcribed by hand from section 5 ("Comparative scoring") of the
project document `zero-capital-synthesis-v1` (УБТ 2.0 project, 2026-09/10): 12 hypotheses x 13 criteria scored 1-5
(5 = favourable) and 5 weight sets. They are the project's own judgement scores, NOT market data.
`tests/test_backtest.py` re-computes the weighted means and checks them against the published table (H07 3.87 ... H03 1.82).
