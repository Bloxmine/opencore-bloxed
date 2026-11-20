# Metal 3802 web support (WebGL and WebGPU on Ivy Bridge and Haswell)

On macOS Tahoe with OCLP's legacy Metal stack (MetalOld + the Big Sur HD 4000 / Monterey HD 5000 drivers), Safari
creates WebGL and WebGPU contexts but:

- **WebGL draws nothing.** Pages stay black or show only their clear colour; no GL error is raised.
- **WebGPU kills the GPU process** as soon as a page builds a pipeline. Because WebGL and WebGPU share that process,
  the page's other canvases go blank too.

This folder holds the fixes, the sources for them and the tools that reproduce each problem. The root patcher
installs them as the "Intel Ivy Bridge Web Support" / "Intel Haswell Web Support" patch sets
([metal_3802_web.py](../opencore_legacy_patcher/sys_patch/patchsets/shared_patches/metal_3802_web.py)).

## Root causes

### WebGL: a vertex-stage miscompile in the legacy Intel compiler

ANGLE (WebKit's WebGL backend) keeps its Y flip in a packed `uint` of its driver uniforms (`ANGLE_flipXY`, byte
offset 12 of `ANGLEUniformBlock`, the `.w` lane of the first constant register) and multiplies `gl_Position.y` by
`unpack_snorm4x8_to_float(ANGLE_flipXY).w`.

In **vertex shaders only**, the legacy compiler (MTLCompilerService → IGIL → iCBE) computes component 3 of
`unpack_snorm4x8_to_float` / `unpack_unorm4x8_to_float` of a `uint` at lane `.y`, `.z` or `.w` from the top byte of
lane **`.x`** of the same register. For ANGLE, lane `.x` is `depthRange.near = 0.0`, so the flip factor is 0, every
vertex lands on `y = 0`, and every triangle has zero area. Scalar byte extraction (`>> 24`, `as_type<char4>(w).w`,
`extract_bits`) is correct, as is the fragment stage. [verify/unpack_lanes.m](verify/unpack_lanes.m) shows it:

```
vertex   offset  0 (reg c0.x) =   1.0000   1.0000   1.0000  -1.0000  ok
vertex   offset  4 (reg c0.y) =   1.0000   1.0000   1.0000   0.1339  WRONG   (0.1339 * 127 = 0x11, top byte of c0.x)
vertex   offset 12 (reg c0.w) =   1.0000   1.0000   1.0000   0.1339  WRONG
fragment offset 12 (reg c0.w) =   1.0000   1.0000   1.0000  -1.0000  ok
```

**Fix:** `libmetal3802-angle.dylib` ([src/angle_unpack_fix.m](src/angle_unpack_fix.m)) hooks
`-[_MTLDevice newLibraryWithSource:options:{error:,completionHandler:}]`. In MSL that ANGLE generated, it replaces
those unpacks with an equivalent whose component 3 is taken from `v >> 8` (verified correct at every lane). Other
shader sources pass through untouched. `METAL3802_ANGLE_FIX=0` in a process's environment turns it off.

### WebGPU: selectors MetalOld lacks, and (HD 4000) argument buffers

1. WebKit's `WebGPU::createComputePipelineState` calls `-[MTLComputePipelineDescriptor setShaderValidation:]`
   (macOS 15+). MetalOld (Ventura's Metal 306) doesn't have it, so the GPU process aborts with an unrecognized
   selector. **Fix:** hao-patcher's `libmetalold-selectors.dylib` adds the 104 selectors newer frameworks send to
   MetalOld's base classes, each with the answer a device without the feature gives. It never overrides an
   existing method.
2. Bind groups are argument buffers. The **Monterey HD 5000 driver (Haswell) implements them natively**
   (`MTLIGEmulationIndirectArgumentEncoder`): compute and render through argument buffers read back correctly on an
   Iris 5100. The **Big Sur HD 4000 driver has no implementation**, so MetalOld reaches an `abort()`.
   **Fix (HD 4000, experimental):** hao-patcher's `libargbuf.dylib` (device side) and iCBE wrapper (shader side)
   from [tools/metal-argbuf](https://github.com/lythka/hao-patcher/tree/main/tools/metal-argbuf). Do **not** use
   libargbuf on Haswell: it replaces the working native encoder and crashes.

## What gets installed (Tahoe only)

| GPU | Files | Setting |
|---|---|---|
| Haswell (HD 4600/5000, Iris, Iris Pro) | `/usr/lib/libmetalold-selectors.dylib`, `/usr/lib/libmetal3802-angle.dylib`; HD5000 MTL driver + 2 weak loads | WebGL/WebGPU Support (on) |
| Ivy Bridge (HD 4000) | the same two shims; HD4000 MTL driver + 2 weak loads | WebGL/WebGPU Support (on) |
| Ivy Bridge, extra | `libargbuf.dylib` in the MTL driver bundle (+1 weak load); `iCBE.dylib` wrapper + `iCBE-real.dylib` (stock) in the GL driver bundle | HD 4000 WebGPU (Experimental) (off) |

The MTL driver bundle executable is the one module every Metal client loads, so the shims are present exactly when
the legacy classes are (hao-patcher's method). At patch time
[sys_patch/utilities/metal3802_web.py](../opencore_legacy_patcher/sys_patch/utilities/metal3802_web.py) copies the
driver from PatcherSupportPkg, refuses it unless its SHA-256 is the 3.0.0 build these edits were made for, adds the
`LC_LOAD_WEAK_DYLIB` commands in the header's zero padding (byte-identical to hao-patcher's `add_weak_dylib.py`) and
signs it ad hoc. Reverting root patches removes everything.

Changes to hao-patcher's sources ([src/hao](src/hao), from 5b0276f):
- `icbe_wrap.c`: the real iCBE path is a build-time define.
- `argbuf.m`: installs itself only in WebKit processes (`com.apple.WebKit.*`). On Tahoe nothing else on the HD 4000
  needs argument buffers, so WindowServer and apps keep the stock path. `AGB_ALL_PROCESSES=1` enables it in another
  process.

## Status

| | Haswell (MacBookPro11,1, Iris 5100, 26.7.1) | Ivy Bridge (HD 4000) |
|---|---|---|
| WebGL draws through Safari's ANGLE | **fixed** (ES 3.0 scene: textures, depth, indexed, matrices) | expected: the same compiler path; run `verify.sh` |
| WebGL canvas on screen | works once draws work | hao-patcher reports it doesn't on macOS 27; not checked on Tahoe |
| WebGPU `setShaderValidation:` abort | **fixed** | fixed (same shim, validated by hao-patcher on HD 4000) |
| WebGPU argument buffers | native, works | libargbuf: validated by hao-patcher on macOS 27, not on Tahoe |
| Whole system with the patch installed | **not yet run**: needs a root patch | **not yet run** |

All Haswell results come from standalone harnesses with the shims injected (`verify.sh --inject`). Safari itself
loads them only after root patching.

## Verify

```sh
metal3802_web/verify/verify.sh --inject   # before root patching: injects payloads/Metal3802Web
metal3802_web/verify/verify.sh            # after root patching
```

Then open [verify/webgl-webgpu-check.html](verify/webgl-webgpu-check.html) in Safari. To see what the shims do:
`log stream --predicate 'subsystem == "metalold-selectors" OR subsystem == "com.dortania.metal3802" OR subsystem == "com.hao.argbuf"'`.

## Rebuild

```sh
python3 metal3802_web/build.py   # Xcode or Command Line Tools; writes payloads/Metal3802Web
```

The iCBE wrapper links against a text stub, so the build needs no Apple binary.
