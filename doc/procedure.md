# What?

Stiefelsystem was invented to allow booting your (or anyone's really) desktop PC with the exact same hard disk that your laptop is running from, basically exactly as if you'd unscrew the SSD from your laptop and plug it into the desktop.

The data transfer to the hard disk goes over a ethernet network link, because everyone has that, it's reliable and dead-simple.


# Why?

We don't like to maintain multiple operating systems and associated home folders, but we still want to profit from the speed, comfort and power of a desktop PC if we encounter one.

Unfortunately, on most laptops it takes longer than 3 seconds to unscrew the SSD and connect it to the desktop pc, so we wrote this.


# How?

The laptop acts as the server.
It first provides the initrd/kernel via HTTP,
and then the entire block device for its main disk via NBD.
A dedicated high-speed network link is recommended for this (henceforth referred to as: `stiefellink`).

Ideally, one uses a dedicated point-to-point network connection between both devices.
The OS cannot be running on the laptop in write-mode while it serves the disk to the desktop which also wants to write data.
Thus, when the `stiefellink` NIC is detected by the `stiefel-autokexec.service`, the laptop reboots into a custom ramdisk which acts as the stiefelsystem server that provides the aforementioned services.
Configuration (IP addresses, block device identifiers, ...) is passed to this server through its kernel cmdline.
The stiefelsystem server will set up the network on `stiefellink` and wait for requests.

On the desktop PC, a minimal stiefelsystem client ramdisk is booted from a USB flash drive; again, the configuration comes from the kernel cmdline.
Apart from the cmdline, the client's bootstrap ramdisk is identical to the server ramdisk.
The stiefelsystem client will search for the server on all of its network interfaces until it receives a correct reply.
Once it does, it requests the kernel and initrd that it shall boot, and kexec's into them.
The target system will use a nbd hook in its own initrd to mount the root partition, then boot as usual.

Authentication, encryption and MITM protection happens through a shared symmetric key and AES-EAX.
Your nbd connection itself is unencrypted and unauthenticated, so we strongly recommend a point-to-point connection and not enabling IP forwarding.
