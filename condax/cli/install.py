import logging
from pathlib import Path
from typing import List, Optional

import click

import condax.config as config
import condax.core as core

from . import cli, options


@cli.command(
    help=f"""
    Install a package with condax.

    This will install a package into a new conda environment and link the executable
    provided by it to `{config.DEFAULT_BIN_DIR}`.
    """
)
@options.channels
@options.is_forcing
@click.option(
    "--file",
    "envfile",
    type=click.Path(exists=True, path_type=Path),
    help=f"Specify Conda environment file in YAML.",
    default=None,
)
@options.common
@options.packages
def install(
    packages: List[str],
    is_forcing: bool,
    log_level: int,
    envfile: Optional[Path],
    **_,
) -> None:

    if envfile:
        core.install_via_env_file(
            envfile,
            packages,
            is_forcing=is_forcing,
            conda_stdout=log_level <= logging.INFO,
        )

        return

    for pkg in packages:
        core.install_package(
            pkg, is_forcing=is_forcing, conda_stdout=log_level <= logging.INFO
        )
