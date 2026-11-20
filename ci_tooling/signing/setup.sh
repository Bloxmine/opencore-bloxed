#!/bin/zsh --no-rcs
# ------------------------------------------------------
# opencore-bloxed signing key setup (run once, in Terminal)
# ------------------------------------------------------
# Creates a self-signed code-signing certificate and its
# private key in a separate keychain, locked with a
# password you choose. The fork's privileged helper only
# runs root commands for apps signed with this key.
#
# The keychain locks itself after 10 minutes idle and on
# sleep. Nothing is added to your trusted certificates.
# ------------------------------------------------------

set -euo pipefail

identity="opencore-bloxed Code Signing"
keychain="$HOME/Library/Keychains/opencore-bloxed-signing.keychain-db"
here="${0:A:h}"

if [[ -e $keychain ]]; then
    echo "$keychain already exists; delete it first to make a new key (apps signed with the old key stop working)."
    exit 1
fi

read -rs "password?Password for the new signing keychain: "; echo
read -rs "confirm?Repeat it: "; echo
[[ -n $password && $password == $confirm ]] || { echo "Passwords are empty or don't match."; exit 1; }

work=$(mktemp -d)
trap '/bin/rm -rf "$work"' EXIT
umask 077

cat > "$work/cert.cnf" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $identity
[ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
EOF

/usr/bin/openssl req -x509 -newkey rsa:3072 -sha256 -days 7300 -nodes \
    -keyout "$work/key.pem" -out "$work/cert.pem" -config "$work/cert.cnf" 2>/dev/null
transfer=$(/usr/bin/openssl rand -hex 24)
/usr/bin/openssl pkcs12 -export -inkey "$work/key.pem" -in "$work/cert.pem" -name "$identity" \
    -out "$work/identity.p12" -passout "pass:$transfer"

/usr/bin/security create-keychain -p "$password" "$keychain"
/usr/bin/security set-keychain-settings -t 600 -l "$keychain"
/usr/bin/security import "$work/identity.p12" -k "$keychain" -P "$transfer" -T /usr/bin/codesign >/dev/null
/usr/bin/security set-key-partition-list -S apple-tool:,apple: -s -k "$password" "$keychain" >/dev/null

# codesign only finds identities in keychains on the search list
existing=("${(@f)$(/usr/bin/security list-keychains -d user | /usr/bin/sed 's/^ *"//; s/"$//')}")
/usr/bin/security list-keychains -d user -s "${existing[@]}" "$keychain"
/usr/bin/security lock-keychain "$keychain"

# The public certificate, for reference (the private key never leaves the keychain)
/bin/cp "$work/cert.pem" "$here/opencore-bloxed.pem"
/bin/chmod 644 "$here/opencore-bloxed.pem"
echo "Created \"$identity\" in $keychain"
echo "Certificate SHA-1: $(/usr/bin/openssl x509 -in "$here/opencore-bloxed.pem" -noout -fingerprint -sha1 | cut -d= -f2)"
