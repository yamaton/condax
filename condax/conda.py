from functools import partial
import io
import json
import logging
import os
import shlex
import shutil
import stat
import subprocess
from pathlib import Path
import sys
import tarfile
from typing import Callable, Iterable, List, Optional, Set, Tuple, Union

import requests

from condax.config import C
from condax.exceptions import CondaxError
from condax.utils import FullPath
import condax.utils as utils


logger = logging.getLogger(__name__)


## Need to activate if using micromamba as drop-in replacement
# def _activate_umamba(umamba_path: Path) -> None:
#     print("Activating micromamba")
#     _subprocess_run(
#         f'eval "$({umamba_path} shell hook --shell posix --prefix {C.mamba_root_prefix()})"',
#         shell=True,
#     )


def inject_to_conda_env(specs: Iterable[str], env_name: str, stdout: bool) -> None:
    """Add packages onto existing `env_name`.

    NOTE: a spec may contain version specification.
    """
    conda_exe = ensure_conda()
    prefix = conda_env_prefix(env_name)
    channels_args = [x for c in C.channels() for x in ["--channel", c]]
    specs_args = [shlex.quote(spec) for spec in specs]

    _subprocess_run(
        [
            conda_exe,
            "install",
            "--prefix",
            prefix,
            "--override-channels",
            *channels_args,
            "--quiet",
            "--yes",
            *specs_args,
        ],
        suppress_stdout=not stdout,
    )


def uninject_from_conda_env(
    packages: Iterable[str], env_name: str, stdout: bool
) -> None:
    """Remove packages from existing environment `env_name`."""
    conda_exe = ensure_conda()
    prefix = conda_env_prefix(env_name)

    _subprocess_run(
        [
            conda_exe,
            "uninstall",
            "--prefix",
            prefix,
            "--quiet",
            "--yes",
            *packages,
        ],
        suppress_stdout=not stdout,
    )


def get_package_info(package: str, specific_name=None) -> Tuple[str, str, str]:
    env_prefix = conda_env_prefix(package)
    package_name = package if specific_name is None else specific_name
    conda_meta_dir = env_prefix / "conda-meta"
    try:
        for file_name in conda_meta_dir.glob(f"{package_name}*.json"):
            with open(file_name, "r") as fo:
                package_info = json.load(fo)
                if package_info["name"] == package_name:
                    name: str = package_info["name"]
                    version: str = package_info["version"]
                    build: str = package_info["build"]
                    return (name, version, build)
    except ValueError:
        logger.warning(
            f"Could not retrieve package info: {package}"
            + (f" - {specific_name}" if specific_name else "")
        )

    return ("", "", "")


def _get_conda_package_dirs() -> List[Path]:
    """
    Get the conda's global package directories.

    Equivalent to running `conda info --json | jq '.pkgs_dirs'`
    """
    conda_exe = ensure_conda()
    res = subprocess.run([conda_exe, "info", "--json"], capture_output=True)
    if res.returncode != 0:
        return []

    d = json.loads(res.stdout.decode())
    return [FullPath(p) for p in d["pkgs_dirs"]]


def _get_dependencies(package: str, pkg_dir: Path) -> List[str]:
    """
    A helper function: Get a list of dependent packages for a given package.
    """
    name, version, build = get_package_info(package)
    p = pkg_dir / f"{name}-{version}-{build}/info/index.json"
    if not p.exists():
        return []

    with open(p, "r") as fo:
        index = json.load(fo)

    if not index or "depends" not in index:
        return []

    return index["depends"]


def get_dependencies(package: str) -> List[str]:
    """
    Get a list of dependent packages of a given package.

    Returns a list of package match specifications.

    https://stackoverflow.com/questions/26101972/how-to-identify-conda-package-dependents
    """
    pkg_dirs = _get_conda_package_dirs()
    result = [x for pkg_dir in pkg_dirs for x in _get_dependencies(package, pkg_dir)]
    return result


class SubprocessError(CondaxError):
    def __init__(self, code: int, exe: Union[Path, str]):
        super().__init__(code, f"{exe} exited with code {code}.")


def _subprocess_run(
    args: Union[str, List[Union[str, Path]]], suppress_stdout: bool = True, **kwargs
) -> subprocess.CompletedProcess:
    """
    Run a subprocess and return the CompletedProcess object.
    """
    env = os.environ.copy()
    env.update({"MAMBA_NO_BANNER": "1"})
    res = subprocess.run(
        args,
        **kwargs,
        stdout=subprocess.DEVNULL if suppress_stdout else None,
        env=env,
    )
    if res.returncode != 0:
        raise SubprocessError(res.returncode, args[0])
    return res


def export_env(env_name: str, out_dir: Path, stdout: bool = False) -> None:
    """Export an environment to a conda environment file."""
    conda_exe = ensure_conda()
    prefix = conda_env_prefix(env_name)
    filepath = out_dir / f"{env_name}.yml"
    _subprocess_run(
        [
            conda_exe,
            "env",
            "export",
            "--no-builds",
            "--prefix",
            prefix,
            "--file",
            filepath,
        ],
        suppress_stdout=not stdout,
    )


def import_env(env_file: Path, is_forcing: bool = False, stdout: bool = False) -> None:
    """Import an environment from a conda environment file."""
    conda_exe = ensure_conda()
    force_args = ["--force"] if is_forcing else []
    env_name = env_file.stem
    prefix = conda_env_prefix(env_name)
    _subprocess_run(
        [
            conda_exe,
            "env",
            "create",
            *force_args,
            "--prefix",
            prefix,
            "--file",
            env_file,
        ],
        suppress_stdout=not stdout,
    )
