from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, List, Optional

from condax.conda import env_info


def create_metadata(env: Path, package: str, executables: Iterable[Path]):
    """
    Create metadata file
    """
    apps = [p.name for p in (executables or env_info.find_exes(env, package))]
    main = MainPackage(package, env, apps)
    meta = CondaxMetaData(main)
    meta.save()


class _PackageBase:
    def __init__(self, name: str, apps: List[str], include_apps: bool):
        self.name = name
        self.apps = apps
        self.include_apps = include_apps

    def __lt__(self, other):
        return self.name < other.name


@dataclass
class MainPackage(_PackageBase):
    name: str
    prefix: Path
    apps: List[str]
    include_apps: bool = True


class InjectedPackage(_PackageBase):
    pass


class CondaxMetaData:
    """
    Handle metadata information written in `condax_metadata.json`
    placed in each environment.
    """

    metadata_file = "condax_metadata.json"

    def __init__(self, main: MainPackage, injected: Iterable[InjectedPackage] = ()):
        self.main_package = main
        self.injected_packages = tuple(sorted(injected))

    def inject(self, package: InjectedPackage):
        self.injected_packages = tuple(sorted(set(self.injected_packages) | {package}))

    def uninject(self, name: str):
        self.injected_packages = tuple(
            p for p in self.injected_packages if p.name != name
        )

    def to_json(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def save(self) -> None:
        p = self.main_package.prefix / self.metadata_file
        with open(p, "w") as fo:
            fo.write(self.to_json())


def load(prefix: Path) -> Optional[CondaxMetaData]:
    p = prefix / CondaxMetaData.metadata_file
    if not p.exists():
        return None

    with open(p) as f:
        d = json.load(f)
        if not d:
            raise ValueError(f"Failed to read the metadata from {p}")
    return _from_dict(d)


def _from_dict(d: dict) -> CondaxMetaData:
    main = MainPackage(**d["main_package"])
    injected = [InjectedPackage(**p) for p in d["injected_packages"]]
    return CondaxMetaData(main, injected)
