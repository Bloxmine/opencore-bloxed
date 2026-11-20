"""
safari_gpu_dom_rendering.py: Turns on Safari's "GPU Process: DOM Rendering" where WebGL/WebGPU canvases need it

Safari's WebKit shows a WebGL or WebGPU canvas only when DOM rendering runs in the GPU process. With in-process
DOM rendering (RemoteLayerWithInProcessRenderingBackingStore), the canvas layer's delegated display is never
performed: frames are drawn and handed to the page, but the layer's contents stay empty, so canvases stay blank
without any error. WebKit enables GPU-process DOM rendering by default only on Macs with at least 4 physical cores
(defaultUseGPUProcessForDOMRenderingEnabled), so dual-core Ivy Bridge and Haswell Macs (e.g. MacBookPro11,1) need
the feature flag set explicitly. Analysis: metal3802_web/README.md

The flag is a per-user Safari preference, stored in Safari's container. Writing it needs access to that container
(macOS asks the user, or the app needs Full Disk Access); without access the patcher says how to set it by hand.
"""

import os
import logging
import subprocess

from pathlib import Path

from ...support.global_settings import GlobalEnviromentSettings


SAFARI_DOMAIN       = "com.apple.Safari"
SAFARI_PREFERENCE   = "WebKitExperimentalUseGPUProcessForDOMRenderingEnabled"
MINIMUM_CORES       = 4   # WebKit's own threshold for the default
PATCHER_SET_MARKER  = "Metal3802_Web_Safari_GPU_DOM_Rendering"   # set only when the patcher turned the flag on
MANUAL_INSTRUCTIONS = "In Safari: Develop > Feature Flags > turn on 'GPU Process: DOM Rendering', then restart Safari"


class SafariGPUDOMRendering:

    def __init__(self) -> None:
        self._container_plist = Path.home() / "Library/Containers/com.apple.Safari/Data/Library/Preferences/com.apple.Safari.plist"


    def _physical_cores(self) -> int:
        result = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.physicalcpu"], capture_output=True, text=True)
        try:
            return int(result.stdout.strip())
        except ValueError:
            return 0


    def _container_accessible(self) -> bool:
        """
        Without access to Safari's container, 'defaults' silently reads and writes a plist Safari never uses
        """
        try:
            with self._container_plist.open("rb") as f:
                f.read(1)
            return True
        except FileNotFoundError:
            logging.info("  - Safari's preferences do not exist yet (Safari never opened)")
            return False
        except PermissionError:
            logging.info("  - No access to Safari's preferences (needs permission to access other apps' data)")
            return False


    def _read(self) -> bool:
        result = subprocess.run(["/usr/bin/defaults", "read", SAFARI_DOMAIN, SAFARI_PREFERENCE], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip() in ["1", "true", "YES"]


    def _usable(self) -> bool:
        if os.geteuid() == 0:
            # Safari's preferences belong to the user; as root they would land in root's domain
            logging.info("  - Running as root, cannot change the user's Safari preferences")
            return False
        return self._container_accessible()


    def enable(self) -> None:
        """
        Called after root patching installed the Web Support patch sets
        """
        cores = self._physical_cores()
        if cores >= MINIMUM_CORES:
            logging.info(f"- Safari renders WebGL/WebGPU canvases by default on this Mac ({cores} cores)")
            return

        logging.info(f"- Turning on Safari's 'GPU Process: DOM Rendering' ({cores} cores: WebGL/WebGPU canvases stay blank without it)")
        if not self._usable():
            logging.warning(f"  - Could not set it automatically. {MANUAL_INSTRUCTIONS}")
            return
        if self._read() is True:
            logging.info("  - Already on")
            return

        result = subprocess.run(["/usr/bin/defaults", "write", SAFARI_DOMAIN, SAFARI_PREFERENCE, "-bool", "true"], capture_output=True, text=True)
        if result.returncode != 0 or self._read() is not True:
            logging.warning(f"  - Failed to set it ({result.stderr.strip() or 'value did not stick'}). {MANUAL_INSTRUCTIONS}")
            return

        GlobalEnviromentSettings().write_property(PATCHER_SET_MARKER, True)
        logging.info("  - Done; restart Safari for it to take effect")


    def disable_if_set_by_patcher(self) -> None:
        """
        Called after reverting root patches or patching without web support:
        undoes only a change the patcher made, never a flag the user set themselves
        """
        settings = GlobalEnviromentSettings()
        if settings.read_property(PATCHER_SET_MARKER) is not True:
            return

        logging.info("- Turning Safari's 'GPU Process: DOM Rendering' back off (it was turned on for web support)")
        if not self._usable():
            logging.warning("  - Could not change it automatically. In Safari: Develop > Feature Flags > turn off 'GPU Process: DOM Rendering'")
            return

        subprocess.run(["/usr/bin/defaults", "delete", SAFARI_DOMAIN, SAFARI_PREFERENCE], capture_output=True)
        settings.delete_property(PATCHER_SET_MARKER)
