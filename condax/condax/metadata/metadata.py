import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set
import logging

from condax.conda import env_info

from .package import MainPackage, InjectedPackage
from .exceptions import BadMetadataError, NoMetadataError
from .serializable import Serializable

logger = logging.getLogger(__name__)


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
        self._main_package = main_package
        self._injected_packages = {pkg.name: pkg for pkg in injected_packages}

    def inject(self, package: InjectedPackage):
        self._injected_packages[package.name] = package

    def uninject(self, name: str):
        self._injected_packages.pop(name, None)

    @property
    def apps(self) -> Set[str]:
        """All the executable apps in the condax environment, including injected ones."""
        return self._main_package._apps.union(
            *(pkg._apps for pkg in self._injected_packages.values())
        )

    @property
    def main_package(self) -> MainPackage:
        return self._main_package

    @property
    def injected_packages(self) -> Set[InjectedPackage]:
        return set(self._injected_packages.values())

    def serialize(self) -> Dict[str, Any]:
        return {
            "main_package": self._main_package.serialize(),
            "injected_packages": [
                pkg.serialize() for pkg in self._injected_packages.values()
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
        metadata_path = self._main_package.prefix / self.metadata_file
        with metadata_path.open("w") as f:
            json.dump(self.serialize(), f, indent=4)


def create(
    prefix: Path,
    package: Optional[str] = None,
    executables: Optional[Iterable[Path]] = None,
):
    """
    Create the metadata file.

    Args:
        prefix: The conda environment to create the metadata file for.
        package: The package to add to the metadata. By default it is the name of the environment's directory.
        executables: The executables to add to the metadata. If not provided, they are searched for in conda's metadata.
    """
    package = package or prefix.name
    apps = (p.name for p in (executables or env_info.find_exes(prefix, package)))
    main = MainPackage(package, prefix, apps)
    meta = CondaxMetaData(main)
    meta.save()


def inject(prefix: Path, packages_to_inject: Iterable[str], include_apps: bool = False):
    """
    Inject the given packages into the condax_metadata.json file for the environment at `prefix`.

    Args:
        prefix: The path to the environment.
        packages_to_inject: The names of the packages to inject.
        include_apps: Whether to make links to the executables of the injected packages.
    """
    meta = load(prefix)
    for pkg in packages_to_inject:
        apps = (p.name for p in env_info.find_exes(prefix, pkg))
        pkg_to_inject = InjectedPackage(pkg, apps, include_apps=include_apps)
        meta.inject(pkg_to_inject)
    meta.save()


def load(prefix: Path) -> CondaxMetaData:
    """Load the metadata object for the given environment.

    If the metadata doesn't exist, it is created.

    Args:
        prefix (Path): The path to the environment.

    Returns:
        CondaxMetaData: The metadata object for the environment.
    """
    meta = _load(prefix)
    # For backward compatibility: metadata can be absent
    if meta is None:
        logger.info(f"Recreating condax_metadata.json in {prefix}...")
        create(prefix)
        meta = _load(prefix)
        if meta is None:
            raise NoMetadataError(prefix)
    return meta


def _load(prefix: Path) -> Optional[CondaxMetaData]:
    """Does the heavy lifting for loading the metadata.

    `load` is the exposed wrapper that tries to create it if it doesn't exist.
    """
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
