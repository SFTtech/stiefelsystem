"""
all available cli entry points
"""

import argparse
import importlib.resources
import os
from pathlib import Path

from .client import Client
from .hostos import HostOSSetup
from .nspawn import NSpawnTest
from .qemu import QemuTest
from .server import Server
from .stiefelos.creator import StiefelOSCreator
from .stiefelos.launch import StiefelOSLauncher
from .subcommand import ConfigDefault
from .update import Updater
from .usbdrive import USBDriveCreator


def parse_args(system_mode=False):
    """
    stiefelsystem has many subcommands:
    - launch stiefelos as client or server
    - for testing with qemu
    - create stiefelos image
    """

    if system_mode:
        # the python module is installed - use the system-wide config file by default
        config_location = "/etc/stiefelsystem/config.yaml"
    else:
        # use the in-repo location
        package_name = __name__.split(".", maxsplit=1)[0]
        package_location = Path(importlib.resources.files(package_name))
        config_location = (package_location.parent / "config.yaml").relative_to(os.getcwd())

    # argument definitions
    cli = argparse.ArgumentParser(description='stiefelsystem - the network boot system')

    cli.add_argument("-v", "--verbose", action="count", default=0,
                     help="increase program verbosity")
    cli.add_argument("-q", "--quiet", action="count", default=0,
                     help="decrease program verbosity")

    cli.add_argument("-c", "--config-file", default=config_location,
                     help="path to main configuration file (default: %(default)s)")

    sp = cli.add_subparsers(dest='mode')
    sp.required = True

    def register_parser(modename, classname, help=None):
        subparser = sp.add_parser(modename, help=help)
        classname.register(subparser)

    register_parser('update', Updater,
                    help="auto-update your stiefelsystem installation")
    register_parser('setup-host-os', HostOSSetup,
                    help="install files to enable stiefelsystem on your host system")
    register_parser('create-stiefelos', StiefelOSCreator,
                    help="create the stiefelOS system image")
    register_parser('create-usbdrive', USBDriveCreator,
                    help="write startup data to a usb drive")
    register_parser('launch-stiefelos', StiefelOSLauncher,
                    help="replace your current system with stiefelOS by kexec")
    register_parser('test-nspawn', NSpawnTest,
                    help="run nspawn for stiefelOS development")
    register_parser('test-qemu', QemuTest,
                    help="run QEMU for stiefelsystem development")
    register_parser('server', Server,
                    help="serve disks over the stiefelsystem protocol")
    register_parser('client', Client,
                    help="access and boot discs over the stiefelsystem protocol")

    args = cli.parse_args()

    # if registered in a subparser, check args for consistency
    if hasattr(args, "checkfunc"):
        args.checkfunc(args)

    return args


def set_config_defaults(args, config):
    """
    scan all the args and replace special ConfigDefault values
    with the configuration file value.
    """
    replacements = dict()
    for member, value in vars(args).items():
        if isinstance(value, ConfigDefault):
            replacements[member] = value.get_value(config)

    vars(args).update(replacements)
