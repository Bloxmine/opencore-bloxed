# Non-Metal: app issues to describe and fix

Open issues with apps on Macs whose GPU has no Metal support, running OCLP's non-Metal patch set (Moraea's
non-metal-frameworks: nVidia Tesla, AMD TeraScale 1/2, Intel Iron Lake and Sandy Bridge). Collected on
2026-11-20 on the MacBookPro11,1 (a Metal Mac), so the real non-Metal machine has **not been examined yet**.
This file is the hand-off for that work.

## Background

On these Macs there is no Metal device at all: `MTLCreateSystemDefaultDevice()` returns nil. OCLP's non-Metal
patches ([non_metal.py](../opencore_legacy_patcher/sys_patch/patchsets/shared_patches/non_metal.py) and the
`non_metal_*` files next to it) replace SkyLight, WindowServer pieces and Core Animation's rendering so the system
UI composites through OpenGL. Apps that call Metal themselves get no such rescue. They either have their own
fallback (OpenGL or CPU), disable the feature, draw nothing, or crash.

## First steps on the non-Metal machine

1. Record the machine: model, GPU (`system_profiler SPDisplaysDataType`), macOS build, OCLP version and the root
   patch sets installed (`plutil -p /System/Library/CoreServices/OpenCore-Legacy-Patcher.plist`). CLAUDE.md's
   hardware and recovery sections describe the MacBookPro11,1, not this machine. Ask the user how this machine
   is recovered (Recovery, USB, another Mac) before anything risky.
2. CLAUDE.md's "Never" rules apply unchanged: no root patching, reverting, `bless`, `kmutil`, `nvram` writes or
   OpenCore installs without the user's go-ahead for that specific action.
3. **Issue 1 crashes WindowServer**, which logs the user out and loses unsaved work in every app. Tell the user
   before reproducing it, and reproduce it only when they say go.

## Issues

| # | App | Symptom on non-Metal | Status |
|---|---|---|---|
| 1 | Photos | Playing a video crashes the whole WindowServer | not investigated |
| 2 | Photos | The default (Library) view needs Metal and is always disabled; only the Recents tab works | not investigated |
| 3 | Word (Microsoft 365) | Selected text is covered by a large opaque box | not reproduced in simulation, see below |
| 4 | Maps (and Find My, Photos "Places") | Map area stays grey | cause known, no practical fix |

### 1. Photos: video playback crashes WindowServer

Goal: video plays in Photos, or at minimum fails inside Photos without taking WindowServer down.

Evidence to collect first:
- The WindowServer crash report: `/Library/Logs/DiagnosticReports/WindowServer*.ips`. The crashing thread's
  backtrace shows which layer of the non-Metal stack fails (SkyLight, QuartzCore, the OpenGL driver, IOSurface).
- Whether video plays in QuickTime Player and in Safari (`<video>`). If those also crash, the problem is how the
  non-Metal compositor handles video layers in general, not Photos.
- `log show` for WindowServer and Photos for the minute before the crash.

Hypotheses (unverified): video frames reach the compositor as IOSurfaces in YUV formats (`420v`, `420f`, 10-bit
`x420`/`&xv0`) or as HDR/EDR content that the OpenGL compositing path does not handle. Another possibility is that
Photos' player view uses a Metal layer (`CAMetalLayer`) whose contents the patched WindowServer cannot draw. The
crash report decides between these.

### 2. Photos: Library view disabled without Metal

Goal: the default Library (grid) view renders on non-Metal instead of being disabled.

Known: Photos' grid is drawn by its own Metal renderer (PhotosUICore ships `default.metallib`), and Photos turns
the view off when there is no Metal device. To find:
- Where Photos makes that decision: who calls `MTLCreateSystemDefaultDevice` / `CGDirectDisplayCopyCurrentMetalDevice`
  (the `nometal` tool below logs the calling module), and what is disabled when it gets nil.
- Whether PhotosUICore has a non-Metal path (CALayer- or CPU-based) that can be selected. If it has none, the
  options are a much older Photos UI component or a software Metal device (see "Software Metal" below).

The decision point can be explored on a Metal Mac with the `nometal` tool. Whether a fix renders correctly needs
the non-Metal machine.

