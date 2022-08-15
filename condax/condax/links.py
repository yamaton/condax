import logging
import os
from pathlib import Path
import shutil
from typing import Iterable

from condax.conda import installers
from condax import utils

logger = logging.getLogger(__name__)


def create_links(
    env: Path,
    executables_to_link: Iterable[Path],
    location: Path,
    is_forcing: bool = False,
):
    """Create links to the executables in `executables_to_link` in `bin_dir`.

    Args:
        env: The conda environment to link executables from.
        executables_to_link: The executables to link.
        location: The location to put the links in.
        is_forcing: If True, overwrite existing links.
    """
    linked = (
        exe.name
        for exe in sorted(executables_to_link)
        if create_link(env, exe, location, is_forcing=is_forcing)
    )
    if executables_to_link:
        logger.info("\n  - ".join(("Created the following entrypoint links:", *linked)))


def create_link(env: Path, exe: Path, location: Path, is_forcing: bool = False) -> bool:
    """Create a link to the executable in `exe` in `bin_dir`.

    Args:
        env: The conda environment to link executables from.
        exe: The executable to link.
        location: The location to put the link in.
        is_forcing: If True, overwrite existing links.

    Returns:
        bool: True if a link was created, False otherwise.
    """
    micromamba_exe = installers.ensure_micromamba()
    if os.name == "nt":
        script_lines = [
            "@rem Entrypoint created by condax\n",
            f"@call {utils.quote(micromamba_exe)} run --prefix {utils.quote(env)} {utils.quote(exe)} %*\n",
        ]
    else:
        script_lines = [
            "#!/usr/bin/env bash\n",
            "\n",
            "# Entrypoint created by condax\n",
            f'{utils.quote(micromamba_exe)} run --prefix {utils.quote(env)} {utils.quote(exe)} "$@"\n',
        ]
        if utils.to_bool(os.environ.get("CONDAX_HIDE_EXITCODE", False)):
            # Let scripts to return exit code 0 constantly
            script_lines.append("exit 0\n")

    script_path = location / _get_wrapper_name(exe.name)
    if script_path.exists() and not is_forcing:
        answer = input(f"{exe.name} already exists. Overwrite? (y/N) ").strip().lower()
        if answer not in ("y", "yes"):
            logger.warning(f"Skipped creating entrypoint: {exe.name}")
            return False

    if script_path.exists():
        logger.warning(f"Overwriting entrypoint: {exe.name}")
        utils.unlink(script_path)
    with open(script_path, "w") as fo:
        fo.writelines(script_lines)
    shutil.copystat(exe, script_path)
    return True


def _get_wrapper_name(name: str) -> str:
    """Get the file name of the entrypoint script for the executable with the given name.

    On Windows, the file name is the executable name with a .bat extension.
    On Unix, the file name is unchanged.
    """
    return f"{Path(name).stem}.bat" if os.name == "nt" else name
