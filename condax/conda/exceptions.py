from subprocess import Popen
from condax.exceptions import CondaxError


class NoPackageMetadataError(CondaxError):
    def __init__(self, package: str):
        super().__init__(201, f"Could not determine package files: {package}.")


class CondaCommandError(CondaxError):
    def __init__(self, command: str, p: Popen[str]):
        super().__init__(
            202, f"Conda command `{command}` failed with exit code {p.returncode}."
        )
