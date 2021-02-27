# What?

Allows you to boot your (or anyone's really) desktop PC with the exact same
hard disk that your laptop is running from, basically exactly as if you'd
unscrew the SSD from your laptop and plug it into the desktop.

The data transfer to the hard disk goes over a network link.

# Why?

I don't like maintaining multiple operating systems and associated home
folders.

On the other hand, I like being able to simply use the comfort and power of a
desktop PC if I encounter one.

Unfortunately, on my laptop it takes longer than 3 seconds to unscrew the SSD,
so I wrote this.

# How?

The laptop acts as the server.
It first provides the initrd/kernel via HTTP,
and then the entire block device for its main disk via NBD.
A dedicated high-speed network link is recommended for this (henceforth referred to as: stiefellink).

I'm using a RTL8156-based 10/100/1G/2.5G USB3.2 NIC on both sides, in a point-to-point topology.
The OS cannot be running on the laptop while it serves the disk, for obvious reasons.
Thus, when the stiefellink NIC is detected by the stiefel-autokexec service, the laptop reboots into
a custom ramdisk which acts as the stiefelsystem server that provides the aforementioned services.
Configuration (IP addresses, block device identifiers, ...) is passed to this server through its kernel cmdline.
The stiefelsystem server will set up the network on stiefellink and wait for requests.

On the desktop PC, a minimal stiefelsystem client ramdisk is booted from a USB flash drive;
again, the configuration comes from the kernel cmdline.
Apart from the cmdline, the ramdisk is actually identical to the server ramdisk.
The steifelsystem client will search for the server on all of its network interfaces until it receives
a correct reply. Once it does, it requests the kernel and initrd that it shall boot, and kexec's into them.
The target system will use a nbd hook in its own initrd to mount the root partition, then boot as usual.

Authentication, encryption and MITM protection happens through a shared symmetric key and AES-EAX.
Your nbd connection itself is unencrypted and unauthenticated, so I strongly recommend a
point-to-point connection and not enabling IP forwarding.

```
time
|
|
| laptop computer                           desktop computer
| regular OS                            boot from usb stick or PXE
|    |                                            |
| autokexec service                               |
v    |              discovery message             |
     |<---------------------<---------------------+
     |                                            |
  reboot to stiefel-server system (kexec)         |
     |                                            |
     |            request kernel + initrd         |
     |<---------------------<---------------------+
     |                                            |
     |            send kernel + initrd            |
     +---------------------->-------------------->|
     |                                    kexec to received kernel
     |                               and network-root compatible initramfs
  serve root block device                         |
     |             map/mount root fs              |
     |<---------------------<---------------------+
     |                                            |
     |                                    switch root and enjoy!
     |               rootfs requests              |
     |<---------------------<---------------------+
     v                                            v
```

# How to?

You need to

- think of your configuration (in `config.yaml`)
- create the stiefelsystem ramdisk (for use by server and client)
- setup the stiefel-autokexec service on the laptop (and provide it with the ramdisk and config)
- setup the nbd hook on your OS
- create the USB boot flash drive (and provide it with the ramdisk and config)

The scripts in this repo automate all of those task (apart from the thinking...)

- `cp config-example.yaml config.yaml` and edit it to your wishes. Select the modules that are appropriate for your system.
- `sudo ./create-initrd` prepares the debian-based initrd, as a folder and as an archive
- you can check out the initrd with `sudo ./test-nspawn`
- you can check out server and client interactions with `sudo ./test-qemu server` and `sudo ./test-qemu client`
- `sudo ./setup-server-os` sets up your system, asking for permission for every operation. It sets up:
  - the stiefel-autokexec service
  - an initrd that can mount your root disk from the network
  - a network manager rule to disable control of the stiefellink
- `sudo ./setup-client-usbdrive` creates the usb drive
- `rm aes-key` to reset the AES key (newly created ramdisks won't work with older ones)

# Why don't you use X in the tech stack?

I tried X and it sucks.

(for some values of X, including but not limited to:)

- iSCSI (super-slow compared to `nbd`, and overly complicated)
- PXE (doesn't support my 2.5GBaseT USB NIC)

# Why don't you use Y in the tech stack?

I'd really like to use Y, but you haven't implemented support yet.

# TODO

## Creation scripts

- Unify create-initrd-nspawn and create-initrd-cpio
- Allow skipping some of the more time-consuming parts of create-initrd-nspawn
- setup-client-usbdrive: add a script to launch the client script in any linux's userland

## Network setup

- Allow enabling jumbo frames (8192 bytes?) for higher throughput with bigger files
- Run a DHCP server on the server (possibly also with PXE support) and support DHCP config on the client
- Allow server to request earlyboot crypto passphrase from the client in its / HTTP GET answer

## Client script

- Search for the server on all network interfaces in parallel, with multiprocessing and network namespaces

## Server script

- Produce warning beeps if not on AC power, especially when battery is low
- Re-setup interfaces as they disappear/appear
