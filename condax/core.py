import collections
import logging
import os
import shlex
import subprocess
import shutil
from pathlib import Path
from typing import Counter, Dict, Iterable, List

import condax.conda as conda
from condax.exceptions import CondaxError
import condax.metadata as metadata
import condax.wrapper as wrapper
import condax.utils as utils
import condax.config as config
from condax.config import C


logger = logging.getLogger(__name__)


def create_link(package: str, exe: Path, is_forcing: bool = False) -> bool:
    micromamba_exe = conda.ensure_micromamba()
    executable_name = exe.name
    # FIXME: Enforcing conda (not mamba) for `conda run` for now
    prefix = conda.conda_env_prefix(package)
    if os.name == "nt":
        script_lines = [
            "@rem Entrypoint created by condax\n",
            f"@call {utils.quote(micromamba_exe)} run --prefix {utils.quote(prefix)} {utils.quote(exe)} %*\n",
        ]
    else:
        script_lines = [
            "#!/usr/bin/env bash\n",
            "\n",
            "# Entrypoint created by condax\n",
            f'{utils.quote(micromamba_exe)} run --prefix {utils.quote(prefix)} {utils.quote(exe)} "$@"\n',
        ]
        if utils.to_bool(os.environ.get("CONDAX_HIDE_EXITCODE", False)):
            # Let scripts to return exit code 0 constantly
            script_lines.append("exit 0\n")

    script_path = _get_wrapper_path(executable_name)
    if script_path.exists() and not is_forcing:
        user_input = input(f"{executable_name} already exists. Overwrite? (y/N) ")
        if user_input.strip().lower() not in ("y", "yes"):
            logger.warning(f"Skipped creating entrypoint: {executable_name}")
            return False

    if script_path.exists():
        logger.warning(f"Overwriting entrypoint: {executable_name}")
        utils.unlink(script_path)
    with open(script_path, "w") as fo:
        fo.writelines(script_lines)
    shutil.copystat(exe, script_path)
    return True


def create_links(
    package: str, executables_to_link: Iterable[Path], is_forcing: bool = False
):
    linked = (
        exe.name
        for exe in sorted(executables_to_link)
        if create_link(package, exe, is_forcing=is_forcing)
    )
    if executables_to_link:
        logger.info("\n  - ".join(("Created the following entrypoint links:", *linked)))


def remove_links(package: str, app_names_to_unlink: Iterable[str]):
    unlinked: List[str] = []
    if os.name == "nt":
        # FIXME: this is hand-waving for now
        for executable_name in app_names_to_unlink:
            link_path = _get_wrapper_path(executable_name)
            utils.unlink(link_path)
    else:
        for executable_name in app_names_to_unlink:
            link_path = _get_wrapper_path(executable_name)
            wrapper_env = wrapper.read_env_name(link_path)
            if wrapper_env is None:
                utils.unlink(link_path)
                unlinked.append(f"{executable_name} \t (failed to get env)")
            elif wrapper_env == package:
                link_path.unlink()
                unlinked.append(executable_name)
            else:
                logger.warning(
                    f"Keeping {executable_name} as it runs in environment `{wrapper_env}`, not `{package}`."
                )

    if app_names_to_unlink:
        logger.info(
            "\n  - ".join(("Removed the following entrypoint links:", *unlinked))
        )


class PackageInstalledError(CondaxError):
    def __init__(self, package: str):
        super().__init__(
            20,
            f"Package `{package}` is already installed. Use `--force` to force install.",
        )


def install_package(
    spec: str,
    is_forcing: bool = False,
    conda_stdout: bool = False,
):
    package, _ = utils.split_match_specs(spec)

    if conda.has_conda_env(package):
        if is_forcing:
            logger.warning(f"Overwriting environment for {package}")
            conda.remove_conda_env(package, conda_stdout)
        else:
            raise PackageInstalledError(package)

    conda.create_conda_environment(spec, conda_stdout)
    executables_to_link = conda.determine_executables_from_env(package)
    utils.mkdir(C.bin_dir())
    create_links(package, executables_to_link, is_forcing=is_forcing)
    _create_metadata(package)
    logger.info(f"`{package}` has been installed by condax")


class PackageMissingInEnvFileError(CondaxError):
    def __init__(self, package: str):
        super().__init__(
            20,
            f"Package `{package}` is missing in the provided environment file. Specify package(s) in the `dependencies`.",
        )


