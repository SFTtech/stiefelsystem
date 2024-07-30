"""
utilities for handling platform specific files
"""

import shutil
import os
import importlib.resources

from pathlib import Path


def get_platform_module_files_path(module_name):
    """
    get the directory path where the given python module name
    stores its files.
    """
    base_module_name = __name__.split(".")[0]
    if base_module_name != 'stiefelsystem':
        raise Exception(
            "stiefelsystem needs to find itself as python module. "
            f"sadly, stiefelsystem is currently running as {base_module_name!r}. "
            "we need to know this name because we install that python "
            "module into the stiefelsystem initrd."
        )

    return Path(importlib.resources.files(module_name))


def install_platform_files(file_glob, destination: Path,
                           module_name="stiefelsystem.platform",
                           subdirectory="files"):
    """
    recursively install $module_name/$subdirectory/$file_glob into
    destination/$file_glob. by default this is platform/files/$glob

    for the default platform file installation, just set file_glob,
    e.g. to `initrd`.
    """

    mod_dir = get_platform_module_files_path(module_name)

    if subdirectory:
        glob_pattern = os.path.join(subdirectory, file_glob)
        base_path = mod_dir / subdirectory
    else:
        glob_pattern = file_glob
        base_path = mod_dir

    for data_path in mod_dir.glob(glob_pattern):
        data_relpath = data_path.relative_to(base_path)
        if data_path.is_dir():
            shutil.copytree(data_path, destination / data_relpath)
        elif data_path.is_file():
            shutil.copy(data_path, destination / data_relpath)
        else:
            raise Exception(f"platform/files glob result neigher file nor directory: {data_path}")
