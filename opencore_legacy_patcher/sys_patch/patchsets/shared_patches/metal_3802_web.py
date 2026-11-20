"""
metal_3802_web.py: Metal 3802 web support (WebGL and WebGPU in Safari) for Intel Ivy Bridge and Haswell
"""

from .base import BaseSharedPatchSet

from ..base import PatchType, DynamicPatchset

from ....constants      import Constants
from ....datasets.os_data import os_data


class Metal3802Web(BaseSharedPatchSet):

    def __init__(self, xnu_major: int, xnu_minor: int, marketing_version: str, global_constants: Constants) -> None:
        super().__init__(xnu_major, xnu_minor, marketing_version)
        self._constants = global_constants


    def _os_requires_patches(self) -> bool:
        """
        Built and tested against Tahoe's WebKit and OCLP's Tahoe Metal 3802 stack
        """
        return self._xnu_major == os_data.tahoe.value and self._constants.enable_metal3802_web is True


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
            "Intel Ivy Bridge Web Support": {
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
            "Intel Haswell Web Support": {
                PatchType.OVERWRITE_SYSTEM_VOLUME: {
                    **self._common_files(),
                    "/System/Library/Extensions/AppleIntelHD5000GraphicsMTLDriver.bundle/Contents/MacOS": {
                        "AppleIntelHD5000GraphicsMTLDriver": DynamicPatchset.Metal3802Web,
                    },
                },
            },
        }
