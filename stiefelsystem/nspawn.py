import argparse

from .subcommand import Subcommand
from .util import (
    command,
    ensure_root,
)


class NSpawnTest(Subcommand):
    """
    Run the StiefelOS image in systemd-nspawn.
    """

    @classmethod
    def register(cls, cli):
        cli.add_argument('--target', default=ConfigDefault("path.initrd"))
        cli.set_defaults(subcommand=cls)

    def run(self, args, cfg):
        """
        launch nspawn inside the stiefelOS image.
        """

        ensure_root()

        command('-b', nspawn=args.target)
