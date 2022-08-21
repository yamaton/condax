from pathlib import Path
from typing import Iterable, Set
import logging

from condax import utils
from condax.conda import Conda, env_info, exceptions as conda_exceptions
from .exceptions import PackageInstalledError, NotAnEnvError, PackageNotInstalled

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
        metadata.create(env, package, executables)
        logger.info(f"`{package}` has been installed by condax")

    def remove_package(self, package: str):
        env = self.prefix_dir / package
        if not env_info.is_env(env):
            logger.warning(f"{package} is not installed with condax")
            return

        apps_to_unlink = metadata.load(env).apps
        links.remove_links(env, apps_to_unlink, self.bin_dir)
        self.conda.remove_env(env)
        logger.info(f"`{package}` has been removed from condax")

    def update_all_packages(
        self, channels: Iterable[str] = (), is_forcing: bool = False
    ):
        for env in env_info.find_envs(self.prefix_dir):
            self.update_package(env.name, channels, is_forcing=is_forcing)

    def update_package(
        self,
        spec: str,
        channels: Iterable[str] = (),
        update_specs: bool = False,
        is_forcing: bool = False,
    ) -> None:
        pkg_name = utils.package_name(spec)
        env = self.prefix_dir / pkg_name
        meta = metadata.load(env)

        if not env_info.is_env(env):
            raise PackageNotInstalled(pkg_name)

        try:
            exes_before = self._find_all_exes(env, meta)
            self.conda.update_env(env, spec, update_specs, channels)
            exes_after = self._find_all_exes(env, meta)

            to_create = exes_after - exes_before
            to_remove = exes_before - exes_after

            links.create_links(env, to_create, self.bin_dir, is_forcing)
            links.remove_links(env, (exe.name for exe in to_remove), self.bin_dir)

            logger.info(f"{pkg_name} updated successfully")

        except conda_exceptions.CondaCommandError as e:
            logger.error(str(e))
            logger.error(f"Failed to update `{env}`")
            logger.warning(f"Recreating the environment...")

            self.remove_package(pkg_name)
            self.install_package(spec, channels, is_forcing=is_forcing)
            for pkg in meta.injected_packages:
                self.inject_package(pkg.name, env, is_forcing=is_forcing)

        # Update metadata file
        metadata.create(env)
        for pkg in meta.injected_packages:
            metadata.inject(env, (pkg.name,), pkg.include_apps)

    def _find_all_exes(self, env: Path, meta: metadata.CondaxMetaData) -> Set[Path]:
        """Get exes of main and injected packages in env directory (not in self.bin_dir)"""
        return {
            utils.FullPath(exe)
            for exe in env_info.find_exes(env, meta.main_package.name).union(
                *(
                    env_info.find_exes(env, injected.name)
                    for injected in meta.injected_packages
                )
            )
        }
