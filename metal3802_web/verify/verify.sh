#!/bin/bash
# verify.sh [--inject]: builds and runs the Metal 3802 web checks on this Mac (needs Xcode or the Command Line Tools)
#
#   verify.sh           checks the installed system (after root patching with Metal 3802 web support)
#   verify.sh --inject  checks this repo's payloads/Metal3802Web shims before root patching (DYLD_INSERT_LIBRARIES)
#
# Then open webgl-webgpu-check.html in Safari (File > Open File) for the browser itself.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
payload=$here/../../payloads/Metal3802Web
out=$(mktemp -d /tmp/metal3802-verify.XXXXXX)
inject=()
if [[ ${1:-} == --inject ]]; then
    shims=$payload/libmetalold-selectors.dylib:$payload/libmetal3802-angle.dylib
    [[ $(system_profiler SPDisplaysDataType 2>/dev/null) == *"HD Graphics 4000"* ]] && shims=$shims:$payload/HD4000/libargbuf.dylib
    inject=(env DYLD_INSERT_LIBRARIES=$shims)
fi

cc=(clang -arch x86_64 -w)
"${cc[@]}" -O1 "$here/angle_scene.c" -o "$out/com.apple.WebKit.angle_scene"
"${cc[@]}" -fobjc-arc -framework Metal -framework Foundation "$here/unpack_lanes.m" -o "$out/unpack_lanes"
"${cc[@]}" -fobjc-arc -framework Metal -framework Foundation "$here/webgpu_metal_calls.m" -o "$out/webgpu_metal_calls"
for b in "$out"/*; do codesign -f -s - "$b" 2>/dev/null; done

echo "== GPU: $(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Chipset Model/{print $2; exit}')"
echo "== WebGL through Safari's ANGLE (want ALL OK)"
"${inject[@]+"${inject[@]}"}" "$out/com.apple.WebKit.angle_scene" 2>&1 | grep -v "^20" || true
echo "== WebGPU's Metal calls (want setShaderValidation: OK, then no crash)"
"${inject[@]+"${inject[@]}"}" env AGB_ALL_PROCESSES=1 "$out/webgpu_metal_calls" 2>&1 | grep -v "^20" || echo "   (aborted)"
echo "== Compiler bug behind dropped WebGL draws (vertex .y/.z/.w rows WRONG = bug present; the fix works around it)"
"$out/unpack_lanes" 2>&1 | grep -v "^20" || true
rm -rf "$out"
