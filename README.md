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
You can of course still access an additional storage device in the Desktop computer.

To make this work, the "server system" (your Laptop) provides the operating system kernel and base system over the network to the "client system" (your Desktop computer).
The base system on the client then connects to the server again and maps the whole storage device (the SSD, mapped with NBD), and then uses it as root filesystem.

Of course this works between any two devices.


## Communication Flow


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

More information can be found in our [more detailed documentation](doc/procedure.md).


# How to?

## Dependencies

* [Arch Linux](doc/arch.md)
* [Debian](doc/debian.md)
* [Gentoo](doc/gentoo.md)


## Setup

Basic steps (commands below):

- You create a Debian-based OS image which is booted on client and server
- This image is flashed on an USB drive, which is used to boot the client
- The same system is kexec'd on your server to serve the root disk


The scripts in this repo automate all of those task (apart from the thinking...)

- Make shure you have all dependencies installed
  * `cp config-example.yaml config.yaml` and edit it to your wishes.
  * Select the modules that are appropriate for your system.
- create the stiefelsystem ramdisk (for use by server and client)
  * `sudo ./create-initrd` prepares the debian-based initrd, as a folder and as an archive
  * You can check out the initrd with `sudo ./test-nspawn`
  * You can check out server and client interactions with `sudo ./test-qemu server` and `sudo ./test-qemu client`

- Setup the `stiefel-autokexec` service on the laptop (and provide it with the ramdisk and config) and setup the nbd rootfs hook in your initfs on your OS
  * `sudo ./setup-server-os` sets up your system, asking for permission for every operation. It sets up:
    * The `stiefel-autokexec.service`
    * Initrd hooks that can mount your root disk from the network
    * A network manager rule to disable control of the network partition network device
- Create a USB boot drive
  * `sudo ./setup-client-usbdrive /dev/sdxxx` creates the usb drive

- To reset the AES key, run `rm aes-key` (newly created ramdisks won't work with older ones)


# Why don't you use X in the tech stack?

We tried X and it sucks.

(for some values of X, including but not limited to:)

- iSCSI (super-slow compared to `nbd`, and overly complicated)
- PXE (unreliable, USB sticks worked better, but we may revisit :)

# Why don't you use Y in the tech stack?

We'd really like to use Y, but you haven't implemented support yet.


# Things to improve

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
