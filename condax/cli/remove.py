import logging
from typing import List
from condax.condax import Condax

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
def remove(packages: List[str], condax: Condax, **_):
    for pkg in packages:
        condax.remove_package(pkg)


@cli.command(
    help="""
    Alias for condax remove.
    """
)
@options.common
@options.packages
def uninstall(packages: List[str], **_):
    remove(packages)
