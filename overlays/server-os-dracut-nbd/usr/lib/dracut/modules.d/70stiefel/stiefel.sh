#!/bin/sh

[ -f /etc/wireguard/wgstiefel.conf ] || exit 1

ip link add dev wgstiefel type wireguard
wg setconf wgstiefel /etc/wireguard/wgstiefel.conf
ip addr add fe80::2/64 dev wgstiefel
ip link set wgstiefel up

