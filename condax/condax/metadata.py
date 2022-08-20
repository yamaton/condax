from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Type, TypeVar

from condax.conda import env_info
from condax.condax.exceptions import BadMetadataError
from condax.utils import FullPath


def create_metadata(env: Path, package: str, executables: Iterable[Path]):
    """
    Create metadata file
    """
    apps = [p.name for p in (executables or env_info.find_exes(env, package))]
    main = MainPackage(package, env, apps)
    meta = CondaxMetaData(main)
    meta.save()


S = TypeVar("S", bound="Serializable")


class Serializable(ABC):
    @classmethod
    @abstractmethod
    def deserialize(cls: Type[S], serialized: Dict[str, Any]) -> S:
        raise NotImplementedError()

    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        raise NotImplementedError()


class _PackageBase(Serializable):
    def __init__(self, name: str, apps: Iterable[str], include_apps: bool):
        self.name = name
        self.apps = set(apps)
        self.include_apps = include_apps

    def __lt__(self, other):
        return self.name < other.name

    def serialize(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "apps": list(self.apps),
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


class CondaxMetaData(Serializable):
    """
    Handle metadata information written in `condax_metadata.json`
    placed in each environment.
    """

    metadata_file = "condax_metadata.json"

    def __init__(
        self,
        main_package: MainPackage,
        injected_packages: Iterable[InjectedPackage] = (),
    ):
        self.main_package = main_package
        self.injected_packages = {pkg.name: pkg for pkg in injected_packages}

    def inject(self, package: InjectedPackage):
        self.injected_packages[package.name] = package

    def uninject(self, name: str):
        self.injected_packages.pop(name, None)

    def serialize(self) -> Dict[str, Any]:
        return {
            "main_package": self.main_package.serialize(),
            "injected_packages": [
                pkg.serialize() for pkg in self.injected_packages.values()
            ],
        }

    @classmethod
    def deserialize(cls, serialized: Dict[str, Any]):
        assert isinstance(serialized, dict)
        assert isinstance(serialized["main_package"], dict)
        assert isinstance(serialized["injected_packages"], list)
        serialized.update(
            main_package=MainPackage.deserialize(serialized["main_package"]),
            injected_packages=[
                InjectedPackage.deserialize(pkg)
                for pkg in serialized["injected_packages"]
            ],
        )
        return cls(**serialized)

    def save(self) -> None:
        metadata_path = self.main_package.prefix / self.metadata_file
        with metadata_path.open("w") as f:
            json.dump(self.serialize(), f, indent=4)


def load(prefix: Path) -> Optional[CondaxMetaData]:
    p = prefix / CondaxMetaData.metadata_file
    if not p.exists():
        return None

    with open(p) as f:
        d = json.load(f)

    try:
        return CondaxMetaData.deserialize(d)
    except AssertionError as e:
        raise BadMetadataError(p, f"A value is of the wrong type. {e}") from e
    except KeyError as e:
        raise BadMetadataError(p, f"Key {e} is missing.") from e
