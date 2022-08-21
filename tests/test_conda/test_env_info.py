from pathlib import Path
import pytest

from condax.conda.env_info import find_envs, is_env, find_exes
from condax.conda.exceptions import NoPackageMetadataError


def test_is_env(env_read_only: Path):
    assert is_env(env_read_only)


def test_is_env_empty_env(empty_env: Path):
    assert is_env(empty_env)


def test_is_env_empty_dir(tmp_path: Path):
    assert not is_env(tmp_path)


def test_is_env_file(tmp_path: Path):
    (tmp_path / "foo.txt").touch()
    assert not is_env(tmp_path)


def test_is_env_not_exists(tmp_path: Path):
    assert not is_env(tmp_path / "foo/bar/biz/")


def test_find_exes(env_read_only: Path):
    exes = {exe.name for exe in find_exes(env_read_only, "pip")}
    assert "pip" in exes
    assert "pip3" in exes
    assert "python" not in exes

    with pytest.raises(NoPackageMetadataError):
        assert not find_exes(env_read_only, "foo")


def test_find_exes_empty_env(empty_env: Path):
    with pytest.raises(NoPackageMetadataError):
        find_exes(empty_env, "pip")


def test_find_envs(env_read_only: Path, empty_env: Path):
    for env in (env_read_only, empty_env):
        assert env in find_envs(env.parent)


def test_find_envs_empty_dir(tmp_path: Path):
    assert find_envs(tmp_path) == set()
