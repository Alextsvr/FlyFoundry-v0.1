# FlyFoundry Phase 1 — task the swarm: a ranked list of business models

Status: APPROVED by the owner on 2026-10-13 with the decisions in section 9; written before any Phase 1 code or probe run.
Language note: repo docs are English; the owner discusses in Russian.

## 0. What Phase 1 can and cannot deliver (read this first)

- The synthetic benchmark of Phase 0 contains no information about real markets. Everything the swarm found there says
  nothing about real businesses. Phase 1 therefore needs a REAL evidence layer, and the quality of the final ranking is
  bounded by the quality of that layer, not by the evolutionary search.
- Free, unattended, machine-checkable evidence is thin: public APIs give counts of mentions, repos and job posts, not
  willingness to pay. Willingness to pay is only observable by asking real people for money (level L4), which the system
  cannot do (owner's decision: no outreach, KYC, accounts or payments by automation).
- Therefore the deliverable is a **shortlist of hypotheses with evidence links, ranked and tested for robustness**, whose
  purpose is to decide which 3-5 micro-experiments the owner runs by hand. It is never a result and never "a business".
- Expected honest outcome space: (a) the automated layer reproduces known verdicts well enough to be useful, (b) it does
  not, and Phase 1 degrades to a curated list with a clear statement that automation added nothing. Both are acceptable;
  the stop rule in section 6 decides which one we report.

## 1. Task

Rank candidate business models in an idea space wider than the original УБТ project, with no dependence on a human
closer, EUR 0 running cost, and the owner's profile constraints (solo operator, Latvia/EU, Python/data/automation
skills, payments/reconciliation background, hardware: one Windows PC with a laptop GPU, GitHub free tier).

## 2. Three evidence layers (never mixed in one column)

| Layer | Content | Source | Label in output |
|---|---|---|---|
| F — verified facts | machine-checkable, dated, with URL and response hash: counts of mentions, free alternatives, job posts | probes (section 3) | `fact` |
| C — curated rules | hard blockers and structural features that a person wrote with a citation: ToS/law blockers, capital need, automatable share | `data/ideas.csv` (hand-maintained, each row has a source URL or "owner judgement") | `curated` |
| J — model judgement | plausibility scores by an LLM (local model on the owner's GPU, or Claude-in-the-loop if later enabled) | optional module, OFF by default | `unverified model opinion` |

Phase 1 v1 uses F + C only. J is added only after the calibration of section 6 shows F + C alone are insufficient.

## 3. Probes (layer F): free, official, rate-limited

| Probe | Source | What it measures | Notes |
|---|---|---|---|
| pain-mentions | Hacker News Algolia API (no key) | count of posts/comments in 24 months matching pain phrases of the idea | demand proxy, biased to tech audience |
| question-volume | Stack Exchange API (free key, optional) | questions per tag/phrase | demand proxy for technical problems |
| free-alternatives | GitHub search API (Actions token, 5000/h) | repos and stars of open-source tools solving the same task | competition pressure from free tools |

Rules: official APIs only, a descriptive User-Agent, honour rate limits and robots/ToS, never bypass a block (a blocked
source is recorded as `blocked`, not worked around). Every response is stored (hash + date) in the state branch so the
analysis can be re-run offline and so drift of the live web is visible. Pricing pages and forums that forbid scraping are
NOT probed; prices enter only through layer C with a citation. Query phrases for each idea are written in
`data/ideas.csv` BEFORE the first probe run and frozen by commit hash (no tuning of queries after seeing counts).

## 4. Idea space

- Taxonomy v4 (`data/taxonomy.json` extended from 8x8x8x8x4 to a wider list: about 30 customer segments, 30 problems,
  15 solution types, 8 revenue mechanisms, 5 channels), each entry short and concrete. The v3 list stays as a subset.
- A candidate = one tuple from the taxonomy plus layer-C features (capital need, automatable share, regulatory friction,
  platform dependency, solo-operator fit). Combinations that are nonsense are removed by a rule table (layer C).
- The 12 hypotheses H01-H12 are part of the idea space (they are the calibration set, section 6) and are marked so.

## 5. Search and fitness

- Probe budget decides whether evolution is useful: candidates are many (tens of thousands), probes are rate-limited. The
  swarm (islands of the GA arm, selection on a `select` subset, final judgement on held-back candidates) decides which
  candidates get probed next. A plain random-sampling baseline with the same probe budget is mandatory (E2 lesson: gains of
  structure were small; E3 lesson: weak criteria prove nothing).
- Fitness of a candidate = weighted sum of normalised layer-F and layer-C features. Five weight sets are fixed in advance
  (the five of `data/h01_h12_weights.csv` mapped to the new feature names). Reported ranking = rank under each weight set
  plus the rank range. A candidate is "robust" only if it stays in the top 10% under all five.
- Hard gates (layer C) remove a candidate before scoring: needs a licence the owner cannot get, depends on a platform that
  bans the activity, requires paid data with no free substitute, requires outreach/KYC/payment handling by the system.

## 6. Validation and stop rule (pre-registered; this is what E3 lacked)

- **Calibration set:** H01-H12. Reference score y = number of positive track verdicts in `zero-capital-synthesis-v1`
  section 2 (A, B, C each: STRONG/PROMISING = 1, split = 0.5, WEAK/KILL = 0): H07=3, H01=2, H05=2, H11=2, H12=2, H08=1.5,
  H02=1, H04=1, H09=1, H10=1, H03=0, H06=0. y comes from manual deep research done independently of the probes.
- **Test:** Spearman rho between the automated layer-F score (frozen queries, one weight set = equal) and y; one-sided
  permutation test (10 000 shuffles), bootstrap CI over the 12 items. **PASS** if rho >= 0.5 and p <= 0.05.
  **Negative control:** the same pipeline with probe results shuffled across ideas must give rho near 0 (checks the
  harness). Power is low (n = 12): a FAIL means "not shown", not "uninformative".
- **Stop rule:** if the calibration FAILS, Phase 1 reports the ranking from layer C alone, labelled "curated, automation
  did not add information", and the probes are not used for ranking. If it PASSES, the combined ranking is produced and
  every item still carries `evidence level <= L3`.
- **Stability:** two probe runs 7 days apart must give Spearman >= 0.8 on the idea scores; otherwise the probe layer is too
  noisy to rank anything.
- **Leakage guard:** the calibration items are ranked by the same code path as all other candidates; no item-specific
  rule exists. A static test checks that `y` values are not importable from the scoring code.

## 7. Outputs

`reports/phase1/`: ranking table (idea, rank under each weight set, rank range, F features with URLs and dates, C features
with citations, gates passed), calibration verdict, stability verdict, probe budget used, and a one-page "what to test by
hand next" section for the top 3-5 with the single cheapest real-world check for each (the check is run by the owner, not
by the system). Plus a HTML dashboard published as an artifact.

