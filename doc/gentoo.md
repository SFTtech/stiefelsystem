# Gentoo

## Dependencies

```
emerge -avt debootstrap kexec-tools dosfstools nbd[netlink] pigz pv pyudev pyyaml syslinux wireless-tools
```

## Setup notes

Enable the stiefelsystem `system-gentoo` module!

Your Gentoo needs an initrd built with **dracut** with the following modules:
- `dracut-systemd` - use systemd as initrd driver
- `network-manager` - bring up the stiefel network via networkmanager
- don't use `systemd-networkd` - it does not connect the nbd yet (`netroot` is ignored?)

If your `nbd-client` does not have `netlink` support, it will be killed when your initrd switches root to the on-network block device, and then make the root fs unavailable. Hours on debugging were invested why this happens (because `nbd-client` should not be killed if it has [`argv[0][0] == '@'`](https://systemd.io/ROOT_STORAGE_DAEMONS )), but with `netlink` it survives the root switch.