def install_via_env_file(
    envfile: Path,
    packages: List[str],
    is_forcing: bool = False,
    conda_stdout: bool = False,
):
    """Install a package via conda environment YAML file.

    The first package becomes the environment name, and the rest will be injected to the environment.
    """

    dependent_packages = utils.get_env_dependencies(envfile)
    for p in packages:
        if p not in dependent_packages:
            raise PackageMissingInEnvFileError(p)

    # Take the first user-specified package name as the environment name
    package_name = packages[0]
    if conda.has_conda_env(package_name):
        if is_forcing:
            logger.warning(f"Overwriting environment for {package_name}")
            conda.remove_conda_env(package_name, conda_stdout)
        else:
            raise PackageInstalledError(package_name)

    conda.import_env(envfile, is_forcing, conda_stdout, package_name)
    executables_to_link = conda.determine_executables_from_env(package_name)
    utils.mkdir(C.bin_dir())
    create_links(package_name, executables_to_link, is_forcing=is_forcing)
    _create_metadata(package_name)

    # Treat the rest of user-specified packages as injected apps
    injected_packages = packages[1:]
    _inject_to_metadata(package_name, injected_packages, include_apps=True)
    for injected_pkg in injected_packages:
        executables_to_link = conda.determine_executables_from_env(
            package_name,
            injected_pkg,
        )
        create_links(package_name, executables_to_link, is_forcing=is_forcing)

    logger.info(
        f"`Dependencies in {envfile.name} have been installed as the package `{package_name}`."
    )


def inject_package_to(
    env_name: str,
    injected_specs: List[str],
    is_forcing: bool = False,
    include_apps: bool = False,
    conda_stdout: bool = False,
):
    pairs = [utils.split_match_specs(spec) for spec in injected_specs]
    injected_packages, _ = zip(*pairs)
    pkgs_str = " and ".join(injected_packages)
    if not conda.has_conda_env(env_name):
        raise PackageNotInstalled(env_name)

    conda.inject_to_conda_env(
        injected_specs,
        env_name,
        conda_stdout,
    )

    # update the metadata
    _inject_to_metadata(env_name, injected_packages, include_apps)

    # Add links only if --include-apps is set
    if include_apps:
        for injected_pkg in injected_packages:
            executables_to_link = conda.determine_executables_from_env(
                env_name,
                injected_pkg,
            )
            create_links(env_name, executables_to_link, is_forcing=is_forcing)
    logger.info(f"`Done injecting {pkgs_str} to `{env_name}`")


def uninject_package_from(
    env_name: str, packages_to_uninject: List[str], conda_stdout: bool = False
):
    if not conda.has_conda_env(env_name):
        raise PackageNotInstalled(env_name)

    already_injected = set(_get_injected_packages(env_name))
    to_uninject = set(packages_to_uninject)
    not_found = to_uninject - already_injected
    for pkg in not_found:
        logger.info(f"`{pkg}` is absent in the `{env_name}` environment.")

    found = to_uninject & already_injected
    if not found:
        logger.warning(f"`No package is uninjected from {env_name}`")
        return

    packages_to_uninject = sorted(found)
    conda.uninject_from_conda_env(packages_to_uninject, env_name, conda_stdout)

    injected_app_names = [
        app for pkg in packages_to_uninject for app in _get_injected_apps(env_name, pkg)
    ]
    remove_links(env_name, injected_app_names)
    _uninject_from_metadata(env_name, packages_to_uninject)

    pkgs_str = " and ".join(packages_to_uninject)
    logger.info(f"`{pkgs_str}` has been uninjected from `{env_name}`")


class PackageNotInstalled(CondaxError):
    def __init__(self, package: str, error: bool = True):
        super().__init__(
            21 if error else 0,
            f"Package `{package}` is not installed with condax",
        )


def exit_if_not_installed(package: str, error: bool = True):
    prefix = conda.conda_env_prefix(package)
    if not prefix.exists():
        raise PackageNotInstalled(package, error)


def remove_package(package: str, conda_stdout: bool = False):
    exit_if_not_installed(package, error=False)
    apps_to_unlink = _get_apps(package)
    remove_links(package, apps_to_unlink)
    conda.remove_conda_env(package, conda_stdout)
    logger.info(f"`{package}` has been removed from condax")


