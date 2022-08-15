import logging
from typing import Iterable, List

from condax import __version__, consts, core
from condax.condax import Condax

from . import cli, options


@cli.command(
    help=f"""
    Install a package with condax.

    This will install a package into a new conda environment and link the executable
    provided by it to `{consts.DEFAULT_PATHS.bin_dir}`.
    """
)
@options.channels
@options.is_forcing
@options.common
@options.packages
def install(
    packages: List[str],
    is_forcing: bool,
    channels: Iterable[str],
    condax: Condax,
    **_,
):
    for pkg in packages:
        condax.install_package(
            pkg,
            is_forcing=is_forcing,
            channels=channels,
        )
