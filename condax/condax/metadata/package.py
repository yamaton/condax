from pathlib import Path
from typing import Any, Dict, Iterable, Set

from condax.utils import FullPath
from .serializable import Serializable


class _PackageBase(Serializable):
    def __init__(self, name: str, apps: Iterable[str], include_apps: bool):
        self.name = name
        self._apps = set(apps)
        self.include_apps = include_apps

    @property
    def apps(self) -> Set[str]:
        """The executable apps provided by the package."""
        return self._apps

    def __lt__(self, other):
        return self.name < other.name

    def serialize(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "apps": list(self._apps),
            "include_apps": self.include_apps,
        }

    @classmethod
    def deserialize(cls, serialized: Dict[str, Any]):
        assert isinstance(serialized, dict)
        assert isinstance(serialized["name"], str)
        assert isinstance(serialized["apps"], list)
        assert all(isinstance(app, str) for app in serialized["apps"])
        assert isinstance(serialized["include_apps"], bool)
        serialized.update(apps=set(serialized["apps"]))
        return cls(**serialized)


class MainPackage(_PackageBase):
    def __init__(
        self, name: str, prefix: Path, apps: Iterable[str], include_apps: bool = True
    ):
        super().__init__(name, apps, include_apps)
        self.prefix = prefix

    def serialize(self) -> Dict[str, Any]:
        return {
            **super().serialize(),
            "prefix": str(self.prefix),
        }

    @classmethod
    def deserialize(cls, serialized: Dict[str, Any]):
        assert isinstance(serialized["prefix"], str)
        serialized.update(prefix=FullPath(serialized["prefix"]))
        return super().deserialize(serialized)


class InjectedPackage(_PackageBase):
    pass
