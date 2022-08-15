import condax.config as config
import condax.paths as paths
from condax import __version__

from . import cli, options


@cli.command(
    help="""
    Ensure the condax links directory is on $PATH.
    """
)
@options.common
def ensure_path(**_):
    paths.add_path_to_environment(config.C.bin_dir())
