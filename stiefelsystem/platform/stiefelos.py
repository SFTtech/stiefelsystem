"""
what to do to allow starting stiefelos on a hostos.
"""

import json
from pathlib import Path

from stiefelsystem.util import FileEditor


def install(prefix, cfg):
    """
    install files so a host system can find stiefelos files and parameters
    to start it.
    """

    # TODO default paths
    # on arch:
    #    "kernel": "vmlinuz-linux",
    #    "initrd": "initramfs-stiefel.img",

    # tell stiefel-server which kernel to serve to a stiefel-client,
    # relative to /boot
    boot_config = {
        # paths to files inside the boot partition
        "kernel": cfg.boot.kernel,
        "initrd": cfg.boot.initrd,
        # cmdline to pass to the above kernel when its started
        "cmdline": cfg.boot.cmdline,
        "stiefelmodules": list(cfg.modules.keys()),
    }

    # TODO: that's the config file read by stiefel-server what to serve!
    edit = FileEditor(prefix / 'boot/stiefelsystem.json')
    edit.set_data(json.dumps(boot_config, indent=4).encode() + b'\n')
    edit.write()

    # store the stiefelsystem kernel and initrd on the host system
    # it will be used for autokexec on the server
    stiefelos_initrd_src = cfg.path.work / 'initrd.cpio'
    # TODO asdf: the kernel is inside this initrd too...
    stiefelos_kernel_src = cfg.path.initrd / 'vmlinuz'

    if not stiefelos_initrd_src.resolve().is_file():
        raise Exception("stiefelos initrd not found - did you create it?")
    if not stiefelos_kernel_src.resolve().is_file():
        raise Exception("stiefelos kernel not found - did you create it?")

    edit = FileEditor(prefix / Path(cfg.server_setup.stiefel_os_initrd).relative_to("/"))
    edit.load_from(stiefelos_initrd_src)
    edit.write()

    # same for the debian-generic-kernel
    edit = FileEditor(prefix / Path(cfg.server_setup.stiefel_os_kernel).relative_to("/"))
    edit.load_from(stiefelos_kernel_src)
    edit.write()
