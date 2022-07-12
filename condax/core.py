import os
import pathlib
import shlex
import subprocess
import shutil
import sys

from . import conda
from .config import CONDA_ENV_PREFIX_PATH, CONDAX_LINK_DESTINATION, DEFAULT_CHANNELS
from .paths import mkpath


def create_link(package, exe):
    executable_name = os.path.basename(exe)
    conda_exe = conda.ensure_conda()
    if os.name == "nt":
        # create a batch file to run our application
        win_path = pathlib.PureWindowsPath(exe)
        name_only, _ = os.path.splitext(executable_name)
        with open(f"{CONDAX_LINK_DESTINATION}/{name_only}.bat", "w") as fo:
            fo.writelines(
                [
                    "@echo off\n",
                    "REM Entrypoint created by condax\n",
                    f"{conda_exe} run --name {package} %*\n",
                ]
            )
    else:
        script_path = os.path.join(CONDAX_LINK_DESTINATION, executable_name)
        with open(script_path, "w") as fo:
            fo.writelines(
                [
                    f"#!/usr/bin/env bash\n\n",
                    f"# Entrypoint created by condax\n",
                    f"{conda_exe} run --name {package} $@\n",
                ]
            )
        shutil.copystat(exe, script_path)


def create_links(package, executables_to_link):
    for exe in executables_to_link:
        create_link(package, exe)
    if len(executables_to_link):
        print("Created the following entrypoint links:", file=sys.stderr)
        for exe in executables_to_link:
            executable_name = os.path.basename(exe)
            print(f"    {executable_name}", file=sys.stderr)


def remove_links(executables_to_unlink):
    for exe in executables_to_unlink:
        executable_name = os.path.basename(exe)
        link_name = f"{CONDAX_LINK_DESTINATION}/{executable_name}"
        if os.path.islink(link_name) and (os.readlink(link_name) == exe):
            os.unlink(link_name)
    if len(executables_to_unlink):
        print("Removed the following entrypoint links:", file=sys.stderr)
        for exe in executables_to_unlink:
            executable_name = os.path.basename(exe)
            print(f"    {executable_name}", file=sys.stderr)


def install_package(package, channels=DEFAULT_CHANNELS):
    conda.create_conda_environment(package, channels=channels)
    executables_to_link = conda.detemine_executables_from_env(package)
    mkpath(CONDAX_LINK_DESTINATION)
    create_links(package, executables_to_link)
    print(f"`{package}` has been installed by condax", file=sys.stderr)


def exit_if_not_installed(package):
    prefix = conda.conda_env_prefix(package)
    if not os.path.exists(prefix):
        print(f"`{package}` is not installed with condax", file=sys.stderr)
        sys.exit(0)


def remove_package(package):
    exit_if_not_installed(package)

    executables_to_unlink = conda.detemine_executables_from_env(package)
    remove_links(executables_to_unlink)
    conda.remove_conda_env(package)
    print(f"`{package}` has been removed from condax", file=sys.stderr)


def update_all_packages():
    for package in os.listdir(CONDA_ENV_PREFIX_PATH):
        if os.path.isdir(os.path.join(CONDA_ENV_PREFIX_PATH, package)):
            update_package(package)


def list_all_packages():
    packages = []
    for package in os.listdir(CONDA_ENV_PREFIX_PATH):
        if os.path.isdir(os.path.join(CONDA_ENV_PREFIX_PATH, package)):
            packages.append(package)
    packages.sort()

    # messages follow pipx's text format
    print(f"conda envs are in {CONDA_ENV_PREFIX_PATH}")
    print(f"apps are exposed on your $PATH at {CONDAX_LINK_DESTINATION}")
    for package in packages:
        _, python_version, _ = conda.get_package_info(package, "python")
        package_name, package_version, package_build = conda.get_package_info(package)
        package_header = "".join([
            f"  package {shlex.quote(package_name)}",
            f" {package_version} ({package_build})",
            f", installed using Python {python_version}" if python_version else "",
        ])
        print(package_header)

        try:
            paths = conda.detemine_executables_from_env(package)
            names = [os.path.basename(path) for path in paths]
            for name in sorted(names):
                print(f"    - {name}")
        except ValueError:
            print("    (no executables found)")


def update_package(package):
    exit_if_not_installed(package)
    try:
        executables_already_linked = set(conda.detemine_executables_from_env(package))
        conda.update_conda_env(package)
        executables_linked_in_updated = set(
            conda.detemine_executables_from_env(package)
        )

        to_create = executables_linked_in_updated - executables_already_linked
        to_delete = executables_already_linked - executables_linked_in_updated

        create_links(package, to_create)
        remove_links(to_delete)
        print(f"{package} update successfully")

    except subprocess.CalledProcessError:
        print(f"`{package}` could not be updated", file=sys.stderr)
        print(f"removing and recreating instead", file=sys.stderr)

        remove_package(package)
        install_package(package)
