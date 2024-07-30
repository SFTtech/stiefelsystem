"""
stiefelsystem client code.
this tool connects to a stiefel-server.
"""

import base64
import hashlib
import hmac
import io
import json
import os
import socket
import struct
import subprocess
import sys
import tarfile
import time
import urllib.request

from .crypto import encrypt, decrypt
from .subcommand import Subcommand


class Client(Subcommand):
    """
    Run stiefelsystem in server mode.
    """

    @classmethod
    def register(cls, cli):
        cli.add_argument("-c", "--config",
                         help="path to config file")
        cli.add_argument("--no-nbd", action="store_true",
                         help="do not generate a config file for nbd-server")
        cli.add_argument("--add-cmd",
                         help="arguments to add to the served cmdline")
        cli.add_argument("cmdline", nargs="+",
                         help="cmdline args. by default, is /proc/cmdline contents")
        cli.set_defaults(subcommand=cls)


    def run(self, args, cfg):
        """
        create an initrd suitable for running stiefel-server or stiefel-client
        """

        ensure_root()

        print(f"reading config from kernel cmdline")

        if args.cmdline:
            cmdlinerawargs = args.cmdline
        else:
            with open('/proc/cmdline') as cmdlinefile:
                cmdline = cmdlinefile.read()
                cmdlinerawargs = cmdline.strip().split()

        cmdlineargs = {}
        for entry in cmdlinerawargs:
            try:
                key, value = entry.split('=', maxsplit=1)
                cmdlineargs[key] = value
            except ValueError:
                continue

        print(f"config: {cmdlineargs}")

        with open('/aes-key', 'rb') as keyfile:
            KEY = keyfile.read()
        KEY_HASH = hashlib.sha256(KEY).hexdigest().encode()
        AUTOKEXEC_HMAC_KEY = hashlib.sha256(b'autokexec-reboot/' + KEY).hexdigest().encode()

        # server discovery loop
        DISCOVERY_PORT = 61570
        NAMEINFO_FLAGS = socket.NI_NUMERICHOST
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        SERVER = None
        SERVER_INTERFACE = None
        NEED_LUKS = None

        while SERVER is None:
            # set interfaces up and send discovery messages
            for netdev in os.listdir('/sys/class/net'):
                try:
                    with open(f'/sys/class/net/{netdev}/operstate') as state_file:
                        state = state_file.read().strip()

                    if state == 'down':
                        print(f"setting link up: {netdev!r}")
                        subprocess.check_call(['ip', 'link', 'set', 'up', netdev])
                    elif state == 'up':
                        with open(f'/sys/class/net/{netdev}/ifindex') as index_file:
                            idx = int(index_file.read().strip())

                        print(f"broadcasting stiefelsystem discovery message to {netdev!r}")

                        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, idx)
                        sock.sendto(
                            b"stiefelsystem:discovery:find-server:" + KEY_HASH,
                            (f"ff02::1", DISCOVERY_PORT)
                        )
                except BaseException as exc:
                    print(f'problem with link {netdev!r}: {exc!r}')

            # receive replies
            timeout = time.monotonic() + 1.0
            while True:
                remaining = timeout - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    break
                host, _ = socket.getnameinfo(addr, NAMEINFO_FLAGS)

                try:
                    if data == b"stiefelsystem:discovery:server-hello:" + KEY_HASH:
                        # test if we can talk to the server on HTTP
                        SERVER_HTTP_URL = f"http://[{host.replace('%', '%25')}]:4644"
                        print(f'fetching {SERVER_HTTP_URL}')
                        request = urllib.request.urlopen(SERVER_HTTP_URL, timeout=1)
                        meta = json.loads(request.read().decode('utf-8'))
                        if meta['what'] != 'stiefelsystem-server':
                            raise ValueError("not a stiefelsystem server!")
                        SERVER_CHALLENGE = meta['challenge']
                        if meta['key-hash'] != KEY_HASH.decode():
                            raise ValueError("wrong key hash")
                        SERVER = host
                        SERVER_INTERFACE = host.split('%')[1]
                        NEED_LUKS = meta.get("need-luks")
                        with open(f'/sys/class/net/{SERVER_INTERFACE}/address') as mac_file:
                            CLIENT_INTERFACE_MAC = mac_file.read().strip()
                        break
                    elif data.startswith(b'stiefelsystem:discovery:autokexec-hello:' + KEY_HASH):
                        # solve the challenge
                        print(f'activating autkexec on {host!r}')
                        challenge = data.split(b':')[-1]
                        response = hmac.new(AUTOKEXEC_HMAC_KEY, challenge, digestmod='sha256').hexdigest()
                        sock.sendto(
                            b'stiefelsystem:discovery:autokexec-reboot:' + KEY_HASH +
                            b':' + response.encode(),
                            addr
                        )

                except BaseException as exc:
                    print(f"server {host!r} is broken: {exc!r}")

        boot_req_args = dict()

        if NEED_LUKS:
            # use systemd-tty-ask-password-agent
            # and wait for input
            luks_phrase = subprocess.check_output([
                'systemd-ask-password',
                'stiefelsystem root block device luks password'
            ]).strip()

            luks_enc = encrypt(KEY, luks_phrase)
            del luks_phrase
            boot_req_args["lukspw"] = base64.b64encode(luks_enc).decode()

        # challenge which the server will included in the requested tar file.
        # by it we make sure we get a fresh archive just for us.
        challenge = base64.b64encode(os.urandom(16)).decode()

        boot_req_args["challenge"] = challenge
        requrl = f"{SERVER_HTTP_URL}/boot.tar.aes"
        reqdata = json.dumps(boot_req_args).encode()
        print(f'fetching {requrl}')

        with urllib.request.urlopen(requrl, reqdata) as bootreq:
            blob = bootreq.read()

        if len(blob) < 32:
            raise ValueError("corrupted boot.tar.aes")

        print('decrypting boot.tar.aes')
        tar_blob = decrypt(KEY, blob)
        print('decryption done')

        stiefelmodules = []

        # cmdline arguments for the to-be-stiefeled kernel
        # these are supplied by stiefel-server.
        inner_cmdline = ''

        with io.BytesIO(tar_blob) as tarfileobj:
            with tarfile.open(fileobj=tarfileobj, mode='r') as tar:
                # validate challenge response
                with tar.extractfile(tar.getmember('challenge')) as fileobj:
                    challenge_response = fileobj.read().decode()
                    if challenge_response != challenge:
                        print(f"challenge response: {challenge_response}")
                        print(f"expected response: {challenge}")
                        raise ValueError('bad challenge response - replay attack?')

                # extract this tar file
                for member in tar.getmembers():
                    with tar.extractfile(member) as fileobj:
                        data = fileobj.read()
                    print(f'    {member.name}: {len(data)} bytes')
                    if member.name == 'challenge':
                        continue
                    elif member.name == 'cmdline':
                        # cmdline for the kexec'd real kernel
                        inner_cmdline = data.decode().strip()
                    elif member.name == 'stiefelmodules':
                        # cmdline for the kexec'd real kernel
                        stiefelmodules = data.decode().split(" ")
                    else:
                        with open(f'/{member.name}', 'wb') as fileobj:
                            fileobj.write(data)

        print('stiefelmodules:\n%s' % "\n".join(stiefelmodules))
        print('inner cmdline from stiefel-server:\n%s' % "\n".join(inner_cmdline.split()))

        # additional inner cmdline arguments given to the stiefel-client-kernel-cmdline
        inner_cmdline += ' ' + base64.b64decode(cmdlineargs.get("stiefel_innercmdline", "")).decode()


        if any(mod in stiefelmodules for mod in ('system-debian', 'system-arch')):
            CMDLINE = (
                inner_cmdline +
                " stiefel_nbdhost=" + SERVER.replace(SERVER_INTERFACE, "stiefellink") +
                " stiefel_nbdname=stiefelblock" +  # name is hardcoded in stiefel-server
                " stiefel_link=" + CLIENT_INTERFACE_MAC
            )

        elif any(mod in stiefelmodules for mod in ('system-gentoo', 'system-arch-dracut')):
            # dracut nbd & network invocation from man dracut.cmdline:
            # netroot=nbd:srv:export[:fstype[:rootflags(fsflags)[:nbdopts]]]
            # pls sync with test-qemu
            CMDLINE = (
                inner_cmdline +
                " ifname=stiefellink:" + CLIENT_INTERFACE_MAC +
                " ip=stiefellink:link6" +
                " netroot=nbd:[" + SERVER.replace(SERVER_INTERFACE, "stiefellink") + "]:stiefelblock:::-persist"
            )
        else:
            raise Exception("with the given stiefelsystem modules, "
                            "couldn't construct kexec cmdline")

        print("booting into received kernel, cmdline:")
        for cmd in CMDLINE.split():
            print(f"{cmd!r}")

        kexec_invoc = ['kexec', '/kernel', '--ramdisk=/initrd', '--command-line=' + CMDLINE]
        print('running kexec: %s' % kexec_invoc)
        subprocess.check_call(kexec_invoc)
