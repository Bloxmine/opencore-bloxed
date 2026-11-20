#!/bin/zsh --no-rcs
# ------------------------------------------------------
# Builds and signs opencore-bloxed (run in Terminal)
# ------------------------------------------------------
# Unlocks the signing keychain from setup.sh (asks for its
# password), rebuilds the privileged helper, builds the app
# and packages signed with the fork's key, checks that the
# helper accepts the app, and locks the keychain again.
#
# Output: dist/OpenCore-Patcher.pkg (install it on each Mac)
# ------------------------------------------------------

set -euo pipefail

identity="opencore-bloxed Code Signing"
keychain="$HOME/Library/Keychains/opencore-bloxed-signing.keychain-db"
repo="${0:A:h:h:h}"
helper="$repo/ci_tooling/privileged_helper_tool/com.dortania.opencore-legacy-patcher.privileged-helper"
python="$repo/.venv/bin/python"
[[ -x $python ]] || python=python3

[[ -e $keychain ]] || { echo "No signing keychain; run ci_tooling/signing/setup.sh first."; exit 1; }
/usr/bin/security unlock-keychain "$keychain"
trap '/usr/bin/security lock-keychain "$keychain"' EXIT

cd "$repo"
/usr/bin/make -C ci_tooling/privileged_helper_tool >/dev/null
OCLP_TARGET_ARCH=x86_64 "$python" Build-Project.command --application-signing-identity "$identity" --git-branch main

# The helper accepts a client signed with its own leaf certificate (see privileged_helper_tool/main.m)
leaf=$(/usr/bin/openssl x509 -in ci_tooling/signing/opencore-bloxed.pem -noout -fingerprint -sha1 | cut -d= -f2 | tr -d : | tr A-F a-f)
for code in "$helper" "dist/OpenCore-Patcher.app/Contents/MacOS/OpenCore-Patcher"; do
    /usr/bin/codesign --verify --strict -R="certificate leaf = H\"$leaf\"" "$code"
done
echo "Signed with \"$identity\"; the helper accepts the app. Install dist/OpenCore-Patcher.pkg."
