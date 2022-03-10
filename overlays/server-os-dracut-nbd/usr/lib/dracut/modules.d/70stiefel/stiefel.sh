#!/bin/sh

# do nothing if there is no config
# do nothing if the interface already exits
if [ -f /etc/wireguard/wgstiefel.conf ] && ! [ -d /sys/class/net/wgstiefel ]; then
    ip link add dev wgstiefel type wireguard
    wg setconf wgstiefel /etc/wireguard/wgstiefel.conf
    ip addr add fe80::2/64 dev wgstiefel
    ip link set wgstiefel up
fi