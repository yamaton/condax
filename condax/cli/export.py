import logging
import click

import condax.core as core
from condax import __version__

from . import cli, options


@cli.command(
    help="""
    [experimental] Export all environments installed by condax.
    """
)
@click.option(
    "--dir",
    default="condax_exported",
    help="Set directory to export to.",
)
@options.common
def export(dir: str, log_level: int, **_):
    core.export_all_environments(dir, conda_stdout=log_level <= logging.INFO)


@cli.command(
    "import",
    help="""
    [experimental] Import condax environments.
    """,
)
@options.is_forcing
@options.common
@click.argument(
    "directory",
    required=True,
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
)
def run_import(directory: str, is_forcing: bool, log_level: int, **_):
    core.import_environments(
        directory, is_forcing, conda_stdout=log_level <= logging.INFO
    )
