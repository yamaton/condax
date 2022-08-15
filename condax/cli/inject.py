import logging
from typing import List
import click

import condax.core as core
from condax import __version__

from . import cli, options


@cli.command(
    help="""
    Inject a package to existing environment created by condax.
    """
)
@options.channels
@options.envname
@options.is_forcing
@click.option(
    "--include-apps",
    help="""Make apps from the injected package available.""",
    is_flag=True,
    default=False,
)
@options.common
@options.packages
def inject(
    packages: List[str],
    envname: str,
    is_forcing: bool,
    include_apps: bool,
    log_level: int,
    **_,
):
    core.inject_package_to(
        envname,
        packages,
        is_forcing=is_forcing,
        include_apps=include_apps,
        conda_stdout=log_level <= logging.INFO,
    )


@cli.command(
    help="""
    Uninject a package from an existing environment.
    """
)
@options.envname
@options.common
@options.packages
def uninject(packages: List[str], envname: str, log_level: int, **_):
    core.uninject_package_from(envname, packages, log_level <= logging.INFO)
