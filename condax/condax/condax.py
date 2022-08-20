from pathlib import Path
from typing import Iterable
import logging

from condax import utils
from condax.conda import Conda, env_info
from .exceptions import PackageInstalledError, NotAnEnvError

from . import links
from .metadata import metadata

logger = logging.getLogger(__name__)


class Condax:
    def __init__(self, conda: Conda, bin_dir: Path, prefix_dir: Path) -> None:
        """
        Args:
            conda: A conda object to use for executing conda commands.
            bin_dir: The directory to make executables available in.
            prefix_dir: The directory where to create new conda environments.
        """
        self.conda = conda
        self.bin_dir = bin_dir
        self.prefix_dir = prefix_dir

    def install_package(
        self,
        spec: str,
        channels: Iterable[str],
        is_forcing: bool = False,
    ):
        """Create a new conda environment with the package provided by `spec` and make all its executables available in `self.bin_dir`.

        Args:
            spec: The package to install. Can have version constraints.
            channels: Additional channels to search for packages in.
            is_forcing: If True, install even if the package is already installed.
        """
        package = utils.package_name(spec)
        env = self.prefix_dir / package

        if env_info.is_env(env):
            if is_forcing:
                logger.warning(f"Overwriting environment for {package}")
                self.conda.remove_env(env)
            else:
                raise PackageInstalledError(package, env)
        elif env.exists() and (not env.is_dir() or tuple(env.iterdir())):
            raise NotAnEnvError(env, "Cannot install to this location")

        self.conda.create_env(env, spec, channels)
        executables = env_info.find_exes(env, package)
        utils.mkdir(self.bin_dir)
        links.create_links(env, executables, self.bin_dir, is_forcing=is_forcing)
        metadata.create_metadata(env, package, executables)
        logger.info(f"`{package}` has been installed by condax")

    def remove_package(self, package: str):
        env = self.prefix_dir / package
        if not env_info.is_env(env):
            logger.warning(f"{package} is not installed with condax")
            return

        apps_to_unlink = metadata.load(env).apps
        links.remove_links(package, self.bin_dir, apps_to_unlink)
        self.conda.remove_env(env)
        logger.info(f"`{package}` has been removed from condax")
