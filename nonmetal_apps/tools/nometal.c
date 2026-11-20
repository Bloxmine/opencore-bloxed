// nometal.c: simulate a Mac without a Metal GPU for one app (DYLD_INSERT_LIBRARIES; needs AMFI off).
// Every way to obtain an MTLDevice answers "none", as on a non-Metal GPU with OCLP's non-Metal patches,
// where MTLCreateSystemDefaultDevice() returns nil. Each call is logged to stderr with the calling module.
// The rest of the system (WindowServer) keeps its Metal GPU, so this shows app-level behaviour only.
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <CoreFoundation/CoreFoundation.h>

#define DYLD_INTERPOSE(_replacement, _replacee) \
    __attribute__((used)) static struct { const void *replacement; const void *replacee; } _interpose_##_replacee \
    __attribute__((section("__DATA,__interpose"))) = { (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee };

static void note(const char *fn, void *caller) {
    Dl_info info = {0};
    const char *mod = dladdr(caller, &info) && info.dli_fname ? info.dli_fname : "?";
    const char *base = strrchr(mod, '/');
    fprintf(stderr, "[nometal] %s -> none (caller %s)\n", fn, base ? base + 1 : mod);
}

// Metal (MetalOld on OCLP's stack)
extern void *MTLCreateSystemDefaultDevice(void);
extern CFArrayRef MTLCopyAllDevices(void);
extern CFArrayRef MTLCopyAllDevicesWithObserver(void **observer, void *handler);
extern void *MTLCopyDeviceForRegistryID(uint64_t registryID);
extern void *MTLCreateDeviceWithID(uint64_t a, uint64_t b);
// SkyLight (CoreGraphics re-exports the CG names)
extern void *SLDirectDisplayCopyCurrentMetalDevice(uint32_t display);
extern void *SLSCreateDefaultMetalDevice(void);
extern void *SLSDisplayCopyCurrentMetalDevice(uint32_t display);
extern void *SLSGetCAMetalDevice(void);

static void *my_MTLCreateSystemDefaultDevice(void) { note("MTLCreateSystemDefaultDevice", __builtin_return_address(0)); return NULL; }
static CFArrayRef my_MTLCopyAllDevices(void) { note("MTLCopyAllDevices", __builtin_return_address(0)); return CFArrayCreate(NULL, NULL, 0, &kCFTypeArrayCallBacks); }
static CFArrayRef my_MTLCopyAllDevicesWithObserver(void **observer, void *handler) {
    note("MTLCopyAllDevicesWithObserver", __builtin_return_address(0));
    if (observer) *observer = NULL;
    return CFArrayCreate(NULL, NULL, 0, &kCFTypeArrayCallBacks);
}
static void *my_MTLCopyDeviceForRegistryID(uint64_t r) { note("MTLCopyDeviceForRegistryID", __builtin_return_address(0)); return NULL; }
static void *my_MTLCreateDeviceWithID(uint64_t a, uint64_t b) { note("MTLCreateDeviceWithID", __builtin_return_address(0)); return NULL; }
static void *my_SLDirectDisplayCopyCurrentMetalDevice(uint32_t d) { note("CGDirectDisplayCopyCurrentMetalDevice", __builtin_return_address(0)); return NULL; }
static void *my_SLSCreateDefaultMetalDevice(void) { note("SLSCreateDefaultMetalDevice", __builtin_return_address(0)); return NULL; }
static void *my_SLSDisplayCopyCurrentMetalDevice(uint32_t d) { note("SLSDisplayCopyCurrentMetalDevice", __builtin_return_address(0)); return NULL; }
static void *my_SLSGetCAMetalDevice(void) { note("SLSGetCAMetalDevice", __builtin_return_address(0)); return NULL; }

DYLD_INTERPOSE(my_MTLCreateSystemDefaultDevice, MTLCreateSystemDefaultDevice)
DYLD_INTERPOSE(my_MTLCopyAllDevices, MTLCopyAllDevices)
DYLD_INTERPOSE(my_MTLCopyAllDevicesWithObserver, MTLCopyAllDevicesWithObserver)
DYLD_INTERPOSE(my_MTLCopyDeviceForRegistryID, MTLCopyDeviceForRegistryID)
DYLD_INTERPOSE(my_MTLCreateDeviceWithID, MTLCreateDeviceWithID)
DYLD_INTERPOSE(my_SLDirectDisplayCopyCurrentMetalDevice, SLDirectDisplayCopyCurrentMetalDevice)
DYLD_INTERPOSE(my_SLSCreateDefaultMetalDevice, SLSCreateDefaultMetalDevice)
DYLD_INTERPOSE(my_SLSDisplayCopyCurrentMetalDevice, SLSDisplayCopyCurrentMetalDevice)
DYLD_INTERPOSE(my_SLSGetCAMetalDevice, SLSGetCAMetalDevice)

__attribute__((constructor)) static void hello(void) { fprintf(stderr, "[nometal] loaded: Metal devices hidden from this process\n"); }
