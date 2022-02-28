#!/bin/bash
check() {
	require_binaries wg || return 1
	# only include if specified
	return 255
}

depends() {
	echo network
}

installkernel() {
		instmods wireguard
}

install() {
		inst wg
		inst_hook initqueue/settled 20 "$moddir/stiefel.sh"
		if dracut_module_included "systemd-initrd"; then
        	inst_script "$moddir/wireguard-generator.sh" "$systemdutildir"/system-generators/dracut-wireguard-generator
		fi
		dracut_need_initqueue
}
