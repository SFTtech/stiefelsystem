"""
automatic update for your current system
"""

from pathlib import Path

from .subcommand import Subcommand
from .stiefelos.creator import StiefelOSCreator


class Updater(Subcommand):
    """
    Discover how your system is set up so stiefelsystem configuration
    and installation is adapted.

    TODO: things to do here:
    - refresh host os setup (static files)
      show diff, should remain identical if installed via distro)
    - make sure stiefelos was built properly
    - figure out the blocks, luks, ... to boot without configuration
    - write json config read by autokexec / stiefel-server
    """

    @classmethod
    def register(cls, cli):
        cli.add_argument("-p", "--prefix", default="/",
                         help="filesystem root prefix to operate on")
        # get all options from stiefelos creation
        StiefelOSCreator.register(cli)

        cli.set_defaults(subcommand=cls)

        def checkfunc(args):
            args.prefix = Path(args.prefix)
        cli.set_defaults(checkfunc=checkfunc)

    def run(self, args, cfg):

        stiefeloscreator = StiefelOSCreator()
        stiefeloscreator.run(args, cfg)

        with open('aes-key', 'rb') as keyfileobj:
            KEY = keyfileobj.read()

        # TODO: this only works after stiefelos was generated!

        # write the config.json after everything was created/updated successfully
        stiefel_config = {
            'aes-key-hash': hashlib.sha256(KEY).hexdigest(),
            'hmac-key': hashlib.sha256(b'autokexec-reboot/' + KEY).hexdigest(),
            "autokexec-triggers": {
                "mac_detectoion": cfg.autokexec.macs,
                "broadcast": cfg.autokexec.broadcast,
                "adapters": cfg.autokexec.macs,
            },
            "bootdisk": cfg.boot.disk,
            "bootpart-luks": cfg.boot.luks_block,
            "bootpart": cfg.boot.part,
            "stiefelsystem-kernel": cfg.server_setup.stiefelsystem_kernel,
            "stiefelsystem-initrd": cfg.server_setup.stiefelsystem_initrd,
            "cmdline": cfg.server_setup.cmdline,
        }

        # TODO: rename to autokexec config
        edit = FileEditor(args.prefix / 'etc/stiefelsystem/config.json')
        edit.set_data(json.dumps(stiefel_config, indent=4).encode() + b'\n')
        edit.write()

        raise NotImplementedError()
