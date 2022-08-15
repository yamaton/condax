import os
from dataclasses import dataclass
from pathlib import Path


from condax.utils import FullPath


IS_WIN = os.name == "nt"
IS_UNIX = not IS_WIN


@dataclass
class Paths:
    conf_dir: Path
    bin_dir: Path
    data_dir: Path
    conf_file_name: str = "config.yaml"
    envs_dir_name: str = "envs"

    @property
    def conf_file(self) -> Path:
        return self.conf_dir / self.conf_file_name

    @property
    def prefix_dir(self) -> Path:
        return self.data_dir / self.envs_dir_name


class _WindowsPaths(Paths):
    def __init__(self):
        conf_dir = data_dir = (
            FullPath(os.environ.get("LOCALAPPDATA", "~/AppData/Local"))
            / "condax/condax"
        )
        super().__init__(
            conf_dir=conf_dir,
            bin_dir=conf_dir / "bin",
            data_dir=data_dir,
        )


class _UnixPaths(Paths):
    def __init__(self):
        super().__init__(
            conf_dir=FullPath(os.environ.get("XDG_CONFIG_HOME", "~/.config"))
            / "condax",
            bin_dir=FullPath("~/.local/bin"),
            data_dir=FullPath(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
            / "condax",
        )


DEFAULT_PATHS: Paths = _UnixPaths() if IS_UNIX else _WindowsPaths()
