from pathlib import Path
from condax.exceptions import CondaxError


class BadMetadataError(CondaxError):
    def __init__(self, metadata_path: Path, msg: str):
        super().__init__(
            301, f"Error loading condax metadata at {metadata_path}: {msg}"
        )


class NoMetadataError(CondaxError):
    def __init__(self, prefix: Path):
        super().__init__(302, f"Failed to recreate condax_metadata.json in {prefix}")