def update_all_packages(update_specs: bool = False, is_forcing: bool = False):
    for package in _get_all_envs():
        update_package(package, update_specs=update_specs, is_forcing=is_forcing)


def list_all_packages(short=False, include_injected=False) -> None:
    if short:
        _list_all_packages_short(include_injected)
    else:
        _list_all_packages(include_injected)


def _list_all_packages_short(include_injected: bool) -> None:
    """
    List packages with --short flag
    """
    for package in _get_all_envs():
        package_name, package_version, _ = conda.get_package_info(package)
        print(f"{package_name} {package_version}")
        if include_injected:
            injected_packages = _get_injected_packages(package_name)
            for injected_pkg in injected_packages:
                name, version, _ = conda.get_package_info(package_name, injected_pkg)
                print(f"    {name} {version}")


def _list_all_packages(include_injected: bool) -> None:
    """
    List packages without any flags
    """
    # messages follow pipx's text format
    _print_condax_dirs()

    executable_counts: Counter[str] = collections.Counter()
    for env in _get_all_envs():
        _list_env(env, executable_counts, include_injected)

    # warn if duplicate of executables are found
    duplicates = [name for (name, cnt) in executable_counts.items() if cnt > 1]
    if duplicates and not include_injected:
        logger.warning(f"\n[warning] The following executables conflict:")
        logger.warning("\n".join(f"    * {name}" for name in duplicates) + "\n")


def _list_env(
    env: str, executable_counts: Counter[str], include_injected: bool
) -> None:
    _, python_version, _ = conda.get_package_info(env, "python")
    package_name, package_version, package_build = conda.get_package_info(env)

    package_header = "".join(
        [
            f"{shlex.quote(package_name)}",
            f" {package_version} {package_build}",
            f", using Python {python_version}" if python_version else "",
        ]
    )
    print(package_header)

    apps = _get_apps(env)
    executable_counts.update(apps)
    if not apps and not include_injected:
        print(f"    (No apps found for {env})")
    else:
        for app in apps:
            app = utils.strip_exe_ext(app)  # for windows
            print(f"    - {app}")

        if include_injected:
            _list_injected(package_name)
    print()


def _list_injected(package_name: str):
    names_injected_apps = _get_injected_apps_dict(package_name)
    for name, injected_apps in names_injected_apps.items():
        for app in injected_apps:
            app = utils.strip_exe_ext(app)  # for windows
            print(f"    - {app}  (from {name})")

    injected_packages = _get_injected_packages(package_name)
    if injected_packages:
        print("    Included packages:")

    for injected_pkg in injected_packages:
        name, version, build = conda.get_package_info(package_name, injected_pkg)
        print(f"        {name} {version} {build}")


def _print_condax_dirs() -> None:
    logger.info(
        f"conda envs are in {C.prefix_dir()}\n"
        f"apps are exposed on your $PATH at {C.bin_dir()}\n"
    )


def update_package(
    spec: str,
    update_specs: bool = False,
    is_forcing: bool = False,
    conda_stdout: bool = False,
) -> None:

    env, _ = utils.split_match_specs(spec)
    exit_if_not_installed(env)
    try:
        main_apps_before_update = set(conda.determine_executables_from_env(env))
        injected_apps_before_update = {
            injected: set(conda.determine_executables_from_env(env, injected))
            for injected in _get_injected_packages(env)
        }
        conda.update_conda_env(spec, update_specs, conda_stdout)
        main_apps_after_update = set(conda.determine_executables_from_env(env))
        injected_apps_after_update = {
            injected: set(conda.determine_executables_from_env(env, injected))
            for injected in _get_injected_packages(env)
        }

        if (
            main_apps_before_update == main_apps_after_update
            and injected_apps_before_update == injected_apps_after_update
        ):
            logger.info(f"No updates found: {env}")

        to_create = main_apps_after_update - main_apps_before_update
        to_delete = main_apps_before_update - main_apps_after_update
        to_delete_apps = [path.name for path in to_delete]

        # Update links of main apps
        create_links(env, to_create, is_forcing)
        remove_links(env, to_delete_apps)

        # Update links of injected apps
        for pkg in _get_injected_packages(env):
            to_delete = (
                injected_apps_before_update[pkg] - injected_apps_after_update[pkg]
            )
            to_delete_apps = [p.name for p in to_delete]
            remove_links(env, to_delete_apps)

            to_create = (
                injected_apps_after_update[pkg] - injected_apps_before_update[pkg]
            )
            create_links(env, to_create, is_forcing)

        logger.info(f"{env} update successfully")

    except subprocess.CalledProcessError:
        logger.error(f"Failed to update `{env}`")
        logger.warning(f"Recreating the environment...")

        remove_package(env, conda_stdout)
        install_package(env, is_forcing=is_forcing, conda_stdout=conda_stdout)

    # Update metadata file
    _create_metadata(env)
    for pkg in _get_injected_packages(env):
        _inject_to_metadata(env, pkg)


