import itertools
from pathlib import Path
import shlex
import subprocess
import logging
from typing import Iterable

from condax import consts
from .installers import ensure_conda


logger = logging.getLogger(__name__)


class Conda:
    def __init__(
        self,
        channels: Iterable[str],
        stdout=subprocess.DEVNULL,
        stderr=None,
    ) -> None:
        """This class is a wrapper for conda's CLI.

        Args:
            channels: Additional channels to use.
            stdout (optional): This is passed directly to `subprocess.run`. Defaults to subprocess.DEVNULL.
            stderr (optional): This is passed directly to `subprocess.run`. Defaults to None.
        """
        self.channels = tuple(channels)
        self.stdout = stdout
        self.stderr = stderr
        self.exe = ensure_conda(consts.DEFAULT_PATHS.bin_dir)

    @classmethod
    def is_env(cls, path: Path) -> bool:
        return (path / "conda-meta").is_dir()

    def remove_env(self, env: Path) -> None:
        """Remove a conda environment.

        Args:
            env: The path to the environment to remove.
        """
        self._run(f"remove --prefix {env} --all --yes")

    def create_env(
        self,
        prefix: Path,
        spec: str,
        extra_channels: Iterable[str] = (),
    ) -> None:
        """Create an environment by installing a package.

        NOTE: `spec` may contain version specificaitons.

        Args:
            prefix: The path to the environment to create.
            spec: Package spec to install. e.g. "python=3.6", "python>=3.6", "python", etc.
            extra_channels: Additional channels to search for packages in.
        """
        self._run(
            f"create --prefix {prefix} {' '.join(f'--channel {c}' for c in itertools.chain(extra_channels, self.channels))} --quiet --yes {shlex.quote(spec)}"
        )

    def _run(self, command: str) -> subprocess.CompletedProcess:
        """Run a conda command.

        Args:
            command: The command to run excluding the conda executable.
        """
        cmd = shlex.split(f"{self.exe} {command}")
        logger.debug(f"Running: {cmd}")
        return subprocess.run(
            cmd,
            stdout=self.stdout,
            stderr=self.stderr,
            text=True,
        )
