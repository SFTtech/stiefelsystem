#!/bin/sh

type getarg > /dev/null 2>&1 || . /lib/dracut-lib.sh
type getargbool > /dev/null 2>&1 || . /lib/dracut-lib.sh

# wg.privkey=XXXXXXXXX wg.endpoint=server:port wg.pubkey=pubkey [wg.allowed_ips=xxxxxxx]
if ! getargbool 0 stiefel; then
  exit 1
fi

[ -z "$PUB_KEY" ] && PUB_KEY=$(getarg wg.pubkey=)
[ -z "$PRIV_KEY" ] && PRIV_KEY=$(getarg wg.privkey=)
[ -z "$SERVER" ] && SERVER=$(getarg wg.endpoint=)
[ -z "$ALLOWED_IPS" ] && ALLOWED_IPS=$(getarg wg.allowed_ips=)

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

{
  echo '#!/bin/sh'
  echo 'if [ $(cat /sys/class/net/wgstiefel/carrier) ]; then'
  echo '  exit 0'
  echo 'else'
  echo '  exit 1'
  echo 'fi'
} > "$hookdir"/initqueue/finished/wg.sh
exit 0
