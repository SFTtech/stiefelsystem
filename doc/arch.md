# Arch Linux

## Dependencies

```
pacman -S debootstrap kexec-tools dosfstools nbd pigz pv python-pyudev python-yaml syslinux wireless_tools mtools gdisk
```

Only required for debugging with test-qemu:
```
pacman -S qemu
```

## Setup notes

If you use mkinitcpio: Enable the `system-arch` module!

If you use dracut: Enable the `system-arch-dracut` module!