def _create_metadata(package: str):
    """
    Create metadata file
    """
    apps = [p.name for p in conda.determine_executables_from_env(package)]
    main = metadata.MainPackage(package, apps)
    meta = metadata.CondaxMetaData(main)
    meta.save()


class NoMetadataError(CondaxError):
    def __init__(self, env: str):
        super().__init__(22, f"Failed to recreate condax_metadata.json in {env}")


def _load_metadata(env: str) -> metadata.CondaxMetaData:
    meta = metadata.load(env)
    # For backward compatibility: metadata can be absent
    if meta is None:
        logger.info(f"Recreating condax_metadata.json in {env}...")
        _create_metadata(env)
        meta = metadata.load(env)
        if meta is None:
            raise NoMetadataError(env)
    return meta


def _inject_to_metadata(
    env: str, packages_to_inject: Iterable[str], include_apps: bool = False
):
    """
    Inject the package into the condax_metadata.json file for the env.
    """
    meta = _load_metadata(env)
    for pkg in packages_to_inject:
        apps = [p.name for p in conda.determine_executables_from_env(env, pkg)]
        pkg_to_inject = metadata.InjectedPackage(pkg, apps, include_apps=include_apps)
        meta.uninject(pkg)  # overwrites if necessary
        meta.inject(pkg_to_inject)
    meta.save()


def _uninject_from_metadata(env: str, packages_to_uninject: Iterable[str]):
    """
    Uninject the package from the condax_metadata.json file for the env.
    """
    meta = _load_metadata(env)
    for pkg in packages_to_uninject:
        meta.uninject(pkg)
    meta.save()


def _get_all_envs() -> List[str]:
    """
    Get all conda envs
    """
    utils.mkdir(C.prefix_dir())
    return sorted(
        pkg_dir.name
        for pkg_dir in C.prefix_dir().iterdir()
        if utils.is_env_dir(pkg_dir)
    )


def _get_injected_packages(env_name: str) -> List[str]:
    """
    Get the list of packages injected into the env.
    """
    meta = _load_metadata(env_name)
    return [p.name for p in meta.injected_packages]


def _get_injected_apps(env_name: str, injected_name: str) -> List[str]:
    """
    Return a list of apps for the given injected package.

    [NOTE] Get a non-empty list only if "include_apps" is True in the metadata.
    """
    meta = _load_metadata(env_name)
    result = [
        app
        for p in meta.injected_packages
        if p.name == injected_name and p.include_apps
        for app in p.apps
    ]
    return result


def _get_main_apps(env_name: str) -> List[str]:
    """
    Return a list of all apps
    """
    meta = _load_metadata(env_name)
    return meta.main_package.apps


def _get_injected_apps_dict(env_name: str) -> Dict[str, List[str]]:
    """
    Return a list of all apps
    """
    meta = _load_metadata(env_name)
    return {p.name: p.apps for p in meta.injected_packages if p.include_apps}


def _get_apps(env_name: str) -> List[str]:
    """
    Return a list of all apps
    """
    meta = _load_metadata(env_name)
    return meta.main_package.apps + [
        app for p in meta.injected_packages if p.include_apps for app in p.apps
    ]


def _get_wrapper_path(cmd_name: str) -> Path:
    p = C.bin_dir() / cmd_name
    if os.name == "nt":
        p = p.parent / (p.stem + ".bat")
    return p


