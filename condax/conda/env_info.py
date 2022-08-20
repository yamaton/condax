import json
from pathlib import Path
from typing import List, Union, Set

from condax.utils import FullPath
from condax import utils
from .exceptions import NoPackageMetadata


def is_env(path: Path) -> bool:
    return (path / "conda-meta").is_dir()


def find_exes(prefix: Path, package: str) -> List[Path]:
    """Find executables in environment `prefix` provided py a given `package`.

    Args:
        prefix: The environment to search in.
        package: The package whose executables to search for.

    Returns:
        A list of executables in `prefix` provided by `package`.

    Raises:
        DeterminePkgFilesError: If the package files could not be determined.
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
        raise NoPackageMetadata(package)

    return sorted(
        prefix / fn for fn in potential_executables if utils.is_executable(prefix / fn)
    )
