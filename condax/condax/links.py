import logging
import os
from pathlib import Path
import shutil
from typing import Iterable, List

from condax.conda import installers
from condax import utils, wrapper

logger = logging.getLogger(__name__)


def create_links(
    env: Path,
    executables_to_link: Iterable[Path],
    location: Path,
    is_forcing: bool = False,
):
    """Create links to the executables in `executables_to_link` in `location`.

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
    """Create a link to the executable in `exe` in `location`.

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
            f'@call "{micromamba_exe}" run --prefix "{env}" "{exe}" %*\n',
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
        answer = input(f"{exe.name} already exists in {location}. Overwrite? (y/N) ")
        if answer.strip().lower() not in ("y", "yes"):
            logger.warning(f"Skipped creating entrypoint: {exe.name}")
            return False

    if script_path.exists():
        logger.warning(f"Overwriting entrypoint: {exe.name}")
        utils.unlink(script_path)
    with open(script_path, "w") as fo:
        fo.writelines(script_lines)
    shutil.copystat(exe, script_path)
    return True


def remove_links(env: Path, executables_to_unlink: Iterable[str], location: Path):
    """Remove links in `location` which point to to executables in `env` whose names match those in `executables_to_unlink`.

    Args:
        env: The conda environment which the links must point to to be removed.
        location: The location the links are in.
        executables_to_unlink: The names of the executables to unlink.
    """
    unlinked: List[str] = []
    executables_to_unlink = tuple(executables_to_unlink)
    for executable_name in executables_to_unlink:
        link_path = location / _get_wrapper_name(executable_name)
        if os.name == "nt":
            # FIXME: this is hand-waving for now
            utils.unlink(link_path)
        else:
            wrapper_env = wrapper.read_prefix(link_path)

            if wrapper_env is None:
                utils.unlink(link_path)
                unlinked.append(f"{executable_name} \t (failed to get env)")
                continue

            if wrapper_env.samefile(env):
                logger.warning(
                    f"Keeping {executable_name} as it runs in environment `{wrapper_env}`, not `{env}`."
                )
                continue

            link_path.unlink()

        unlinked.append(executable_name)

    if executables_to_unlink:
        logger.info(
            "\n  - ".join(("Removed the following entrypoint links:", *unlinked))
        )


def _get_wrapper_name(name: str) -> str:
    """Get the file name of the entrypoint script for the executable with the given name.

    On Windows, the file name is the executable name with a .bat extension.
    On Unix, the file name is unchanged.
    """
    return f"{Path(name).stem}.bat" if os.name == "nt" else name
