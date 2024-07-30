"""
stiefelsystem main entry point
"""

import argparse
from pathlib import Path
import importlib.resources
import sysconfig


from .cli import parse_args, set_config_defaults
from .config import Config
from .util import log_setup


def main():
    """
    parse and launch requested feature
    """

    # detect if stiefelsystem is running in its repo, or globally
    module_location = Path(importlib.resources.files("stiefelsystem"))
    sys_mod_path = Path(sysconfig.get_path("purelib"))
    system_mode = module_location.is_relative_to(sys_mod_path)

    args = parse_args()

    # adjust log level
    log_setup(args.verbose - args.quiet)

    # instance the subcommand class
    subcommand = args.subcommand()

    # parse and evaluate config file,
    # and use args to override available config fields
    config = Config(args.config_file, system_mode)

    # for arguments that shall take their defaults from the config file
    # resolve the values here.
    set_config_defaults(args, config)

    # run the subcommand
    ret = subcommand.run(args, config)

    exit(ret)
