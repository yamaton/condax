from typing import List
from condax.condax import Condax

from . import cli, options


@cli.command(
    help="""
    Remove a package.

    This will remove a package installed with condax and destroy the underlying
    conda environment.
    """,
    aliases=["uninstall"],
)
@options.common
@options.packages
def remove(packages: List[str], condax: Condax, **_):
    for pkg in packages:
        condax.remove_package(pkg)
