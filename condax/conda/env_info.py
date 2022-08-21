import json
from pathlib import Path
from typing import Union, Set

from condax.utils import FullPath
from condax import utils
from .exceptions import NoPackageMetadataError


def is_env(path: Path) -> bool:
    return (path / "conda-meta/history").is_file()


def find_exes(prefix: Path, package: str) -> Set[Path]:
    """Find executables in environment `prefix` provided py a given `package`.

    Args:
        prefix: The environment to search in.
        package: The package whose executables to search for.

    Returns:
        A list of executables in `prefix` provided by `package`.

    Raises:
        NoPackageMetadataError: If the package files could not be determined.
    """

    def is_exe(p: Union[str, Path]) -> bool:
        return FullPath(p).parent.name in ("bin", "sbin", "scripts", "Scripts")

    conda_meta_dir = prefix / "conda-meta"
    for file_name in conda_meta_dir.glob(f"{package}*.json"):
        with file_name.open() as fo:
            package_info = json.load(fo)
            if package_info["name"] == package:
                potential_executables: Set[str] = {
                    fn
                    for fn in package_info["files"]
                    if (fn.startswith("bin/") and is_exe(fn))
                    or (fn.startswith("sbin/") and is_exe(fn))
                    # They are Windows style path
                    or (fn.lower().startswith("scripts") and is_exe(fn))
                    or (fn.lower().startswith("library") and is_exe(fn))
                }
                break
    else:
        raise NoPackageMetadataError(package)

    return {
        prefix / fn for fn in potential_executables if utils.is_executable(prefix / fn)
    }


def find_envs(directory: Path) -> Set[Path]:
    """Find all environments in `directory`.

    Args:
        directory: The directory to search in.

    Returns:
        A list of environment prefixes in `directory`.
    """
    return {prefix for prefix in directory.iterdir() if is_env(prefix)}
