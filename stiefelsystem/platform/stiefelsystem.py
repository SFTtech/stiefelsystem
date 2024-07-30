"""
components for stiefelsystem itself.
"""

import sysconfig
import shutil

from .util import get_platform_module_files_path, install_platform_files


def install(prefix):
    """
    install stiefelsystem python module, and service files.
    stiefel-server and stiefel-client can then run in the given prefix.
    usually this is the stiefelos initrd.
    """

    # install python modules to the initrd
    initrd_py_modules = ['stiefelsystem', 'stiefelsystem.platform']

    # the files are shipped due to setup.py package_data!
    # install all platform-specific files so stiefelsystem
    # can self-replicate to take over the world, if desired.
    module_data_dir_globs = {
        'stiefelsystem.platform': ["files/**/*"]
    }

    for module in initrd_py_modules:
        mod_dir = get_platform_module_files_path(module)

        # destination directory for the python module
        # for a posix system (such as our stiefelOS initrd system)
        initrd_mod_dir = (prefix /
                          sysconfig.get_path("purelib", "posix_prefix")[1:] /
                          module.replace('.', '/'))
        initrd_mod_dir.mkdir(parents=True, exist_ok=True)

        # python module files
        for pyfile in mod_dir.iterdir():
            if not pyfile.is_file():
                continue
            shutil.copy(pyfile, initrd_mod_dir)

        # install all data files, restricted by glob.
        for glob_pattern in module_data_dir_globs.get(module, []):
            install_platform_files(glob_pattern, prefix=initrd_mod_dir,
                                   module_name=module, subdirectory=None)

    # systemd units
    install_platform_files("stiefeltools")
    install_platform_files("networkmanager")
