# Arch Linux

## Dependencies

```
pacman -S debootstrap kexec-tools dosfstools nbd pigz pv python-pyudev python-yaml syslinux wireless_tools mtools gdisk
```

Only required for debugging with `test-qemu`:
```
pacman -S qemu
```

If you want to use lvm in `test-qemu`:
```
pacman -S lvm2
```

## Setup notes

If you use mkinitcpio: Enable the `system-arch` module!

If you use dracut: Enable the `system-arch-dracut` module!
If you use dracut with the `network-manager` module, `networkmanager` must be installed on the system.
To verify which networking solution you are using, use `lsinitrd` on your initramfs and look for `network-manager`, `systemd-network`, `network-wicked` or `network-legacy`
