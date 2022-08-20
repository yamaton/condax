import itertools
from pathlib import Path
import shlex
import subprocess
import logging
import sys
from typing import IO, Iterable, Optional
from halo import Halo

from condax import consts
from .installers import ensure_conda


logger = logging.getLogger(__name__)


class Conda:
    def __init__(self, channels: Iterable[str]) -> None:
        """This class is a wrapper for conda's CLI.

        Args:
            channels: Additional channels to use.
        """
        self.channels = tuple(channels)
        self.exe = ensure_conda(consts.DEFAULT_PATHS.bin_dir)

    def remove_env(self, env: Path) -> None:
        """Remove a conda environment.

        Args:
            env: The path to the environment to remove.
        """
        self._run(
            f"env remove --prefix {env} --yes",
            stdout_level=logging.DEBUG,
            stderr_level=logging.INFO,
        )

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
        cmd = f"create --prefix {prefix} {' '.join(f'--channel {c}' for c in itertools.chain(extra_channels, self.channels))} --quiet --yes {shlex.quote(spec)}"
        if logger.getEffectiveLevel() <= logging.INFO:
            with Halo(
                text=f"Creating environment for {spec}",
                spinner="dots",
                stream=sys.stderr,
            ):
                self._run(cmd)
        else:
            self._run(cmd)

    def _run(
        self,
        command: str,
        stdout_level: int = logging.DEBUG,
        stderr_level: int = logging.ERROR,
    ) -> subprocess.CompletedProcess:
        """Run a conda command.

        Args:
            command: The command to run excluding the conda executable.
        """
        cmd = f"{self.exe} {command}"
        logger.debug(f"Running: {cmd}")
        cmd_list = shlex.split(cmd)

        p = subprocess.Popen(
            cmd_list, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout_done, stderr_done = False, False
        while not stdout_done or not stderr_done:
            stdout_done = self._log_stream(p.stdout, stdout_level)
            stderr_done = self._log_stream(p.stderr, stderr_level)

        ret_code = p.wait()

        return subprocess.CompletedProcess(
            cmd_list,
            ret_code,
            p.stdout.read() if p.stdout else None,
            p.stderr.read() if p.stderr else None,
        )

    def _log_stream(self, stream: Optional[IO[str]], log_level: int) -> bool:
        """Log one line of process ouput.

        Args:
            stream: The stream to read from.
            log_level: The log level to use.

        Returns:
            True if the stream is depleted. False otherwise.
        """
        if stream is None:
            return True
        line = stream.readline()
        if line:
            logger.log(log_level, f"\r{line.rstrip()}")
        return not line
