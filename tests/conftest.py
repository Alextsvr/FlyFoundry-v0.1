import pytest

from flyfoundry.config import ExperimentConfig


@pytest.fixture(scope="session")
def tiny_cfg():
    return ExperimentConfig(n_seeds=2, pop_size=20, survivors=6, elites=2, gens_per_run=3)