## 8. Resource and policy envelope

Same caps as Phase 0 (<= 10 parallel jobs, <= 120 job-minutes/day, kill switch). Probe calls cached and capped per day
(starting value 3 000 requests/day across all sources). No new paid service, no secret except an optional free Stack
Exchange key. Claude-in-the-loop stays OFF.

## 9. Owner decisions (2026-10-13)

1. Scope and the stop rule of section 6: APPROVED.
2. Probe sources: Hacker News, GitHub, Stack Exchange only. Freelance job APIs: NOT approved (dropped from section 3).
3. Layer J (LLM judgement): NOT now. Phase 1 v1 = layers F + C only; J only after a calibration FAIL shows it is needed,
   and only with the owner's separate approval.
4. Seed ideas beyond H01-H12 and the taxonomy: still open (needed for P1-D, not for P1-C).

Implementation notes: from the Claude working environment and from the owner's PC sandbox none of the three APIs is
reachable, so live probes run only on GitHub Actions (`phase1-probe` workflow); code is tested offline with fixtures.

## 10. Work packages

P1-A probes + cache + tests (offline fixtures); P1-B `data/ideas.csv` with frozen queries for H01-H12 and the taxonomy v4;
P1-C calibration + negative control + stability; P1-D swarm search over the idea space with a random-sampling baseline;
P1-E report and dashboard. P1-C gates P1-D: no ranking is produced before the calibration verdict exists.

## 11. Outcome log

- 2026-10-13, P1-C calibration run 1 (Actions run 38371302136): FAIL (rho -0.18, p 0.71). Stop rule triggered: layer F is not used for
  ranking; Phase 1 continues with layer C only. See docs/RESULTS.md. The 7-day stability check is moot for ranking purposes
  but may still be run once to document probe noise.
