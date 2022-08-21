import pytest

from condax.conda.conda import Conda


@pytest.fixture(scope="session")
def conda() -> Conda:
    return Conda(channels=("conda-forge",))
