"""
how to configure initramfs-tools from debian/ubuntu to build a
stiefelsystem bootable initrd.
"""

from . import install_platform_files


def install(prefix, cfg):
    if 'nbd' in cfg.modules:
        install_platform_files('initramfs-tools_nbd')
        # re-build the initramfs
        command('update-initramfs', '-u', '-k', 'all')
