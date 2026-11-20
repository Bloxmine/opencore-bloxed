# opencore-bloxed

A personal fork of [OpenCore Legacy Patcher](https://github.com/dortania/OpenCore-Legacy-Patcher) 3.0.0
(`origin` = github.com/Bloxmine/opencore-bloxed; work happens on the default branch `metal3802-web`, `main` lags behind).
The target machine is a **MacBookPro11,1** (late 2013,
Haswell Iris 5100) running **macOS Tahoe 26.7.1**, booted through OpenCore and root patched by this fork.

What the fork adds on top of upstream OCLP:

- **Metal 3802 web support**: WebGL and WebGPU in Safari on Ivy Bridge/Haswell under Tahoe. Analysis, sources and
  verify tools are in [metal3802_web/](metal3802_web/README.md). Read that README before touching anything Metal.
- **Own code signing**: the privileged helper only serves apps signed with the fork's self-signed key
  ([ci_tooling/signing/](ci_tooling/signing/README.md)). Upstream's helper rejects fork builds.
- **No official updates**: the updater and the nightly installer are disabled, because they would replace this fork.
- **Linux tools** ([linux/](linux/README.md)) to build the OpenCore EFI and a rescue USB when no Mac is available.

## Layout

| Path | What |
| --- | --- |
| `opencore_legacy_patcher/sys_patch/patchsets/shared_patches/metal_3802_web.py` | "Intel Ivy Bridge/Haswell Web Support" patch sets, AMFI guard |
| `opencore_legacy_patcher/sys_patch/utilities/metal3802_web.py` | stages the MTL driver from PatcherSupportPkg (SHA-256 checked), adds `LC_LOAD_WEAK_DYLIB`s, signs ad hoc |
| `opencore_legacy_patcher/support/defaults.py` (`_check_amfipass_supported`) | keeps `amfi=0x80` when web support is on (Ivy/Haswell, Tahoe) |
| `opencore_legacy_patcher/sys_patch/sys_patch_helpers.py` | root patch plist; `Custom Signature: false` when web support is installed |
| `payloads/Metal3802Web/` | prebuilt shims (`build.json` records their hashes); rebuild with `metal3802_web/build.py` |
| `ci_tooling/signing/build.sh` | the only way to produce an installable app: builds, signs with the fork key, makes `dist/OpenCore-Patcher.pkg` |

## Build and test

- Python deps live in `.venv` (x86_64 wxPython; `OCLP_TARGET_ARCH=x86_64`). Shims: `python3 metal3802_web/build.py`
  (Xcode Command Line Tools).
- App: `ci_tooling/signing/build.sh` asks for the signing keychain password. **The user types it, never you.**
  Then the user installs `dist/OpenCore-Patcher.pkg`.
- Before any root patch, test shims in isolation: `metal3802_web/verify/verify.sh --inject` (standalone harnesses, no
  system change). After patching: `verify.sh` and `metal3802_web/verify/webgl-webgpu-check.html` in Safari.
- Shim logs: `log stream --predicate 'subsystem == "metalold-selectors" OR subsystem == "com.dortania.metal3802"'`.

## Incident, 2026-11-20: root patch made the Mac unbootable

After root patching with web support, every boot stopped in verbose text. WindowServer aborted in
`CoreDisplay_CreateDisplayForCGXDisplayDevice`, and its crash report showed the HD5000 MTL driver was **never loaded**.
Cause: the patch installs an **ad hoc signed** MTL driver and shims, but this Mac's OpenCore kept AMFI on
(boot-args without `amfi=0x80`) and relied on AMFIPass, which only covers OCLP's own PatcherSupportPkg binaries.
WindowServer is a platform binary, so dyld refused the driver ("mapping process is a platform binary, but mapped
file is not"), Metal had no device, and there was no GUI. Safe mode panicked too: it booted without OpenCore's
boot-args, so AMFI also rejected OCLP's patched IO80211 framework.

Fixed by: the web patch sets install only when AMFI is off in the current boot; `defaults.py` keeps `amfi=0x80` in
OpenCore builds while web support is on; the root plist reports `Custom Signature: false`. Recovery was booting
OpenCore from a USB (built on Linux with `linux/build_efi.py`, which has `amfi=0x80`).

Lesson: "works in a standalone harness" does not mean "works in WindowServer". Anything loaded into Metal clients
runs in platform processes under AMFI.

## Never

- **Never root patch, revert root patches, run `bless`, `kmutil`, `mount -uw`, write `nvram`, or install OpenCore to a
  disk without the user's explicit go-ahead for that specific action.** These run as root on the only machine, and a
  mistake means no GUI and a Linux machine plus Recovery to get back. Explain what will change and how to undo it first.
- **Never let an EFI without `amfi=0x80` be installed while the web support patch sets are on the root volume.** After
  "Build and Install OpenCore", check the build log contains `- Disabling AMFI` and `config.plist` boot-args contain
  `amfi=0x80` before the user reboots.
- **Never remove or weaken the AMFI guard** (`amfi_allows_adhoc_binaries`) or the `defaults.py` exception, and never
  rely on AMFIPass for ad hoc signed files.
- **Never install code into platform processes (WindowServer, WebKit, system daemons) that hasn't run in
  `verify.sh --inject` first.** Shims must be inert where they aren't needed; `libargbuf` is WebKit-only and must never
  load on Haswell (it replaces the working native argument-buffer encoder and crashes).
- **Never handle the signing key**: don't read, export, print or commit the keychain, its password or private key.
  `ci_tooling/signing/opencore-bloxed.pem` is the public certificate and is fine.
- **Never re-enable Dortania's updater or nightly downloads**, or point anything at Dortania's releases: they replace
  this fork and its helper.
- **Never commit or push without being asked.** Never commit `logs/` (crash reports with personal data), `.venv`,
  `Build-Folder/`, `dist/` or Apple binaries (KDKs, PatcherSupportPkg contents, Apple frameworks or drivers).
- **Never change the staged driver edits without the PatcherSupportPkg hash check** in `utilities/metal3802_web.py`; a
  different driver build means the offsets and assumptions must be re-verified.
- **Don't suggest safe mode as a recovery path** on this Mac (it panics, see above). Use Recovery or the USB.

## Recovery cheat sheet (this Mac)

- Volumes: system `macOS` (disk3s4), data `macOS - Data` (disk3s1), ESP disk0s1. Not "Macintosh HD".
- Crash reports: `/Volumes/macOS - Data/Library/Logs/DiagnosticReports/` (from Recovery, `diskutil mount disk3s1` first).
- OpenCore picker: press Space to show Recovery.
- Full revert from Recovery: `diskutil mount disk3s4` then `bless --mount /Volumes/macOS --bootefi --last-sealed-snapshot`
  (boots unaccelerated; root patch again afterwards).
- Rescue USB from Linux: `python3 linux/build_efi.py --model MacBookPro11,1 --verbose --output <FAT32 mount>`, plus
  `EFI/BOOT/BOOTx64.efi` copied from `System/Library/CoreServices/boot.efi` for MBR sticks. Boot with Option → "EFI Boot".
