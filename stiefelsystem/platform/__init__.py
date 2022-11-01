"""
stiefelsystem platform specific files

each linux distribution and tool needs its special configuration.
they are implemented here.
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
    if __name__.split(".")[0] != 'stiefelsystem':
        raise Exception(
            "stiefelsystem needs to find itself as python module. "
            f"sadly, stiefelsystem is currently running as {__name__!r}. "
            "we need to know this name because we install that python "
            "module into the stiefelsystem initrd."
        )

    return Path(importlib.resources.files(module_name))


def install_platform_files(file_glob, prefix: Path,
                           module_name="stiefelsystem.platform",
                           subdirectory="files"):
    """
    install $module_name/$subdirectory/$file_glob into prefix/
    by default this is platform/files/$glob
    """

    mod_dir = get_platform_module_files_path(module_name)

    if subdirectory:
        glob_pattern = os.path.join(subdirectory, file_glob)
    else:
        glob_pattern = file_glob

    for data_elem in mod_dir.glob(glob_pattern):
        data_relpath = data_elem.relative_to(mod_dir)
        if data_elem.is_dir():
            (prefix / data_relpath).mkdir(parents=True, exist_ok=True)
        elif data_elem.is_file():
            shutil.copy(data_elem, prefix / data_relpath)
        else:
            raise Exception(f"platform/files glob result neigher file nor directory: {data_elem}")
