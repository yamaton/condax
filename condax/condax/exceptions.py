from pathlib import Path
from condax.exceptions import CondaxError


class PackageInstalledError(CondaxError):
    def __init__(self, package: str, location: Path):
        super().__init__(
            101,
            f"Package `{package}` is already installed at {location / package}. Use `--force` to overwrite.",
        )


class NotAnEnvError(CondaxError):
    def __init__(self, location: Path, msg: str = ""):
        super().__init__(
            102,
            f"{location} exists, is not empty, and is not a conda environment. {msg}",
        )


class PackageNotInstalled(CondaxError):
    def __init__(self, package: str):
        super().__init__(103, f"Package `{package}` is not installed with condax")
