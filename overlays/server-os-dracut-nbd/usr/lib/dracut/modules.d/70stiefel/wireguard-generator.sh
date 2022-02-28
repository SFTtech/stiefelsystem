#!/bin/sh

type getarg > /dev/null 2>&1 || . /lib/dracut-lib.sh

# wg.privkey=XXXXXXXXX wg.endpoint=server:port wg.pubkey=pubkey [wg.allowed_ips=xxxxxxx]

[ -z "$PUB_KEY" ] && PUB_KEY=$(getarg wg_pubkey=)
[ -z "$PRIV_KEY" ] && PRIV_KEY=$(getarg wg_privkey=)
[ -z "$SERVER" ] && SERVER=$(getarg wg_endpoint=)
[ -z "$ALLOWED_IPS" ] && ALLOWED_IPS=$(getarg wg_allowed_ips=)

! [ -n "$PRIV_KEY" ] || ! [ -n "$PUB_KEY" ] || ! [ -n "$SERVER" ] && exit 1
! [ -n "$ALLOWED_IPS" ] && ALLOWED_IPS="fe80::/64"

mkdir /etc/wireguard
{
	echo "[Interface]"
	echo "PrivateKey = $PRIV_KEY"
	echo ""
	echo "[Peer]"
	echo "PublicKey = $PUB_KEY"
	echo "Endpoint = $SERVER"
	echo "AllowedIPs = $ALLOWED_IPS"
} > /etc/wireguard/wgstiefel.conf

exit 0
