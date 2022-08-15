import logging
from typing import List
import click

import condax.core as core
from condax import __version__

from . import cli, options


@cli.command(
    help="""
    Remove a package.

    This will remove a package installed with condax and destroy the underlying
    conda environment.
    """
)
@options.common
@options.packages
def remove(packages: List[str], log_level: int, **_):
    for pkg in packages:
        core.remove_package(pkg, conda_stdout=log_level <= logging.INFO)


@cli.command(
    help="""
    Alias for condax remove.
    """
)
@options.common
@options.packages
def uninstall(packages: List[str], **_):
    remove(packages)
