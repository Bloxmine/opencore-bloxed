#!/usr/bin/env python3
"""
build_efi.py: Build an OpenCore Legacy Patcher EFI folder on Linux

OCLP's EFI builder is plain Python; only the host probes (IOKit through PyObjC, sw_vers, diskutil, hdiutil)
need macOS. This entry point skips them and builds for the model given on the command line, the same way
OCLP builds "for another machine" (Settings -> Target Model) on a Mac.

Usage:
    python3 linux/build_efi.py --model MacBookPro11,1 [--verbose] [--output DIR]

Root patching and createinstallmedia need a running macOS and cannot work from Linux.
To put the EFI on a USB drive with a macOS recovery image, see linux/make_recovery_usb.sh.
"""

import argparse
import importlib.abc
import importlib.machinery
import logging
import shutil
import sys
import types

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


# Modules OCLP imports at module level that are macOS-only (PyObjC, py_sip_xnu, py-applescript) or only used by the
# GUI (markdown2). The EFI builder never calls into them.
MACOS_ONLY_MODULES = ("objc", "Foundation", "CoreFoundation", "Cocoa", "AppKit", "Quartz", "PyObjCTools", "py_sip_xnu", "applescript", "markdown2")


class _MacOSOnlyFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):

    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in MACOS_ONLY_MODULES:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        module = types.ModuleType(spec.name)
        module.__path__ = []
        module.__getattr__ = lambda attribute, _name=spec.name: _PyObjCStub(f"{_name}.{attribute}")
        return module

    def exec_module(self, module):
        pass


def _stub_pyobjc() -> None:
    """
    Installed after the real import machinery, so a module that does exist (wxPython, ...) is still used
    """
    sys.meta_path.append(_MacOSOnlyFinder())


class _PyObjCStub:
    def __init__(self, name: str) -> None:
        self._name = name

    def __call__(self, *args, **kwargs):
        # ioreg.py calls a few of these at import time; any real use would fail on the stub it returns
        return _PyObjCStub(f"{self._name}()")

    def __getattr__(self, attribute: str):
        return _PyObjCStub(f"{self._name}.{attribute}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an OpenCore Legacy Patcher EFI folder on Linux")
    parser.add_argument("--model", required=True, help="Target Mac model identifier, e.g. MacBookPro11,1")
    parser.add_argument("--verbose", action="store_true", help="Boot macOS verbose (-v)")
    parser.add_argument("--debug_oc", action="store_true", help="Use OpenCore DEBUG and log to file")
    parser.add_argument("--output", default=None, help="Copy the finished EFI folder here")
    args = parser.parse_args()

    if sys.platform == "darwin":
        print("On macOS, use OpenCore-Patcher-GUI.command instead.")
        return 1

    _stub_pyobjc()
    sys.path.insert(0, str(REPO))
    # OCLP's CLI parser reads sys.argv; keep it from seeing ours
    sys.argv = [sys.argv[0]]

    from opencore_legacy_patcher import constants
    from opencore_legacy_patcher.datasets import model_array, os_data
    from opencore_legacy_patcher.detections import device_probe
    from opencore_legacy_patcher.efi_builder import build
    from opencore_legacy_patcher.support import defaults, global_settings

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # OCLP keeps its settings in /Users/Shared; use a per-user file here instead
    settings_folder = Path.home() / ".config" / "opencore-bloxed"
    settings_folder.mkdir(parents=True, exist_ok=True)
    def _settings_init(self) -> None:
        self.file_name              = ".com.dortania.opencore-legacy-patcher.plist"
        self.global_settings_folder = str(settings_folder)
        self.global_settings_plist  = f"{self.global_settings_folder}/{self.file_name}"
        self._generate_settings_file()
    global_settings.GlobalEnviromentSettings.__init__ = _settings_init

    if args.model not in model_array.SupportedSMBIOS:
        print(f"{args.model} is not a model OCLP supports")
        return 1

    global_constants = constants.Constants()
    global_constants.wxpython_variant = True
    global_constants.cli_mode = True
    global_constants.gui_mode = True
    global_constants.current_path = REPO
    global_constants.payload_path = REPO / "payloads"
    global_constants.launcher_script = str(REPO / "OpenCore-Patcher-GUI.command")
    global_constants.launcher_binary = sys.executable
    global_constants.commit_info = ("Built from source", "Linux", "")

    # Building for another machine: no host data at all, and target the newest macOS OCLP knows
    global_constants.computer = device_probe.Computer(real_model="Linux", real_board_id="Linux")
    global_constants.detected_os = os_data.os_data.tahoe
    global_constants.detected_os_minor = 0
    global_constants.detected_os_build = ""
    global_constants.detected_os_version = "26.0"
    global_constants.custom_model = args.model

    defaults.GenerateDefaults(args.model, False, global_constants, ignore_settings_file=True)
    if args.verbose:
        global_constants.verbose_debug = True
    if args.debug_oc:
        global_constants.opencore_debug = True

    build.BuildOpenCore(args.model, global_constants)

    build_root = global_constants.opencore_release_folder
    if not (build_root / "EFI" / "OC" / "config.plist").exists():
        print("Build failed: no config.plist was written")
        return 1

    # What OCLP's installer copies to the ESP: EFI/OC and the System/Library/CoreServices/boot.efi bootstrap
    if args.output:
        destination = Path(args.output).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        for folder in ["EFI", "System"]:
            if (destination / folder).exists():
                shutil.rmtree(destination / folder)
            shutil.copytree(build_root / folder, destination / folder)
        build_root = destination

    print(f"\nOpenCore for {args.model}: {build_root}  (EFI/ and System/)")
    print("Copy both folders to the root of a FAT32 partition, or use linux/make_recovery_usb.sh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
