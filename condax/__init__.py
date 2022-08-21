import sys


if sys.version_info >= (3, 8):
    import importlib.metadata as _metadata
else:
    import importlib_metadata as _metadata

__version__ = _metadata.version(__package__)
