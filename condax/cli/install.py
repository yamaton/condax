import logging
from typing import List

import click

import condax.config as config
import condax.core as core
from condax import __version__

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
@options.common
@options.packages
def install(
    packages: List[str],
    is_forcing: bool,
    log_level: int,
    **_,
):
    for pkg in packages:
        core.install_package(
            pkg, is_forcing=is_forcing, conda_stdout=log_level <= logging.INFO
        )
