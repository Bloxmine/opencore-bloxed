#!/usr/bin/env bash
# make_recovery_usb.sh: OpenCore Legacy Patcher USB for a legacy Mac, made on Linux
#
# Writes a GPT disk with one FAT32 partition holding:
#   EFI/OC + System/Library/CoreServices/boot.efi   OpenCore built by linux/build_efi.py for the given model
#   com.apple.recovery.boot/                        macOS recovery (Tahoe by default), from Apple via macrecovery.py
#
# Boot the Mac holding Option, pick "EFI Boot", then in OpenCore's picker pick the recovery entry. From recovery you
# can reinstall macOS over the network, or use Terminal / Disk Utility on the installed system.
#
# This is not a full offline installer: Apple's createinstallmedia only runs on macOS.
#
# Usage: sudo linux/make_recovery_usb.sh /dev/sdX [MODEL] [--no-recovery]
#   MODEL defaults to MacBookPro11,1. --no-recovery writes OpenCore only.
#
# ALL DATA ON THE TARGET DEVICE IS ERASED.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE="${1:-}"
MODEL="${2:-MacBookPro11,1}"
RECOVERY=1
for argument in "$@"; do
    [[ "$argument" == "--no-recovery" ]] && RECOVERY=0
done
[[ "$MODEL" == "--no-recovery" ]] && MODEL="MacBookPro11,1"

# Pinned to the OpenCore version OCLP ships (constants.py: opencore_version)
OPENCORE_TAG="$(sed -n 's/.*self.opencore_version: *str *= *"\([0-9.]*\)".*/\1/p' "$REPO/opencore_legacy_patcher/constants.py")"
MACRECOVERY_URL="https://raw.githubusercontent.com/acidanthera/OpenCorePkg/${OPENCORE_TAG}/Utilities/macrecovery/macrecovery.py"
# Board ID and "-os latest" from macrecovery's recovery_urls.txt (Tahoe)
RECOVERY_BOARD_ID="Mac-CFF7D910A743CAAF"

die() { echo "Error: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run with sudo (partitioning needs root)"
[[ -n "$DEVICE" && -b "$DEVICE" ]] || die "usage: sudo $0 /dev/sdX [MODEL] [--no-recovery]"
for tool in lsblk parted mkfs.vfat python3 curl; do
    command -v "$tool" >/dev/null || die "$tool is not installed"
done

# Refuse anything that is not a whole removable disk
[[ "$(lsblk -dno TYPE "$DEVICE")" == "disk" ]] || die "$DEVICE is not a whole disk (give /dev/sdX, not /dev/sdX1)"
NAME="$(basename "$DEVICE")"
REMOVABLE="$(cat "/sys/block/$NAME/removable" 2>/dev/null || echo 0)"
TRANSPORT="$(lsblk -dno TRAN "$DEVICE" || true)"
if [[ "$REMOVABLE" != "1" && "$TRANSPORT" != "usb" ]]; then
    die "$DEVICE is not removable or USB; refusing to erase it"
fi
if lsblk -no MOUNTPOINTS "$DEVICE" | grep -qE '^/(boot|home)?$'; then
    die "$DEVICE holds a system mount point"
fi

echo
lsblk -o NAME,SIZE,TRAN,MODEL,LABEL,MOUNTPOINTS "$DEVICE"
echo
echo "This ERASES everything on $DEVICE and writes OpenCore for $MODEL$([[ $RECOVERY == 1 ]] && echo " + macOS Tahoe recovery")."
read -r -p "Type the device name ($NAME) to continue: " CONFIRM
[[ "$CONFIRM" == "$NAME" ]] || die "not confirmed"

WORK="$(mktemp -d)"
chmod 755 "$WORK"
MOUNT="$WORK/usb"
cleanup() {
    mountpoint -q "$MOUNT" && umount "$MOUNT" || true
    rm -rf "$WORK"
}
trap cleanup EXIT

echo "==> Building OpenCore for $MODEL"
# Build as the invoking user so Build-Folder is not root-owned
BUILD_USER="${SUDO_USER:-root}"
chown "$BUILD_USER" "$WORK"
sudo -H -u "$BUILD_USER" python3 "$REPO/linux/build_efi.py" --model "$MODEL" --output "$WORK/oc" \
    || die "OpenCore build failed"

if [[ $RECOVERY == 1 ]]; then
    echo "==> Downloading macOS recovery (macrecovery.py from OpenCorePkg $OPENCORE_TAG)"
    mkdir -p "$WORK/tools" "$WORK/recovery"
    chown -R "$BUILD_USER" "$WORK/tools" "$WORK/recovery"
    sudo -H -u "$BUILD_USER" curl -fsSL -o "$WORK/tools/macrecovery.py" "$MACRECOVERY_URL"
    (cd "$WORK/recovery" && sudo -H -u "$BUILD_USER" python3 -I "$WORK/tools/macrecovery.py" \
        -b "$RECOVERY_BOARD_ID" -m 00000000000000000 -os latest -o "$WORK/recovery" download) \
        || die "recovery download failed"
fi

echo "==> Partitioning $DEVICE"
for partition in $(lsblk -lno PATH "$DEVICE" | tail -n +2); do
    umount "$partition" 2>/dev/null || true
done
wipefs -a "$DEVICE" >/dev/null
parted -s "$DEVICE" mklabel gpt mkpart OCLP fat32 1MiB 100% set 1 esp on
partprobe "$DEVICE" 2>/dev/null || true
udevadm settle 2>/dev/null || sleep 2
PARTITION="$(lsblk -lno PATH "$DEVICE" | sed -n 2p)"
[[ -b "$PARTITION" ]] || die "partition did not appear"
mkfs.vfat -F 32 -n OCLP "$PARTITION" >/dev/null

echo "==> Copying files"
mkdir -p "$MOUNT"
mount "$PARTITION" "$MOUNT"
cp -r "$WORK/oc/EFI" "$WORK/oc/System" "$MOUNT/"
if [[ $RECOVERY == 1 ]]; then
    mkdir -p "$MOUNT/com.apple.recovery.boot"
    cp "$WORK/recovery/"* "$MOUNT/com.apple.recovery.boot/"
fi
sync
umount "$MOUNT"

echo
echo "Done. On the Mac: hold Option at power-on, pick \"EFI Boot\", then pick the recovery entry in OpenCore."
