"""
script to prepare your OS for being stiefeled.
"""
from pathlib import Path

from .subcommand import Subcommand
from .platform import nbd


class HostOSSetup(Subcommand):
    """
    Setup your regular OS so it can be served by StiefelOS server.

    This can either be used directly by a user
    or when creating a stiefelsystem distribution package.

    All steps here must be possible without any dynamic configuration,
    since this is what can be executed when packaging stiefelsystem.
    """

    @classmethod
    def register(cls, cli):
        cli.add_argument("-p", "--prefix", default="/",
                         help="filesystem prefix to use for installing files")

        cli.set_defaults(subcommand=cls)

        def checkfunc(args):
            args.prefix = Path(args.prefix)
        cli.set_defaults(checkfunc=checkfunc)

    def run(self, args, cfg):
        if 'nbd' in cfg.modules:
            nbd.install(args.prefix, cfg)

        else:
            raise RuntimeError("no disk transport mechanism enabled")
