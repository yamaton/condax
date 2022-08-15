import logging
import rainbowlog
from statistics import median
from typing import Callable, Sequence
from pathlib import Path
from functools import wraps

from condax import config

import click


def common(f: Callable) -> Callable:
    """
    This decorator adds common options to the CLI.
    """
    options: Sequence[Callable] = (
        config_file,
        log_level,
        click.help_option("-h", "--help"),
    )

    for op in options:
        f = op(f)

    return f


packages = click.argument("packages", nargs=-1, required=True)

config_file = click.option(
    "--config",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    help=f"Custom path to a condax config file in YAML. Default: {config.DEFAULT_CONFIG}",
    callback=lambda _, __, f: (f and config.set_via_file(f)) or f,
)

channels = click.option(
    "--channel",
    "-c",
    "channels",
    multiple=True,
    help=f"""Use the channels specified to install. If not specified condax will
    default to using {config.DEFAULT_CHANNELS}, or 'channels' in the config file.""",
    callback=lambda _, __, c: (c and config.set_via_value(channels=c)) or c,
)

envname = click.option(
    "--name",
    "-n",
    "envname",
    required=True,
    prompt="Specify the environment (Run `condax list --short` to see available ones)",
    type=str,
    help=f"""Specify existing environment to inject into.""",
    callback=lambda _, __, n: n.strip(),
)

is_forcing = click.option(
    "-f",
    "--force",
    "is_forcing",
    help="""Modify existing environment and files in CONDAX_BIN_DIR.""",
    is_flag=True,
    default=False,
)

verbose = click.option(
    "-v",
    "--verbose",
    count=True,
    help="Raise verbosity level.",
)

quiet = click.option(
    "-q",
    "--quiet",
    count=True,
    help="Decrease verbosity level.",
)


def log_level(f: Callable) -> Callable:
    """
    This click option decorator adds -v and -q options to the CLI, then sets up logging with the specified level.
    It passes the level to the decorated function as `log_level`.
    """

    @verbose
    @quiet
    @wraps(f)
    def setup_logging_hook(verbose: int, quiet: int, **kwargs):
        handler = logging.StreamHandler()
        logger = logging.getLogger((__package__ or __name__).split(".", 1)[0])
        handler.setFormatter(rainbowlog.Formatter(logging.Formatter()))
        logger.addHandler(handler)
        level = int(
            median(
                (logging.DEBUG, logging.INFO - 10 * (verbose - quiet), logging.CRITICAL)
            )
        )
        logger.setLevel(level)
        return f(log_level=level, **kwargs)

    return setup_logging_hook
