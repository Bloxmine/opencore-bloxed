"""
metal3802_web.py: Stages the Metal 3802 web support files for Ivy Bridge and Haswell on macOS Tahoe

The legacy MTL driver from PatcherSupportPkg gets weak load commands for:
- libmetalold-selectors.dylib: Metal selectors MetalOld lacks (setShaderValidation: aborts WebKit's WebGPU)
- libmetal3802-angle.dylib:    works around a vertex-stage miscompile that drops every ANGLE (WebGL) draw
- libargbuf.dylib (HD 4000):   argument buffers, which the Big Sur HD 4000 driver lacks (WebGPU bind groups)

The driver is the module that loads into every Metal client, so the shims are present exactly when the legacy
classes are. Sources and analysis: metal3802_web/README.md
"""

import hashlib
import logging
import shutil
import struct
import subprocess
import tempfile

from pathlib import Path

from ... import constants


LC_SEGMENT_64      = 0x19
LC_LOAD_WEAK_DYLIB = 0x80000018
DYLIB_COMMANDS     = [0xc, 0x80000018, 0x8000001f, 0x80000023, 0xd] # load, weak, reexport, lazy, id

SELECTORS_DYLIB = "/usr/lib/libmetalold-selectors.dylib"
ANGLE_DYLIB     = "/usr/lib/libmetal3802-angle.dylib"

HD4000_MTL_DRIVER = "/System/Library/Extensions/AppleIntelHD4000GraphicsMTLDriver.bundle/Contents/MacOS"
HD4000_GL_DRIVER  = "/System/Library/Extensions/AppleIntelHD4000GraphicsGLDriver.bundle/Contents/MacOS"
HD5000_MTL_DRIVER = "/System/Library/Extensions/AppleIntelHD5000GraphicsMTLDriver.bundle/Contents/MacOS"

# Only the PatcherSupportPkg binaries these edits were made and tested against are modified
LEGACY_DRIVERS = {
    "AppleIntelHD4000GraphicsMTLDriver": {
        "payload":   "11.7.10",
        "directory": HD4000_MTL_DRIVER,
        "sha256":    "43ff24fc61c93a320f869ac913edf34e6c6af181a792c864c31511900bdbb6e9",
    },
    "AppleIntelHD5000GraphicsMTLDriver": {
        "payload":   "12.5",
        "directory": HD5000_MTL_DRIVER,
        "sha256":    "357c4de2e4af7d16c6cb4a20e673e248f7fc7fc2a3e7ec8214b915ece67f54ba",
    },
}

HD4000_ICBE = {
    "payload": "11.7.10",
    "sha256":  "63e7e5cbd978692ed0c0ae33c09f8832147bd4bc852db1e6305e2131d9ab9886",
}


def add_weak_dylibs(binary: bytes, paths: list) -> bytes:
    """
    Append LC_LOAD_WEAK_DYLIB commands to a thin x86_64 MH_DYLIB, in the zero padding after its load commands

    The old code signature stays in place for codesign to replace.
    Ported from hao-patcher's patches/metalold-selectors/src/add_weak_dylib.py (MIT).
    """
    data = bytearray(binary)
    for path in paths:
        magic, cpu, _, file_type, ncmds, sizeofcmds, _, _ = struct.unpack_from("<8I", data, 0)
        if magic != 0xfeedfacf or cpu != 0x01000007 or file_type != 6:
            raise Exception("Not a thin x86_64 Mach-O dylib")

        offset, first_section = 32, None
        for _ in range(ncmds):
            command, size = struct.unpack_from("<2I", data, offset)
            if command == LC_SEGMENT_64:
                nsects = struct.unpack_from("<I", data, offset + 64)[0]
                for section in range(nsects):
                    section_offset = struct.unpack_from("<I", data, offset + 72 + section * 80 + 48)[0]
                    if section_offset and (first_section is None or section_offset < first_section):
                        first_section = section_offset
            if command in DYLIB_COMMANDS:
                name_offset = struct.unpack_from("<I", data, offset + 8)[0]
                name = bytes(data[offset + name_offset:offset + size]).split(b"\0")[0].decode()
                if name == path:
                    raise Exception(f"{path} is already referenced")
            offset += size

        end = 32 + sizeofcmds
        if offset != end:
            raise Exception("Load command walk mismatch")

        name = path.encode() + b"\0"
        command_size = (24 + len(name) + 7) & ~7
        if first_section is None or end + command_size > first_section:
            raise Exception(f"Header padding too small for {path}")
        if any(data[end:end + command_size]):
            raise Exception("Header padding is not zero")

        load_command = struct.pack("<6I", LC_LOAD_WEAK_DYLIB, command_size, 24, 2, 0, 0) + name
        data[end:end + command_size] = load_command + b"\0" * (command_size - len(load_command))
        struct.pack_into("<2I", data, 16, ncmds + 1, sizeofcmds + command_size)

    return bytes(data)


