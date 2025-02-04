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
from condax.constants import EXCLUCDED_FILE_EXTENSIONS
from condax.exceptions import CondaxError
from condax.utils import to_path
import condax.utils as utils


logger = logging.getLogger(__name__)


def _ensure(execs: Iterable[str], installer: Callable[[], Path]) -> Path:
    for exe in execs:
        exe_path = shutil.which(exe)
        if exe_path is not None:
            return to_path(exe_path)

    logger.info("No existing conda installation found. Installing the standalone")
    return installer()


def ensure_conda() -> Path:
    return _ensure(("mamba", "conda"), setup_conda)


def ensure_micromamba() -> Path:
    return _ensure(("micromamba",), setup_micromamba)


def setup_conda() -> Path:
    url = utils.get_conda_url()
    resp = requests.get(url, allow_redirects=True)
    resp.raise_for_status()
    utils.mkdir(C.bin_dir())
    exe_name = "conda.exe" if os.name == "nt" else "conda"
    target_filename = C.bin_dir() / exe_name
    with open(target_filename, "wb") as fo:
        fo.write(resp.content)
    st = os.stat(target_filename)
    os.chmod(target_filename, st.st_mode | stat.S_IXUSR)
    return target_filename


def setup_micromamba() -> Path:
    utils.mkdir(C.bin_dir())
    exe_name = "micromamba.exe" if os.name == "nt" else "micromamba"
    umamba_exe = C.bin_dir() / exe_name
    _download_extract_micromamba(umamba_exe)
    return umamba_exe


def _download_extract_micromamba(umamba_dst: Path) -> None:
    url = utils.get_micromamba_url()
    print(f"Downloading micromamba from {url}")
    response = requests.get(url, allow_redirects=True)
    response.raise_for_status()

    utils.mkdir(umamba_dst.parent)
    tarfile_obj = io.BytesIO(response.content)
    with tarfile.open(fileobj=tarfile_obj) as tar, open(umamba_dst, "wb") as f:
        p = "Library/bin/micromamba.exe" if os.name == "nt" else "bin/micromamba"
        extracted = tar.extractfile(p)
        if extracted:
            shutil.copyfileobj(extracted, f)

    st = os.stat(umamba_dst)
    os.chmod(umamba_dst, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


## Need to activate if using micromamba as drop-in replacement
# def _activate_umamba(umamba_path: Path) -> None:
#     print("Activating micromamba")
#     _subprocess_run(
#         f'eval "$({umamba_path} shell hook --shell posix --prefix {C.mamba_root_prefix()})"',
#         shell=True,
#     )


def create_conda_environment(spec: str, stdout: bool) -> None:
    """Create an environment by installing a package.

    NOTE: `spec` may contain version specificaitons.
    """
    conda_exe = ensure_conda()
    prefix = conda_env_prefix(spec)

    channels = C.channels()
    channels_args = [x for c in channels for x in ["--channel", c]]

    _subprocess_run(
        [
            conda_exe,
            "create",
            "--prefix",
            prefix,
            "--override-channels",
            *channels_args,
            "--quiet",
            "--yes",
            shlex.quote(spec),
        ],
        suppress_stdout=not stdout,
    )


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


def remove_conda_env(package: str, stdout: bool) -> None:
    """Remove a conda environment."""
    conda_exe = ensure_conda()

    _subprocess_run(
        [conda_exe, "remove", "--prefix", conda_env_prefix(package), "--all", "--yes"],
        suppress_stdout=not stdout,
    )


def update_conda_env(spec: str, update_specs: bool, stdout: bool) -> None:
    """Update packages in an environment.

    NOTE: More controls of package updates might be needed.
    """
    _, match_spec = utils.split_match_specs(spec)
    conda_exe = ensure_conda()
    prefix = conda_env_prefix(spec)
    channels_args = [x for c in C.channels() for x in ["--channel", c]]
    update_specs_args = ["--update-specs"] if update_specs else []
    # NOTE: `conda update` does not support version specification.
    # It suggets to use `conda install` instead.
    args: Iterable[str]
    if conda_exe.name == "conda" and match_spec:
        subcmd = "install"
        args = (shlex.quote(spec),)
    elif match_spec:
        subcmd = "update"
        args = (*update_specs_args, shlex.quote(spec))
    else:
        ## FIXME: this update process is inflexible
        subcmd = "update"
        args = (*update_specs_args, "--all")

    command: List[Union[Path, str]] = [
        conda_exe,
        subcmd,
        "--prefix",
        prefix,
        "--override-channels",
        "--quiet",
        "--yes",
        *channels_args,
        *args,
    ]

    _subprocess_run(command, suppress_stdout=not stdout)


def has_conda_env(package: str) -> bool:
    # TODO: check some properties of a conda environment
    p = conda_env_prefix(package)
    return p.exists() and p.is_dir()


def conda_env_prefix(spec: str) -> Path:
    package, _ = utils.split_match_specs(spec)
    return C.prefix_dir() / package


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


class DeterminePkgFilesError(CondaxError):
    def __init__(self, package: str):
        super().__init__(40, f"Could not determine package files: {package}.")


def determine_executables_from_env(
    package: str, injected_package: Optional[str] = None
) -> List[Path]:
    def is_good(p: Union[str, Path]) -> bool:
        p = to_path(p)
        res = (p.parent.name in ("bin", "sbin", "scripts", "Scripts")) and (
            p.suffix not in EXCLUCDED_FILE_EXTENSIONS
        ) and (
            not p.name.startswith(".") and not p.name.startswith("_")
        )
        return res

    env_prefix = conda_env_prefix(package)
    target_name = injected_package if injected_package else package

    conda_meta_dir = env_prefix / "conda-meta"
    for file_name in conda_meta_dir.glob(f"{target_name}*.json"):
        with file_name.open() as fo:
            package_info = json.load(fo)
            if package_info["name"] == target_name:
                potential_executables: Set[str] = {
                    fn
                    for fn in package_info["files"]
                    if (fn.startswith("bin/") and is_good(fn))
                    or (fn.startswith("sbin/") and is_good(fn))
                    # They are Windows style path
                    or (fn.lower().startswith("scripts") and is_good(fn))
                    or (fn.lower().startswith("library") and is_good(fn))
                }
                break
    else:
        raise DeterminePkgFilesError(target_name)

    return sorted(
        env_prefix / fn
        for fn in potential_executables
        if utils.is_executable(env_prefix / fn)
    )


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
    return [to_path(p) for p in d["pkgs_dirs"]]


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


def import_env(
    env_file: Path,
    is_forcing: bool = False,
    stdout: bool = False,
    env_name: Optional[str] = None,
) -> None:
    """Import an environment from a conda environment file."""
    conda_exe = ensure_conda()
    force_args = ["--force"] if is_forcing else []
    if env_name is None:
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


def mamba_clean_all(stdout: bool = False) -> None:
    """Run `mamba clean --all`."""
    conda_exe = ensure_conda()
    _subprocess_run(
        [
            conda_exe,
            "clean",
            "--all",
            "--yes",
        ],
        suppress_stdout=not stdout,
    )
