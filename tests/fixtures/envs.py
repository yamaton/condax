from pathlib import Path
import shlex
import subprocess
import tempfile
from typing import Generator
import pytest

from condax.conda.conda import Conda


@pytest.fixture(scope="session")
def env_read_only(conda: Conda) -> Generator[Path, None, None]:
    """For efficiency, this env can be reused by all tests which won't modify it.

    This env is guaranteed to contain pip=22.2.2 and some version of python, which it depends on."""
    with tempfile.TemporaryDirectory() as tmp_path:
        prefix = Path(tmp_path) / "env_read_only"
        conda.create_env(prefix, "pip=22.2.2")
        yield prefix


@pytest.fixture(scope="session")
def empty_env(conda: Conda) -> Generator[Path, None, None]:
    """For efficiency, this env can be reused by all tests which won't modify it.
    This env is guaranteed to contain no packages."""
    with tempfile.TemporaryDirectory() as tmp_path:
        prefix = Path(tmp_path) / "empty_env"
        subprocess.run(
            shlex.split(f"{conda.exe} create --prefix {prefix} --yes --quiet")
        )
        yield prefix
