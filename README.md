# Stiefelsystem

The *Stiefelsystem* allows you to use your computer as a **bootable** storage device **for another computer**, you just need a **network connection** between both.

For proper functionality your system has to be compatible with both devices seamlessly, hence this tool is optimized for **Linux**.

Unfortunately, it takes longer than 3 seconds to unscrew the SSD of a Laptop and connect it to the desktop PC, so we wrote this software :smile_cat:

Needed components:
- A computer serving a storage device to to boot from
- Another computer whose CPU/GPU you actually want to use
- A network connection between both
- A USB stick to bootstrap your other computer's startup (no PXE yet)


## How?

Instead of unscrewing your SSD of a Laptop and putting it in a Desktop computer to start it there, the *Stiefelsystem* boots up the same system over network while fetching/storing all system files from the Laptop.
Since your system is really running on the desktop, you can of course still access an additional storage device and other hardware installed in the Desktop computer (VR Headsets, ...).

It works like this: The "server system" (your Laptop) provides the operating system kernel and bootstrapping system over the network to the "client system" (your Desktop computer).
The bootstrapping system on the client then connects to the server again and mapps the whole storage device (your SSD, mapped with NBD), and then mounts it as root filesystem.

Now you have one computer serving as network disk, the other having that network disk mounted and running on it.


## Communication Flow


```
time
|
|
| laptop computer                           desktop computer
| regular OS                            boot live system from USB or PXE
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

More information can be found in our [more detailed documentation](doc/procedure.md).


# How to?

## Dependencies

* [Arch Linux](doc/arch.md)
* [Debian](doc/debian.md)
* [Gentoo](doc/gentoo.md)


## Setup

Gist:

- We create a debian based boostrapping system image
- We flash this image on an USB drive, which is used to boot the client
- The same boostrapping image is kexec'd on your server to serve the root disk over network

Steps:
- visit the config file, but all defaults should be good to go
  - the suitable defaults should be set by your Linux distribution in this file!
- `sudo stiefelctl update`: update the bootstrap image
- `sudo stiefelctl create-usbdrive /dev/sdxxx`: flash client boot usb thumbdrive with bootstrap image
- `sudo stiefelctl server`: wait until client connects to serve disks
  - or, enable/run `stiefelsystem.service` which just runs `stiefelctl server`

## Development

- `stiefelctl test-nspawn` to test the stiefelOS image
- `stiefelctl test-qemu <client|server>` to test client-server interactions with virtual machines

- To your secret key, remove `aes-key` at the location specified in the config.


# Why don't you use X in the tech stack?

We tried X and it sucks.

(for some values of X, including but not limited to:)

- iSCSI (super-slow compared to `nbd`, and overly complicated)
- PXE (unreliable, USB sticks worked better, but we may revisit :)

# Why don't you use Y in the tech stack?

We'd really like to use Y, but you haven't implemented support yet.


# Things to improve

## Network setup

- Allow enabling jumbo frames (8192 bytes?) for higher throughput with bigger files
- Run a DHCP server on the server (possibly also with PXE support) and support DHCP config on the client

## StiefelOS Client

- Search for the server on all network interfaces in parallel, with multiprocessing and network namespaces

## StiefelOS Server

- Produce warning beeps if not on AC power, especially when battery is low
- Re-setup interfaces as they disappear/appear
