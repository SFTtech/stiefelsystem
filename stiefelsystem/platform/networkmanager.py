"""
NetworkManager configuration files
"""

from . import install_platform_files


def install(prefix, cfg):
    install_platform_files("networkmanager")
