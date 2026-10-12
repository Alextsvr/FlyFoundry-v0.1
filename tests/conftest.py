import pytest

from flyfoundry.config import ExperimentConfig


@pytest.fixture(scope="session")
def tiny_cfg():
    return ExperimentConfig(n_seeds=2, pop_size=20, survivors=6, elites=2, gens_per_run=3)


@pytest.fixture(autouse=True)
def _clean_ci_env(monkeypatch):
    """Tests must behave the same locally and on GitHub Actions (reports embed the run URL when these are set)."""
    for k in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_SHA"):
        monkeypatch.delenv(k, raising=False)
