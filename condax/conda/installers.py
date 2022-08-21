import io
import shutil
import logging
import tarfile
import requests
import os
import stat
from functools import partial
from pathlib import Path
from typing import Callable, Iterable

from condax.utils import FullPath
from condax import utils, consts

logger = logging.getLogger(__name__)


DEFAULT_CONDA_BINS_DIR = consts.DEFAULT_PATHS.data_dir / "bins"


def _ensure(execs: Iterable[str], installer: Callable[[], Path]) -> Path:
    path = os.pathsep.join((os.environ.get("PATH", ""), str(DEFAULT_CONDA_BINS_DIR)))
    for exe in execs:
        exe_path = shutil.which(exe, path=path)
        if exe_path is not None:
            return FullPath(exe_path)

    logger.info("No existing conda installation found. Installing the standalone")
    return installer()


def ensure_conda(bin_dir: Path = DEFAULT_CONDA_BINS_DIR) -> Path:
    return _ensure(("conda", "mamba"), partial(install_conda, bin_dir))


def ensure_micromamba(bin_dir: Path = DEFAULT_CONDA_BINS_DIR) -> Path:
    return _ensure(("micromamba",), partial(install_micromamba, bin_dir))


def install_conda(bin_dir: Path = DEFAULT_CONDA_BINS_DIR) -> Path:
    url = utils.get_conda_url()
    resp = requests.get(url, allow_redirects=True)
    resp.raise_for_status()
    utils.mkdir(bin_dir)
    exe_name = "conda.exe" if os.name == "nt" else "conda"
    target_filename = bin_dir / exe_name
    with open(target_filename, "wb") as fo:
        fo.write(resp.content)
    st = os.stat(target_filename)
    os.chmod(target_filename, st.st_mode | stat.S_IXUSR)
    return target_filename


def install_micromamba(bin_dir: Path = DEFAULT_CONDA_BINS_DIR) -> Path:
    utils.mkdir(bin_dir)
    exe_name = "micromamba.exe" if os.name == "nt" else "micromamba"
    umamba_exe = bin_dir / exe_name
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
