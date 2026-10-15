"""Template registry (metadata only: no application code is generated for discovered opportunities)."""
from __future__ import annotations

TEMPLATES = [
    {"id": "streamlit_dashboard", "name": "Streamlit analytics dashboard", "keywords": ["dashboard", "streamlit", "analytics", "visualization", "monitor", "radar", "tracker"],
     "intended_use": "Interactive data exploration / monitoring UI for a dataset or API.", "inputs": ["public dataset or API", "metric definitions"],
     "outputs": ["Streamlit app", "README with screenshots", "demo video"], "dependencies": ["streamlit", "pandas", "plotly or altair"],
     "testing": ["unit tests for data transforms", "smoke import of the app", "fixture-based snapshot of key tables"],
     "deployment": ["Streamlit Community Cloud (free) from a public GitHub repo"], "effort_hours": [8, 24], "reuse_from": "panta-signal-radar (Streamlit app structure, data layer, README, demo recording workflow)"},
    {"id": "api_client", "name": "Python API client", "keywords": ["api", "sdk", "client", "wrapper", "integration"],
     "intended_use": "Typed, tested wrapper around a public API with retries and rate limiting.", "inputs": ["API docs", "free-tier key if any"],
     "outputs": ["package", "usage examples", "tests with recorded fixtures"], "dependencies": ["stdlib urllib or requests"],
     "testing": ["offline tests with injected transport", "error/backoff paths"], "deployment": ["pip-installable repo", "GitHub release"], "effort_hours": [3, 8],
     "reuse_from": "flyfoundry.bounty_factory.http.Fetcher (retry, backoff, robots)"},
    {"id": "data_pipeline", "name": "Data collection and normalization pipeline", "keywords": ["data", "pipeline", "etl", "scrape", "collect", "dataset", "index", "aggregate"],
     "intended_use": "Collect public data, normalize, deduplicate, store with provenance.", "inputs": ["source list", "schema"],
     "outputs": ["SQLite or CSV store", "normalized schema docs", "quality report"], "dependencies": ["stdlib sqlite3"],
     "testing": ["dedupe tests", "schema validation", "idempotent rerun"], "deployment": ["GitHub Actions schedule + state branch"], "effort_hours": [6, 20],
     "reuse_from": "flyfoundry.bounty_factory.store / sources"},
    {"id": "scheduled_automation", "name": "Scheduled GitHub Actions automation", "keywords": ["automation", "schedule", "workflow", "bot", "alert", "notify", "ci"],
     "intended_use": "Cron-driven job with persisted state and failure reporting.", "inputs": ["task script", "state location"],
     "outputs": ["workflow YAML", "state branch", "run summary"], "dependencies": ["GitHub Actions free tier"],
     "testing": ["YAML validation", "dry run via workflow_dispatch"], "deployment": ["public repo workflow"], "effort_hours": [2, 6],
     "reuse_from": ".github/workflows/experiment.yml, scripts/state_save.sh, scripts/state_restore.sh"},
    {"id": "cli_utility", "name": "CLI utility", "keywords": ["cli", "command line", "terminal", "developer tool", "devtool", "linter", "tooling"],
     "intended_use": "Single-purpose command-line tool.", "inputs": ["files or stdin"], "outputs": ["CLI", "man-style README"], "dependencies": ["argparse"],
     "testing": ["subprocess tests on fixtures"], "deployment": ["pip install from repo"], "effort_hours": [2, 8], "reuse_from": "flyfoundry.cli.main patterns"},
    {"id": "data_quality", "name": "Data quality and validation toolkit", "keywords": ["validation", "quality", "reconcile", "audit", "schema", "anomaly", "verify", "check"],
     "intended_use": "Rules-based checks over tabular data with explainable findings.", "inputs": ["CSV/XLSX", "rule definitions"],
     "outputs": ["findings report", "rule library"], "dependencies": ["stdlib csv"], "testing": ["rule unit tests", "golden reports"],
     "deployment": ["CLI + optional Streamlit front end"], "effort_hours": [4, 16], "reuse_from": "no employer-derived rules: public rule sets only"},
    {"id": "ml_eval", "name": "Lightweight AI/ML evaluation project", "keywords": ["ai", "ml", "machine learning", "model", "llm", "benchmark", "eval", "agent", "classification"],
     "intended_use": "Small reproducible evaluation of models/prompts using free or local resources.", "inputs": ["public dataset", "local model or free tier"],
     "outputs": ["evaluation notebook/script", "results table", "report"], "dependencies": ["numpy", "optional local model"],
     "testing": ["determinism test", "metric unit tests"], "deployment": ["repo + report page"], "effort_hours": [6, 24], "reuse_from": "flyfoundry.research (benchmark discipline, bootstrap CIs)"},
    {"id": "research_report", "name": "Technical research report", "keywords": ["research", "report", "analysis", "whitepaper", "study", "writeup", "essay"],
     "intended_use": "Evidence-based written analysis with reproducible figures.", "inputs": ["public sources"], "outputs": ["markdown/PDF report", "figures", "data appendix"],
     "dependencies": [], "testing": ["citation/link check", "figure regeneration script"], "deployment": ["repo + hosted page"], "effort_hours": [3, 12],
     "reuse_from": "docs/research/ structure; claim/evidence/confidence tagging"},
]


def match_templates(text: str, k: int = 3) -> list:
    t = (text or "").lower()
    scored = []
    for tpl in TEMPLATES:
        hits = [kw for kw in tpl["keywords"] if kw in t]
        if hits:
            scored.append((len(hits) / len(tpl["keywords"]), tpl["id"], hits))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{"id": i, "overlap": round(s, 3), "matched_keywords": h} for s, i, h in scored[:k]]


def by_id(tid: str):
    return next((t for t in TEMPLATES if t["id"] == tid), None)
