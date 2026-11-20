# Linux tools

For when the Mac doesn't boot and only a Linux machine is at hand.

| Script | What it does |
|---|---|
| `build_efi.py --model MacBookPro11,1 [--verbose] [--output DIR]` | Builds the OCLP OpenCore EFI (`EFI/` + `System/` bootstrap) for a model, like "Build and Install OpenCore" with a target model set. Output: `Build-Folder/OpenCore-Build`, or `DIR`. |
| `sudo make_recovery_usb.sh /dev/sdX [MODEL] [--no-recovery]` | Erases a USB drive and writes OpenCore for `MODEL` plus macOS Tahoe recovery, downloaded from Apple by OpenCorePkg's `macrecovery.py`. Only accepts removable/USB disks, and asks you to type the device name. |

Needs `python3` with `requests`, `packaging` and `wxPython` (the patcher imports the GUI modules; nothing is
displayed), plus `parted`, `dosfstools` and `curl` for the USB script. PyObjC, py_sip_xnu and py-applescript are
macOS-only; `build_efi.py` stubs them, since the EFI builder never calls them when it builds for a given model.

Not possible from Linux: root patching (it modifies a running macOS system volume) and full offline installers
(`createinstallmedia` is a macOS binary). From the recovery USB you can reinstall macOS over the network, or use
Terminal in recovery to revert root patches (`bless --mount "/Volumes/Macintosh HD" --bootefi --last-sealed-snapshot`).

To boot the USB, hold Option at power-on and pick "EFI Boot", then pick the recovery entry in OpenCore's picker
(press Space if it is hidden).
