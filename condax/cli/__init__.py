import click

import condax.config as config
from condax import __version__


@click.group(
    help=f"""Install and execute applications packaged by conda.

    Default variables:

      Conda environment location is {config.DEFAULT_PREFIX_DIR}\n
      Links to apps are placed in {config.DEFAULT_BIN_DIR}
    """
)
@click.version_option(
    __version__,
    message="%(prog)s %(version)s",
)
@click.help_option("-h", "--help")
def cli(**_):
    return
