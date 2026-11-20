#!/usr/bin/env python3
"""
build.py: Builds the Metal 3802 web support binaries into payloads/Metal3802Web

Usage: python3 metal3802_web/build.py   (needs Xcode or the Command Line Tools; x86_64 output)

Outputs (all x86_64, ad hoc signed):
    libmetalold-selectors.dylib   missing Metal selectors for MetalOld (hao-patcher)           -> /usr/lib
    libmetal3802-angle.dylib      ANGLE vertex-stage unpack workaround (WebGL draws)            -> /usr/lib
    HD4000/libargbuf.dylib        argument buffers for the HD 4000 driver (hao-patcher)         -> HD4000 MTL driver bundle
    HD4000/iCBE.dylib             iCBE wrapper: argument-buffer shader rewrite (hao-patcher)    -> HD4000 GL driver bundle

The driver binaries themselves are edited at patch time (sys_patch/utilities/metal3802_web.py), from the copies in
PatcherSupportPkg, so no Apple binary is needed or redistributed here.
"""

import hashlib
import json
import shutil
import subprocess
import tempfile

from pathlib import Path


SOURCE = Path(__file__).resolve().parent / "src"
OUTPUT = Path(__file__).resolve().parent.parent / "payloads" / "Metal3802Web"

HD4000_MTL = "/System/Library/Extensions/AppleIntelHD4000GraphicsMTLDriver.bundle/Contents/MacOS"
HD4000_GL  = "/System/Library/Extensions/AppleIntelHD4000GraphicsGLDriver.bundle/Contents/MacOS"

X86 = ["-arch", "x86_64"]


def run(arguments: list) -> None:
    print("  " + " ".join(str(argument) for argument in arguments))
    subprocess.run(arguments, check=True)


def sign(path: Path, identifier: str) -> None:
    run(["/usr/bin/codesign", "-f", "-s", "-", "-i", identifier, path])


def build_selectors(output: Path) -> None:
    run(["clang", *X86, "-mmacosx-version-min=13.0", "-fobjc-arc", "-O2", "-Wall", "-Wextra", "-Werror",
         "-dynamiclib", "-install_name", "/usr/lib/libmetalold-selectors.dylib",
         "-framework", "Foundation", "-Wl,-no_warn_inits",
         "-o", output, SOURCE / "hao" / "metalold_selectors.m"])
    sign(output, "libmetalold-selectors")


def build_angle_fix(output: Path) -> None:
    run(["clang", *X86, "-mmacosx-version-min=13.0", "-fno-objc-arc", "-O2", "-Wall", "-Wextra", "-Werror",
         "-dynamiclib", "-install_name", "/usr/lib/libmetal3802-angle.dylib",
         "-framework", "Foundation", "-Wl,-no_warn_inits",
         "-o", output, SOURCE / "angle_unpack_fix.m"])
    sign(output, "libmetal3802-angle")


def build_argbuf(output: Path) -> None:
    device = SOURCE / "hao" / "argbuf" / "device"
    run(["clang", *X86, "-mmacosx-version-min=11.7", "-fobjc-arc", "-O1", "-Wall", "-Wextra",
         "-Wno-unused-parameter", "-Wno-protocol", "-Wno-mismatched-parameter-types", "-Wl,-no_warn_inits",
         "-dynamiclib", "-install_name", f"{HD4000_MTL}/libargbuf.dylib",
         device / "argbuf.m", device / "astc.m", device / "heap.m", device / "argbuf_tramp.s",
         "-framework", "Foundation", "-framework", "Metal", "-late",
         "-o", output])
    sign(output, "libargbuf")


def build_icbe_wrapper(output: Path) -> None:
    """
    The wrapper re-exports the real iCBE, installed beside it as iCBE-real.dylib at patch time.
    It is linked against a text stub of that library, so the build needs no Apple binary.
    """
    compiler = SOURCE / "hao" / "argbuf" / "compiler"
    with tempfile.TemporaryDirectory() as scratch:
        stub = Path(scratch) / "iCBE-real.tbd"
        stub.write_text(
            "--- !tapi-tbd\n"
            "tbd-version:     4\n"
            "targets:         [ x86_64-macos ]\n"
            f"install-name:    '{HD4000_GL}/iCBE-real.dylib'\n"
            "current-version: 0\n"
            "compatibility-version: 0\n"
            "exports:\n"
            "  - targets:         [ x86_64-macos ]\n"
            "    symbols:         [ _Create, _Delete ]\n"
            "...\n"
        )
        run(["clang", *X86, "-mmacosx-version-min=11.7", "-O1", "-Wall", "-dynamiclib",
             f"-DREAL=\"{HD4000_GL}/iCBE-real.dylib\"",
             compiler / "icbe_wrap.c", compiler / "igil_rewrite.c", compiler / "air_hook.c", compiler / "air_pass.c",
             "-Wl,-not_for_dyld_shared_cache", f"-Wl,-reexport_library,{stub}",
             "-install_name", f"{HD4000_GL}/iCBE.dylib",
             "-o", output])
    sign(output, "com.apple.iCBE")


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    (OUTPUT / "HD4000").mkdir(parents=True)

    print("Building Metal 3802 web support binaries")
    build_selectors(OUTPUT / "libmetalold-selectors.dylib")
    build_angle_fix(OUTPUT / "libmetal3802-angle.dylib")
    build_argbuf(OUTPUT / "HD4000" / "libargbuf.dylib")
    build_icbe_wrapper(OUTPUT / "HD4000" / "iCBE.dylib")

    toolchain = subprocess.run(["clang", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    manifest = {
        "toolchain": toolchain,
        "files": {
            str(path.relative_to(OUTPUT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(OUTPUT.rglob("*.dylib"))
        },
    }
    (OUTPUT / "build.json").write_text(json.dumps(manifest, indent=4) + "\n")
    print(f"Built into {OUTPUT}")


if __name__ == "__main__":
    main()
