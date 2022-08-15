import logging
import subprocess
import rainbowlog
import yaml
from statistics import median
from typing import Any, Callable, Mapping, Optional, Sequence
from pathlib import Path
from functools import wraps

from condax import consts
from condax.condax import Condax
from condax.conda import Conda

import click

from condax.utils import FullPath


def common(f: Callable) -> Callable:
    """
    This decorator adds common options to the CLI.
    """
    options: Sequence[Callable] = (
        condax,
        click.help_option("-h", "--help"),
    )

    for op in options:
        f = op(f)

    return f


packages = click.argument("packages", nargs=-1, required=True)


def _config_file_callback(_, __, config_file: Path) -> Mapping[str, Any]:
    try:
        with (config_file or consts.DEFAULT_PATHS.conf_file).open() as cf:
            config = yaml.safe_load(cf) or {}
    except FileNotFoundError:
        config = {}

    if not isinstance(config, dict):
        raise click.BadParameter(
            f"Config file {config_file} must contain a dict as its root."
        )

    return config


config = click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help=f"Custom path to a condax config file in YAML. Default: {consts.DEFAULT_PATHS.conf_file}",
    callback=_config_file_callback,
)

channels = click.option(
    "--channel",
    "-c",
    "channels",
    multiple=True,
    help="Use the channels specified in addition to those in the configuration files of condax, conda, and/or mamba.",
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

bin_dir = click.option(
    "-b",
    "--bin-dir",
    type=click.Path(exists=True, path_type=Path),
    help=f"Custom path to the condax bin directory. Default: {consts.DEFAULT_PATHS.bin_dir}",
)


def conda(f: Callable) -> Callable:
    """
    This click option decorator adds the --channel and --config options as well as all those added by `options.log_level` to the CLI.
    It constructs a `Conda` object and passes it to the decorated function as `conda`.
    It reads the config file and passes it as a dict to the decorated function as `config`.
    """

    @log_level
    @config
    @wraps(f)
    def construct_conda_hook(config: Mapping[str, Any], log_level: int, **kwargs):
        return f(
            conda=Conda(
                config.get("channels", []),
                stdout=subprocess.DEVNULL if log_level >= logging.INFO else None,
                stderr=subprocess.DEVNULL if log_level >= logging.CRITICAL else None,
            ),
            config=config,
            log_level=log_level,
            **kwargs,
        )

    return construct_conda_hook


def condax(f: Callable) -> Callable:
    """
    This click option decorator adds the --bin-dir option as well as all those added by `options.conda` to the CLI.
    It then constructs a `Condax` object and passes it to the decorated function as `condax`.
    """

    @conda
    @bin_dir
    @wraps(f)
    def construct_condax_hook(
        conda: Conda, config: Mapping[str, Any], bin_dir: Optional[Path], **kwargs
    ):
        return f(
            condax=Condax(
                conda,
                bin_dir
                or config.get("bin_dir", None)
                or config.get("target_destination", None)  # Compatibility <=0.0.5
                or consts.DEFAULT_PATHS.bin_dir,
                FullPath(
                    config.get("prefix_dir", None)
                    or config.get("prefix_path", None)  # Compatibility <=0.0.5
                    or consts.DEFAULT_PATHS.prefix_dir
                ),
            ),
            **kwargs,
        )

    return construct_condax_hook


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