### 3. Word: opaque box over selected text

Simulated on the MacBookPro11,1 by hiding Metal from Word (`nometal`): Word 16.114.1 falls back to OpenGL by
itself (it loads the OpenGL stack; `mso40ui` asks for a Metal device and gets nil) and renders documents fine.
The opaque selection box does **not** reproduce there. What differs on the real machine: the non-Metal compositor
(OpenGL WindowServer) and the old GPU's OpenGL driver.

Hypothesis (unverified): Word draws the selection highlight as a layer with a blend mode (`compositingFilter`)
or partial transparency, which the non-Metal compositor draws opaque. Check with `layerdump3`: dump Word's layer
tree with text selected and look at the highlight layer's `compFilter`, `op` and `bg` alpha. If the highlight is a
blend-mode layer, a fix is either in the non-Metal compositor or a per-app shim that draws the highlight without
the blend mode.

### 4. Maps: grey map

Reproduced in simulation: VectorKit asks `CGDirectDisplayCopyCurrentMetalDevice` once, gets nil, tries nothing
else, and the map stays grey. Dortania lists Maps (and Find My, Photos "Places") as broken on non-Metal since
Monterey. There is no fallback to switch on.

## Software Metal (the only general route for Metal-only apps)

Translating Metal to OpenGL is not feasible on these GPUs: they top out at OpenGL 3.3 on macOS, which has no
compute shaders, and nothing translates Metal shaders (AIR, LLVM bitcode) to GLSL. A CPU implementation of a
Metal device (like SwiftShader or Mesa's lavapipe for Vulkan) could run AIR through LLVM on the CPU. Nobody has
built one for Metal; it is months of work and would be slow on these CPUs. Decide with the user before starting.

## Tools ([tools/](tools/))

Build with the Command Line Tools, x86_64. Injecting into Apple apps needs AMFI off (`amfi=0x80`); attaching lldb
needs SIP's debugging restrictions off.

- **nometal.c**: hides all Metal devices from one app on a Metal Mac, to see how the app behaves without Metal.
  Logs each attempt to get a device and the module that asked.
  ```sh
  clang -arch x86_64 -dynamiclib -O1 -framework Metal -framework CoreFoundation -Wl,-undefined,dynamic_lookup nometal.c -o libnometal.dylib
  codesign -f -s - libnometal.dylib
  DYLD_INSERT_LIBRARIES=$PWD/libnometal.dylib /System/Applications/Photos.app/Contents/MacOS/Photos 2>&1 | grep nometal
  ```
  Only the app loses Metal; WindowServer keeps it. Compositor bugs (issues 1 and 3) do not reproduce this way.
- **layerdump3.m**: returns an app's CALayer tree with frames, opacity, background alpha, blend mode
  (`compositingFilter`), filters and content class. Load it into a running app with lldb and call it once.
  It has no constructor and changes nothing.
  ```sh
  clang -arch x86_64 -dynamiclib -fobjc-arc -framework AppKit -framework QuartzCore layerdump3.m -o liblayerdump3.dylib
  codesign -f -s - liblayerdump3.dylib
  lldb -p <pid> --batch -o "settings set target.max-string-summary-length 400000" \
    -o "expr (void*)dlopen(\"$PWD/liblayerdump3.dylib\", 2)" \
    -o "expr ((const char*(*)(void))dlsym((void*)-2, \"dump_layers3\"))()" -o detach > layers.txt
  ```
  The result is printed as an escaped C string; sandboxed apps cannot write files themselves.
- **trace_surfaces.py**: lldb tracer that logs calls (arguments, IOSurface IDs and sizes, return values) of named
  functions in a running process for N seconds, then detaches. See its header for usage and pitfalls.

A Metal Mac can also be forced into non-Metal mode with the patcher's developer-only "Non-Metal Enforcement" patch
set ([non_metal_enforcement.py](../opencore_legacy_patcher/sys_patch/patchsets/shared_patches/non_metal_enforcement.py),
"verified functional with HD4000", "not suitable for end users"). That is a root patch: it needs the user's
go-ahead, and the real non-Metal machine is the better test bed.
