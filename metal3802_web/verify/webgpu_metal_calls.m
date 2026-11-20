// webgpu_metal_calls.m: the Metal calls that abort WebKit's GPU process on the legacy stack when a page uses WebGPU:
// -setShaderValidation: (MetalOld lacks it; libmetalold-selectors adds it) and argument encoders (HD 4000: libargbuf).
#import <Metal/Metal.h>
#import <dlfcn.h>
int main(void) { @autoreleasepool {
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    void (*install)(void) = dlsym(RTLD_DEFAULT, "agb_install"); if (install) install();
    printf("selectors shim: %s, argbuf: %s\n", dlsym(RTLD_DEFAULT, "objc_msgSend") && dlopen("libmetalold-selectors.dylib", RTLD_NOLOAD) ? "yes" : "no", install ? "yes" : "no");
    MTLComputePipelineDescriptor *cpd = [MTLComputePipelineDescriptor new];
    @try { [(id)cpd setShaderValidation:MTLShaderValidationDisabled]; printf("setShaderValidation: OK\n"); }
    @catch (NSException *e) { printf("setShaderValidation: EXCEPTION %s\n", e.reason.UTF8String); }
    fflush(stdout);
    MTLArgumentDescriptor *a = [MTLArgumentDescriptor argumentDescriptor]; a.dataType = MTLDataTypePointer; a.index = 0; a.access = MTLBindingAccessReadWrite;
    MTLArgumentDescriptor *b = [MTLArgumentDescriptor argumentDescriptor]; b.dataType = MTLDataTypeTexture; b.index = 1; b.textureType = MTLTextureType2D;
    id<MTLArgumentEncoder> enc = [d newArgumentEncoderWithArguments:@[a, b]];
    printf("newArgumentEncoderWithArguments: %s encodedLength=%lu\n", enc ? "OK" : "nil", (unsigned long)enc.encodedLength);
    id<MTLBuffer> ab = [d newBufferWithLength:enc.encodedLength options:0]; id<MTLBuffer> buf = [d newBufferWithLength:64 options:0];
    [enc setArgumentBuffer:ab offset:0]; [enc setBuffer:buf offset:16 atIndex:0];
    printf("encoded pointer word = 0x%llx\n", ((unsigned long long *)ab.contents)[0]);
}}
