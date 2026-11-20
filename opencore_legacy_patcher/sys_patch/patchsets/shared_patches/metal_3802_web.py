"""
metal_3802_web.py: Metal 3802 web support (WebGL and WebGPU in Safari) for Intel Ivy Bridge and Haswell
"""

import logging

from functools import cache

from .base import BaseSharedPatchSet

from ..base import PatchType, DynamicPatchset

from ....constants      import Constants
from ....datasets.os_data import os_data
from ....detections     import amfi_detect


# Root patch plist entries; a root with either one holds ad hoc signed binaries (see sys_patch_helpers)
WEB_SUPPORT_PATCH_SETS = ["Intel Ivy Bridge Web Support", "Intel Haswell Web Support"]


@cache
def amfi_allows_adhoc_binaries() -> bool:
    """
    The edited MTL driver and the shims are signed ad hoc, and every Metal client (WindowServer included) is a
    platform binary. AMFIPass only lets OCLP's PatcherSupportPkg binaries through: with AMFI enforcing, dyld refuses
    the driver ("mapping process is a platform binary, but mapped file is not"), Metal has no device and
    WindowServer aborts in CoreDisplay at every boot. So AMFI itself must be off (amfi=0x80), AMFIPass or not.
    """
    return amfi_detect.AmfiConfigurationDetection().check_config(amfi_detect.AmfiConfigDetectLevel.ALLOW_ALL)


class Metal3802Web(BaseSharedPatchSet):

    def __init__(self, xnu_major: int, xnu_minor: int, marketing_version: str, global_constants: Constants) -> None:
        super().__init__(xnu_major, xnu_minor, marketing_version)
        self._constants = global_constants


    def _os_requires_patches(self) -> bool:
        """
        Built and tested against Tahoe's WebKit and OCLP's Tahoe Metal 3802 stack
        """
        if self._xnu_major != os_data.tahoe.value or self._constants.enable_metal3802_web is not True:
            return False
        if amfi_allows_adhoc_binaries() is False:
            logging.warning("- Skipping WebGL/WebGPU Support: it needs AMFI disabled (amfi=0x80); AMFIPass does not cover its ad hoc signed files")
            return False
        return True


    def _common_files(self) -> dict:
        """
        Shims loaded by the legacy MTL driver:
        - libmetalold-selectors: Metal selectors MetalOld lacks (WebKit's WebGPU aborts on setShaderValidation:)
        - libmetal3802-angle:    rewrites ANGLE shaders around a vertex-stage miscompile that drops all WebGL draws
        """
        return {
            "/usr/lib": {
                "libmetalold-selectors.dylib": DynamicPatchset.Metal3802Web,
                "libmetal3802-angle.dylib":    DynamicPatchset.Metal3802Web,
            },
        }


    def ivy_bridge_patches(self) -> dict:
        """
        Must be applied after the Ivy Bridge driver bundles are installed
        HD 4000 WebGPU additionally needs argument buffers, which the Big Sur driver lacks (hao-patcher's libargbuf)
        """
        if self._os_requires_patches() is False:
            return {}

        return {
            WEB_SUPPORT_PATCH_SETS[0]: {
                PatchType.OVERWRITE_SYSTEM_VOLUME: {
                    **self._common_files(),
                    "/System/Library/Extensions/AppleIntelHD4000GraphicsMTLDriver.bundle/Contents/MacOS": {
                        "AppleIntelHD4000GraphicsMTLDriver": DynamicPatchset.Metal3802Web,
                        **({"libargbuf.dylib": DynamicPatchset.Metal3802Web} if self._constants.enable_hd4000_webgpu is True else {}),
                    },
                    **({
                        "/System/Library/Extensions/AppleIntelHD4000GraphicsGLDriver.bundle/Contents/MacOS": {
                            "iCBE.dylib":      DynamicPatchset.Metal3802Web,
                            "iCBE-real.dylib": DynamicPatchset.Metal3802Web,
                        },
                    } if self._constants.enable_hd4000_webgpu is True else {}),
                },
            },
        }


    def haswell_patches(self) -> dict:
        """
        Must be applied after the Haswell driver bundles are installed
        The Monterey HD 5000 driver implements argument buffers itself
        """
        if self._os_requires_patches() is False:
            return {}

        return {
            WEB_SUPPORT_PATCH_SETS[1]: {
                PatchType.OVERWRITE_SYSTEM_VOLUME: {
                    **self._common_files(),
                    "/System/Library/Extensions/AppleIntelHD5000GraphicsMTLDriver.bundle/Contents/MacOS": {
                        "AppleIntelHD5000GraphicsMTLDriver": DynamicPatchset.Metal3802Web,
                    },
                },
            },
        }