def export_all_environments(out_dir: str, conda_stdout: bool = False) -> None:
    """Export all environments to a directory.

    NOTE: Each environment exports two files:
        - One is YAML from `conda env export`.
        - Another is a copy of `condax_metadata.json`.
    """
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    logger.info(f"Started exporting all environments to {p}")

    envs = _get_all_envs()
    for env in envs:
        conda.export_env(env, p, conda_stdout)
        _copy_metadata(env, p)

    logger.info("Done.")


def _copy_metadata(env: str, p: Path):
    """Export `condax_metadata.json` in the prefix directory `env`
    to the specified directory."""
    _from = metadata.CondaxMetaData.get_path(env)
    _to = p / f"{env}.json"
    shutil.copyfile(_from, _to, follow_symlinks=True)


def _overwrite_metadata(envfile: Path):
    """Import `condax_metadata.json file` to the prefix directory."""
    env = envfile.stem
    _from = envfile
    _to = metadata.CondaxMetaData.get_path(env)
    if _to.exists():
        shutil.move(_to, _to.with_suffix(".bak"))
    shutil.copyfile(_from, _to, follow_symlinks=True)


def import_environments(
    in_dir: str, is_forcing: bool, conda_stdout: bool = False
) -> None:
    """Import all environments from a directory."""
    p = Path(in_dir)
    logger.info(f"Started importing environments in {p}")
    for i, envfile in enumerate(p.glob("*.yml")):
        env = envfile.stem
        if conda.has_conda_env(env):
            if is_forcing:
                remove_package(env, conda_stdout)
            else:
                logger.info(f"Environment {env} already exists. Skipping...")
                continue

        conda.import_env(envfile, is_forcing, conda_stdout)
        # clean up every 10 packages
        if (i + 1) % 10 == 0:
            logger.info("Cleaning up...")
            conda.mamba_clean_all(conda_stdout)
        metafile = p / (env + ".json")
        _overwrite_metadata(metafile)
        _recreate_links(env)

    logger.info("Done imports.")


def _get_executables_to_link(env: str) -> List[Path]:
    """Return a list of executables to link."""
    meta = _load_metadata(env)

    env = meta.main_package.name
    result = conda.determine_executables_from_env(env)

    injected_packages = meta.injected_packages
    for pkg in injected_packages:
        if pkg.include_apps:
            result += conda.determine_executables_from_env(env, pkg.name)

    return result


def _recreate_links(env: str) -> None:
    """
    Recreate the links for the given environment.
    """
    executables_to_link = _get_executables_to_link(env)
    create_links(env, executables_to_link, is_forcing=True)


def _recreate_all_links():
    """
    Recreate the links for all environments.
    """
    envs = _get_all_envs()
    for env in envs:
        _recreate_links(env)


def _prune_links():
    """Remove condax bash scripts if broken."""
    to_apps = {env: _get_apps(env) for env in _get_all_envs()}

    utils.mkdir(C.bin_dir())
    links = C.bin_dir().glob("*")
    for link in links:
        if link.is_symlink() and (not link.exists()):
            link.unlink()

        if not wrapper.is_wrapper(link):
            continue

        target_env = wrapper.read_env_name(link)
        if target_env is None:
            logging.info(f"Failed to read env name from {link}")
            continue

        exec_name = utils.to_body_ext(link.name)
        valid_apps = to_apps.get(target_env, [])
        if exec_name not in valid_apps:
            print("  ... removing", link)
            link.unlink()


def _add_to_conda_env_list() -> None:
    """Add condax environment prefixes to ~/.conda/environments.txt if not already there."""
    envs = _get_all_envs()
    prefixe_str_set = {str(conda.conda_env_prefix(env)) for env in envs}
    lines = set()

    envs_txt = config.CONDA_ENVIRONMENT_FILE
    if envs_txt.exists():
        with envs_txt.open() as f:
            lines = {line.strip() for line in f.readlines()}

    missing = sorted(prefixe_str_set - lines)
    if missing:
        envs_txt.parent.mkdir(exist_ok=True)
        with envs_txt.open("a") as f:
            print("", file=f)
            print("\n".join(missing), file=f)


def fix_links():
    """Repair condax bash scripts in bin_dir."""
    utils.mkdir(C.bin_dir())

    print(f"Repairing links in the BIN_DIR: {C.bin_dir()}...")
    _prune_links()
    _recreate_all_links()
    _add_to_conda_env_list()
    print("  ... Done.")
