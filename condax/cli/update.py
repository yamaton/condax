from typing import List

import click

import condax.core as core
from condax.condax import Condax

from . import cli, options


@cli.command(
    help="""
    Update package(s) installed by condax.

    This will update the underlying conda environments(s) to the latest release of a package.
    """
)
@click.option(
    "--all", is_flag=True, help="Set to update all packages installed by condax."
)
@click.option(
    "--update-specs", is_flag=True, help="Update based on provided specifications."
)
@options.common
@options.is_forcing
@options.channels
@click.argument("packages", required=False, nargs=-1)
def update(
    condax: Condax,
    packages: List[str],
    all: bool,
    update_specs: bool,
    is_forcing: bool,
    channels: List[str],
    **_
):

    if not (all or packages):
        raise click.BadArgumentUsage(
            "No packages specified. To update all packages use --all."
        )

    if all and packages:
        raise click.BadArgumentUsage("Cannot specify packages and --all.")

    if all:
        condax.update_all_packages(channels, is_forcing)
    else:
        for pkg in packages:
            condax.update_package(pkg, channels, update_specs, is_forcing)