class Metal3802WebStaging:
    """
    Builds a System-rooted tree of the files the "Web Support" patch sets install
    """

    def __init__(self, global_constants: constants.Constants, source_files_path: str) -> None:
        self.constants: constants.Constants = global_constants
        self.source_files_path = Path(source_files_path)
        self.prebuilt_path = self.constants.payload_path / "Metal3802Web"


    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


    def _payload_file(self, payload: str, directory: str, file_name: str, sha256: str) -> Path:
        path = self.source_files_path / payload / directory.lstrip("/") / file_name
        if not path.exists():
            raise Exception(f"Missing {path}")
        if self._sha256(path) != sha256:
            raise Exception(f"{path} is not the PatcherSupportPkg build Metal 3802 web support was made for")
        return path


    def _copy(self, source: Path, root: Path, directory: str, file_name: str = None) -> Path:
        destination = root / directory.lstrip("/") / (file_name or source.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination


    def _stage_driver(self, root: Path, driver: str, weak_dylibs: list) -> None:
        info = LEGACY_DRIVERS[driver]
        source = self._payload_file(info["payload"], info["directory"], driver, info["sha256"])
        destination = root / info["directory"].lstrip("/") / driver
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(add_weak_dylibs(source.read_bytes(), weak_dylibs))
        subprocess.run(
            ["/usr/bin/codesign", "-f", "-s", "-", "-i", f"com.apple.driver.{driver}", destination],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        logging.info(f"- Staged {driver} with weak loads: {', '.join(weak_dylibs)}")


    def stage(self) -> str:
        """
        Returns the staging root, to be used as the patch sets' source
        """
        root = Path(tempfile.mkdtemp(prefix="oclp-metal3802-web-"))
        logging.info(f"- Staging Metal 3802 web support in {root}")

        for dylib in ["libmetalold-selectors.dylib", "libmetal3802-angle.dylib"]:
            self._copy(self.prebuilt_path / dylib, root, "/usr/lib")

        self._stage_driver(root, "AppleIntelHD5000GraphicsMTLDriver", [SELECTORS_DYLIB, ANGLE_DYLIB])

        hd4000_dylibs = [SELECTORS_DYLIB, ANGLE_DYLIB]
        if self.constants.enable_hd4000_webgpu is True:
            hd4000_dylibs.append(f"{HD4000_MTL_DRIVER}/libargbuf.dylib")
            self._copy(self.prebuilt_path / "HD4000" / "libargbuf.dylib", root, HD4000_MTL_DRIVER)
            self._copy(self.prebuilt_path / "HD4000" / "iCBE.dylib", root, HD4000_GL_DRIVER)
            real_icbe = self._payload_file(HD4000_ICBE["payload"], HD4000_GL_DRIVER, "iCBE.dylib", HD4000_ICBE["sha256"])
            self._copy(real_icbe, root, HD4000_GL_DRIVER, "iCBE-real.dylib")
        self._stage_driver(root, "AppleIntelHD4000GraphicsMTLDriver", hd4000_dylibs)

        return str(root)
