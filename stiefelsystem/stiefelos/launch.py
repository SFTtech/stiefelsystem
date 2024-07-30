#!/usr/bin/env python3

"""
Code for generating an initrd system capable of running as stiefel-server
or stiefel-client. So it's used to serve the disk over network, or chain-load
into the server's OS.
"""

import argparse
import base64
import hmac
import multiprocessing
import os
import socket

from ..util import command
from ..subcommand import Subcommand


class StiefelOSLauncher(Subcommand):
    """
    Wait for a discovery message to launch StiefelOS
    """

    @classmethod
    def register(cls, cli):
        sp = cli.add_subparsers(dest="launchmode")
        sp.required = True

        commonp = argparse.ArgumentParser(add_help=False)
        commonp.add_argument('--now', action='store_true',
                             help="launch StiefelOS now, don't wait for a trigger")

        serverp = sp.add_parser("server", parents=[commonp])
        clientp = sp.add_parser("client", parents=[commonp])

        cli.set_defaults(subcommand=cls)

    def run(self, args, cfg):
        self.cfg = cfg

        if os.path.exists('/sys/class/net/stiefellink'):
            print("won't kexec since this is already a stiefeled system. "
                  "we assume it's stiefeled because of the 'stiefellink' network interface.")
            return

        if args.launchmode == "server":
            self.launch_server(args)
        elif args.launchmode == "client":
            self.launch_client(args)
        else:
            raise Exception(f"invalid launchmode {args.launchmode}")

    def launch_client(args):
        if args.now:
            raise NotImplementedError("launching stiefelOS client via kexec not yet supported")
            # self.do_kexec_client()
        else:
            raise Exception("no client launch triggers available, use --now.")

    def launch_server(args):
        if args.now:
            self.do_kexec_server()
            return

        if not self.cfg.autokexec.macs and not self.cfg.autokexec.broadcast:
            print("no trigger-based launch method enabled. maybe use --now?")
            return

        with open(self.cfg.aes_key_location, 'rb') as keyfileobj:
            aeskey = keyfileobj.read()

        if self.cfg.autokexec.broadcast:
            aes_key_hash = hashlib.sha256(aeskey).hexdigest().encode()
            hmac_key = hashlib.sha256(b'autokexec-reboot/' + aeskey).hexdigest().encode()
            multiprocessing.Process(
                target=self.kexec_on_server_discovery_message,
                args=(aes_key_hash, hmac_key)
            ).start()

        if self.cfg.autokexec.macs:
            self.kexec_on_adapter_found(self.cfg.autokexec.macs)

    def kexec_on_adapter_found(self, adapters):
        print('waiting for one of these adapters:')
        for mac in adapters:
            print(f'  {mac}')

        import pyudev
        context = pyudev.Context()
        udev_monitor = pyudev.Monitor.from_netlink(context)
        udev_monitor.filter_by(subsystem='net')
        while True:
            # test if we have the adapter now
            for netif in os.listdir('/sys/class/net'):
                with open(f'/sys/class/net/{netif}/address') as addrfile:
                    mac = addrfile.read().strip()
                    if mac in adapters:
                        print(f"adapter found: {mac}")
                        self.do_kexec_server()

            # wait until something happens
            udev_monitor.poll()

    def kexec_on_server_discovery_message(self, aes_key_hash, hmac_key):
        discovery_port = 61570  # determined by random.choice(range(49152, 2**16))
        nameinfo_flags = socket.NI_NUMERICHOST

        challenge = base64.b64encode(os.urandom(16))

        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', discovery_port))
        # allow multicast loopback for development
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)

        print("kexec-on-server-discovery-message: listening for messages")
        while True:
            data, addr = sock.recvfrom(1024)
            if data == b'stiefelsystem:discovery:find-server:' + aes_key_hash:
                host, _ = socket.getnameinfo(addr, nameinfo_flags)
                print(f"{host!r} is looking for a stiefelsystem server! challenging it...")
                try:
                    sock.sendto(
                        b'stiefelsystem:discovery:autokexec-hello:' + aes_key_hash +
                        b':' + challenge, addr
                    )
                except BaseException as exc:
                    print(f"cannot send discovery reply: {exc!r}")
            elif data.startswith(b'stiefelsystem:discovery:autokexec-reboot:' + aes_key_hash + b':'):
                response = data.split(b':')[-1]
                if hmac.compare_digest(
                    response,
                    hmac.new(hmac_key, challenge, digestmod='sha256').hexdigest().encode()
                ):
                    # this reboot request is authentic, it solved our challenge
                    self.do_kexec_server()
                else:
                    print(f'bad HMAC signature for autokexec-reboot challenge')

    def do_kexec_server(self):
        print(f'booting into stiefelsystem server')

        cmdline = [
            f'systemd.unit=stiefel-server.service',
            f'stiefel_bootdisk={self.cfg.boot.disk}',
            f'stiefel_bootpart={self.cfg.boot.part}',
        ]

        bootpart_luks = self.cfg.boot.luks_block
        if bootpart_luks is not None:
            cmdline.append(
                f'stiefel_bootpart_luks={bootpart_luks}'
            )

        cmdline.extend(config.get("cmdline", []))

        command(
            'kexec',
            self.cfg.server_setup.stiefel_os_kernel,
            '--ramdisk=' + self.cfg.server_setup.stiefel_os_initrd,
            '--reset-vga',
            '--console-vga',
            '--command-line=' + ' '.join(self.cfg.server_setup.cmdline)
        )
