#!/bin/bash
# Makes the certificates that let phones open the kit over https, which phones need
# before they let a web page use their GPS. Run by share-library.sh on every start;
# it only does work the first time, or when the Mac's address on the Wi-Fi has changed.
#
#   tools/certs/ca.crt       this kit's own certificate authority, installed once on each phone
#   tools/certs/server.crt   the kit's https certificate, signed by that authority
#
# The authority is made on this Mac, never leaves it except as the public ca.crt, and is
# limited (name constraints) to local addresses: *.local and home-network IP numbers.
# So even if its key leaked, it could not be used to impersonate any internet site.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"
KIT_NAME=$(country kit_name)
C="$KIT/tools/certs"
SSL=/usr/bin/openssl   # macOS's own LibreSSL, present on every Mac
mkdir -p "$C"
chmod 700 "$C"

NAME=$(scutil --get LocalHostName 2>/dev/null || hostname -s)
IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1 || echo 127.0.0.1)

if [ ! -f "$C/ca.key" ] || [ ! -f "$C/ca.crt" ]; then
  cat > "$C/ca.cnf" <<EOF
[req]
distinguished_name = dn
prompt = no
x509_extensions = v3_ca
[dn]
CN = $KIT_NAME @ $NAME
O = $KIT_NAME
[v3_ca]
basicConstraints = critical, CA:true, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
nameConstraints = critical, permitted;DNS:.local, permitted;DNS:localhost, permitted;IP:192.168.0.0/255.255.0.0, permitted;IP:10.0.0.0/255.0.0.0, permitted;IP:172.16.0.0/255.240.0.0, permitted;IP:127.0.0.0/255.0.0.0
EOF
  "$SSL" genrsa -out "$C/ca.key" 2048 2>/dev/null
  chmod 600 "$C/ca.key"
  "$SSL" req -x509 -new -key "$C/ca.key" -sha256 -days 3650 -config "$C/ca.cnf" -out "$C/ca.crt"
  rm -f "$C/server.crt"
  say "Створено сертифікат для GPS телефона" "Made the certificate for the phone's GPS"
fi

# The https certificate must name this Mac and its current address; renew it if not.
if [ -f "$C/server.crt" ] && "$SSL" x509 -in "$C/server.crt" -noout -text | grep -q "IP Address:$IP\b" \
   && "$SSL" x509 -in "$C/server.crt" -noout -checkend 2592000 >/dev/null; then
  exit 0
fi
cat > "$C/server.cnf" <<EOF
[req]
distinguished_name = dn
prompt = no
[dn]
CN = $NAME.local
[ext]
basicConstraints = critical, CA:false
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:$NAME.local, DNS:localhost, IP:$IP, IP:127.0.0.1
EOF
"$SSL" genrsa -out "$C/server.key" 2048 2>/dev/null
chmod 600 "$C/server.key"
"$SSL" req -new -key "$C/server.key" -config "$C/server.cnf" -out "$C/server.csr"
# 800 days: Apple devices refuse https certificates that last longer than 825 days.
"$SSL" x509 -req -in "$C/server.csr" -CA "$C/ca.crt" -CAkey "$C/ca.key" -CAcreateserial -sha256 -days 800 \
  -extfile "$C/server.cnf" -extensions ext -out "$C/server.crt" 2>/dev/null
rm -f "$C/server.csr"
