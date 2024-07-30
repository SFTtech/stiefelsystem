"""
Code for generating an initrd system capable of running as stiefel-server
or stiefel-client. So it's used to serve the disk over network, or chain-load
into the server's OS.
"""

from pathlib import Path
import os
import shutil

from ..util import (
    command,
    download_tar,
    ensure_root,
    ensure_single_system,
    initrd_write,
    list_files_in_packages,
    mount_tmpfs,
    umount,
)
from ..subcommand import Subcommand, ConfigDefault
from ..platform import stiefelsystem, stiefelos


class StiefelOSCreator(Subcommand):
    """
    Create the StiefelOS initramfs for running stiefel-client and stiefel-server.
    It is a minimal operating system to share disks or boot from them.
    """

    @classmethod
    def register(cls, cli):
        # TODO: use the system mirror if there is one?
        cli.add_argument('--debian-mirror', default='http://mirror.stusta.de/debian/')
        cli.add_argument('--out', default=ConfigDefault("path.cpio"),
                         help=("output cpio file path. "
                               "default: %(default)s"))
        cli.add_argument('--compressor', default=ConfigDefault("packing.compressor"),
                         help=("compression format to use for initrd. "
                               "default: %(default)s"))
        cli.add_argument('--skip-setup', action='store_true')
        cli.add_argument('--update', action='store_true')
        cli.add_argument('--tmp-work', action='store_true',
                         help='use a tmpfs for work and cachedir')
        cli.add_argument('--prefix', default="/",
                         help=("filesystem prefix to prepend to the resulting "
                               "kernel/initrd installation path"))
        cli.set_defaults(subcommand=cls)

        def checkfunc(args):
            args.prefix = Path(args.prefix)
        cli.set_defaults(checkfunc=checkfunc)

    def run(self, args, cfg):
        """
        Create an initrd suitable for running stiefel-server or stiefel-client
        """

        self.create_image(cfg=cfg, prefix=args.prefix, skip_setup=args.skip_setup,
                          tmp_work=args.tmp_work, debian_mirror_url=args.debian_mirror,
                          update_packages=args.update, compressor=args.compressor,
                          output_file=args.out)

    def create_image(self, cfg, prefix, skip_setup, tmp_work, debian_mirror_url, update_packages,
                     compressor=None, output_file=None):

        ensure_root()
        ensure_single_system(cfg)

        if not skip_setup:
            # discard existing ramdisk content
            umount(cfg.path.initrd_devel)
            umount(cfg.path.work)

            os.makedirs(cfg.path.work, exist_ok=True)
            os.makedirs(cfg.path.cache, exist_ok=True)

            # provide the various tmpfses
            if tmp_work:
                mount_tmpfs(cfg.path.work)
                mount_tmpfs(cfg.path.cache)

            deb_packages = [
                'ifrename',  # needed by the payload scripts
                'iproute2',  # needed by the payload scripts
                'kexec-tools',  # needed for booting the payload system
                'linux-image-amd64',  # needed for booting the stiefel system
                'python3',  # all payload scripts are written in Python3
                'python3-pycryptodome',
                'python3-aiohttp',
                'systemd-container',  # to allow launching inside nspawn during this script
                'systemd-sysv',  # to provide symlinks in /sbin: init, poweroff, ...
            ]

            if 'nbd' in cfg.modules:
                deb_packages.extend(['nbd-server'])

            if 'lvm' in cfg.modules:
                deb_packages.append('lvm2')

            if 'i915' in cfg.modules:
                deb_packages.append('firmware-misc-nonfree')

            if cfg.boot.luks_block:
                deb_packages.append('cryptsetup')

            deb_packages.extend(cfg.initrd.include_packages)

            # perform initial setup
            # this logs to $workdir/$workdir_subpath_initrd/debootstrap/debootstrap.log
            # -> usually "workdir/initrd.nspawn/debootstrap/debootstrap.log"
            print(f"running debootstrap with log {cfg.path.initrd}/debootstrap/debootstrap.log")
            command(
                'debootstrap',
                '--include=' + ','.join(deb_packages),
                '--cache-dir=' + os.path.abspath(cfg.path.cache),
                '--variant=minbase',
                '--components=main,contrib,non-free',
                '--merged-usr',
                '--verbose',
                'stable',
                cfg.path.initrd,
                debian_mirror_url,
            )

        # install the stiefelsystem python module, .service and config files
        stiefelsystem.install(Path(cfg.path.initrd))

        # generate and install AES key securing the initial server/client communication
        # TODO: store in /var/lib/stiefelsystem as statedir of config file
        if not os.path.exists(cfg.aes_key_location):
            print('generating new AES key...')
            with open(cfg.aes_key_location, 'wb') as fileobj:
                fileobj.write(os.urandom(16))

        # TODO rename to something stiefel-related
        shutil.copy(cfg.aes_key_location, Path(cfg.path.initrd) / 'aes-key')

        if not args.skip_setup:
            # set root password
            command(
                'chpasswd',
                nspawn=cfg.path.initrd,
                stdin=f'root:{cfg.initrd.password}\n'
            )

            # set root shell
            command(
                'chsh', '-s',
                cfg.initrd.shell,
                nspawn=cfg.path.initrd
            )

            # enable login from systemd-nspawn
            initrd_write(
                cfg.path.initrd,
                '/etc/securetty',
                'pts/0',
                append=True
            )

            # set the hostname
            initrd_write(
                cfg.path.initrd,
                '/etc/hostname',
                'stiefelsystem'
            )

            # disable lidswitch handling...
            initrd_write(
                cfg.path.initrd,
                '/etc/systemd/logind.conf',
                'HandleSuspendKey=ignore',
                'HandleHibernateKey=ignore',
                'HandleLidSwitch=ignore',
                'HandleLidSwitchExternalPower=ignore',
                'HandleLidSwitchDocked=ignore',
                append=True
            )

            # systemd configuration
            command('systemctl', 'set-default',
                'multi-user.target',
                nspawn=cfg.path.initrd
            )
            command('systemctl', 'enable',
                'fake-entropy.service',
                nspawn=cfg.path.initrd
            )
            command('systemctl', 'disable',
                'rsyslog.service',
                'cron.service',
                'networking.service',
                'kexec.service',
                'kexec-load.service',
                'machines.target',
                'remote-fs.target',
                nspawn=cfg.path.initrd
            )
            command('systemctl', 'mask',
                'serial-getty@.service',
                'apt-daily.timer',
                'apt-daily-upgrade.timer',
                'serial-getty@.service',
                'systemd-journal-flush.service',
                'systemd-timedated.service',
                'systemd-timesyncd.service',
                'systemd-tmpfiles-clean.timer',
                'systemd-update-utmp.service',
                'systemd-update-utmp-runlevel.service',
                'time-sync.target',
                nspawn=cfg.path.initrd
            )

            # stiefel configuration
            if 'nbd' in cfg.modules:
                command('systemctl', 'disable', 'nbd-server.service', nspawn=cfg.path.initrd)
                # the nbd server configuration will be generated on-the-fly

            # kernel name
            kernel_name = os.readlink(cfg.path.initrd + '/vmlinuz')[13:]

            # create devel overlay system which we'll use to compile a few things
            os.makedirs(cfg.path.initrd_devel, exist_ok=True)
            os.makedirs(cfg.path.initrd_devel + "-overlayfs-upperdir", exist_ok=True)
            os.makedirs(cfg.path.initrd_devel + "-overlayfs-workdir", exist_ok=True)

            command(
                "mount",
                "-t", "overlay",
                "overlay",
                "-o", ",".join([
                    f"lowerdir={os.path.abspath(cfg.path.initrd)}",
                    f"upperdir={os.path.abspath(cfg.path.initrd_devel + '-overlayfs-upperdir')}",
                    f"workdir={os.path.abspath(cfg.path.initrd_devel + '-overlayfs-workdir')}",
                ]),
                os.path.abspath(cfg.path.initrd_devel),
            )

            command('apt', 'update', nspawn=cfg.path.initrd_devel)
            command('apt', 'upgrade', nspawn=cfg.path.initrd_devel)
            command('apt', 'install', '-y',
                'build-essential',
                'git',
                'linux-headers-amd64',
                'kmod',
                nspawn=cfg.path.initrd_devel
            )

            # compile and install  the userland driver for the clevo fan controller
            if 'clevo-fancontrol' in cfg.modules:
                download_tar(
                    cfg.mod_config["clevo-fancontrol"].url,
                    os.path.join(cfg.path.initrd_devel, "root/fancontrol")
                )
                command('make', '-C', '/root/fancontrol', nspawn=cfg.path.initrd_devel)
                command(
                    "cp",
                    cfg.path.initrd_devel + "/root/fancontrol/clevo-fancontrol",
                    cfg.path.initrd + "/usr/local/bin",
                )
                command(
                    "cp",
                    cfg.path.initrd_devel + "/root/fancontrol/clevo-fancontrol.service",
                    cfg.path.initrd + "/etc/systemd/system",
                )
                command('systemctl', 'enable',
                    'clevo-fancontrol.service',
                    nspawn=cfg.path.initrd
                )

        if update_packages:
            command('apt', 'update', nspawn=cfg.path.initrd_devel)
            command('apt', 'upgrade', nspawn=cfg.path.initrd_devel)

        if 'debug' in cfg.modules:
            command('updatedb', nspawn=cfg.path.initrd)

        if not skip_setup:
            if 'debug' not in cfg.modules:
                # strip kernel modules
                count = 0
                for path, _, files in os.walk(cfg.path.initrd + '/lib/modules'):
                    for filename in files:
                        if filename.endswith('.ko'):
                            full_path = os.path.join(path, filename)
                            command('strip', '--strip-debug', full_path, silent=count)
                            count += 1
                if count > 1:
                    print(f'$ ... (stripped {count - 1} more modules)')

        # the folder is ready, now we can pack and compress the initrd

        paths_to_exclude = set(
            list_files_in_packages(cfg.packing.exclude_packages, cfg.path.initrd)
        )
        paths_to_exclude.update(
            path.encode() for path in cfg.packing.exclude_paths
        )

        old_cwd = os.getcwd()
        os.chdir(cfg.path.initrd)

        def scan_path(path):
            for name in os.listdir(path):
                full = os.path.normpath(os.path.join(path, name))

                if full in paths_to_exclude:
                    continue
                if full.endswith(b'__pycache__'):
                    continue

                yield full
                # recurse into directories (don't follow links)
                if os.path.isdir(full) and not os.path.islink(full):
                    yield from scan_path(full)

        print(f'packing {cfg.path.initrd}')

        archive = command(
            "bsdcpio", "-0", "-o", "-H", "newc",
            stdin=b'\0'.join(scan_path(b'.')) + b'\0',
            capture_stdout=True,
            env={"LANG": "C"},
        )

        os.chdir(old_cwd)
        del old_cwd

        print(f"uncompressed CPIO: {len(archive)} bytes")

        compressor_cmd = compressor or cfg.packing.compressor
        compressed = command(
            f"pv -s {len(archive)} | {compressor_cmd}",
            shell=True,
            stdin=archive,
            capture_stdout=True
        )
        print(f"compressed CPIO: {len(compressed)} bytes")

        output_filename = output_file or cfg.path.cpio
        with open(output_filename, "wb") as cpiofile:
            cpiofile.write(compressed)

        # install the stiefelos initrd image
        # only possible if it was created (debootstrapped) already.
        stiefelos.install(prefix, cfg)
