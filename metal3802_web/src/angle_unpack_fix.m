// angle_unpack_fix.m: works around a vertex-stage miscompile in the legacy Intel Metal compiler (Ivy Bridge/Haswell).
//
// unpack_snorm4x8_to_float / unpack_unorm4x8_to_float of a uint read from lane .y/.z/.w of a constant register take
// the top byte (component 3) from lane .x of that register. ANGLE's Metal backend keeps its Y-flip in that byte
// (ANGLEUniformBlock.ANGLE_flipXY, register c0.w, beside depthRange.near at c0.x = 0.0) and multiplies gl_Position.y
// by it, so every vertex lands on y = 0 and every WebGL draw is dropped. Scalar byte extraction is not affected, so
// component 3 is taken from the source shifted right by 8 instead.
//
// Loaded by the legacy MTL driver bundle (LC_LOAD_WEAK_DYLIB). Rewrites only MSL that ANGLE generated.
// METAL3802_ANGLE_FIX=0 in a process's environment disables it.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <os/log.h>

static os_log_t angle_log;

static NSString *const helpers =
    @"\nstatic inline __attribute__((always_inline)) metal::float4 ANGLE_3802_unpack_snorm4x8(uint32_t v)\n"
     "{ return metal::float4(metal::unpack_snorm4x8_to_float(v).xyz, metal::unpack_snorm4x8_to_float(v >> 8u).z); }\n"
     "static inline __attribute__((always_inline)) metal::float4 ANGLE_3802_unpack_unorm4x8(uint32_t v)\n"
     "{ return metal::float4(metal::unpack_unorm4x8_to_float(v).xyz, metal::unpack_unorm4x8_to_float(v >> 8u).z); }\n";

static NSString *fixed_source(NSString *src) {
    if (![src containsString:@"ANGLE_"] || ![src containsString:@"unpack_"]) return src;
    NSMutableString *s = [src mutableCopy];
    NSUInteger n = [s replaceOccurrencesOfString:@"metal::unpack_snorm4x8_to_float(" withString:@"ANGLE_3802_unpack_snorm4x8(" options:0 range:NSMakeRange(0, s.length)]
                 + [s replaceOccurrencesOfString:@"metal::unpack_unorm4x8_to_float(" withString:@"ANGLE_3802_unpack_unorm4x8(" options:0 range:NSMakeRange(0, s.length)];
    if (!n) return src;
    // after the last #include/using so metal:: is declared, before ANGLE's own code
    NSRange at = [s rangeOfString:@"using namespace metal;"];
    if (at.location == NSNotFound) at = [s rangeOfString:@"#include <metal_stdlib>"];
    if (at.location == NSNotFound) return src;
    [s insertString:helpers atIndex:NSMaxRange(at)];
    os_log_debug(angle_log, "rewrote %lu packed-byte unpacks in ANGLE shader", (unsigned long)n);
    return s;
}

static IMP real_sync, real_async;

static id new_library(id self, SEL _cmd, NSString *src, id options, NSError **error) {
    return ((id (*)(id, SEL, NSString *, id, NSError **))real_sync)(self, _cmd, fixed_source(src), options, error);
}

static void new_library_async(id self, SEL _cmd, NSString *src, id options, id handler) {
    ((void (*)(id, SEL, NSString *, id, id))real_async)(self, _cmd, fixed_source(src), options, handler);
}

static IMP hook(Class cls, const char *name, IMP imp) {
    Method m = cls ? class_getInstanceMethod(cls, sel_registerName(name)) : NULL;
    return m ? method_setImplementation(m, imp) : NULL;
}

__attribute__((constructor)) static void angle_unpack_fix_load(void) {
    const char *off = getenv("METAL3802_ANGLE_FIX");
    if (off && !strcmp(off, "0")) return;
    angle_log = os_log_create("com.dortania.metal3802", "angle");
    Class dev = objc_getClass("_MTLDevice");
    real_sync = hook(dev, "newLibraryWithSource:options:error:", (IMP)new_library);
    real_async = hook(dev, "newLibraryWithSource:options:completionHandler:", (IMP)new_library_async);
    if (!real_sync || !real_async) os_log_error(angle_log, "_MTLDevice newLibraryWithSource methods not found; ANGLE fix inactive");
}
