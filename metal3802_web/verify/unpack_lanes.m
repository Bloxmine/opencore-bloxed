// unpack_lanes.m: shows the legacy compiler bug behind dropped WebGL draws. unpack_snorm4x8_to_float of a uint at
// lane .y/.z/.w of a constant register takes component 3 from lane .x, in vertex shaders only (WRONG rows).
// The bug is in the compiler, so this reports WRONG with or without the fix; libmetal3802-angle rewrites ANGLE's
// shaders around it. Optional argument: another MSL expression of `uint w` to evaluate.
#import <Metal/Metal.h>
int main(int argc, char **argv) { @autoreleasepool { id<MTLDevice> d = MTLCreateSystemDefaultDevice(); NSError *e;
  const char *form = argc > 1 ? argv[1] : "unpack_snorm4x8_to_float(w)";
  printf("form: %s   word 0x817f7f7f -> want 1 1 1 -1\n", form);
  for (int stage = 0; stage < 2; stage++) for (int off = 0; off < 8; off++) {
    NSString *src = [NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\nstruct U { uint pad[%d]; uint w; };\nstruct VO { float4 p [[position]]; float4 c; };\n"
      "vertex VO vs(uint vid [[vertex_id]], constant U &u [[buffer(17)]]) { float2 p[3] = {float2(-1,-1), float2(3,-1), float2(-1,3)}; VO o; o.p = float4(p[vid], 0, 1); uint w = u.w; o.c = %@; return o; }\n"
      "fragment float4 fsv(VO i [[stage_in]]) { return i.c; }\n"
      "fragment float4 fsf(VO i [[stage_in]], constant U &u [[buffer(17)]]) { uint w = u.w; return %@; }\n", off ? off : 1, @(form), @(form)];
    if (!off) src = [src stringByReplacingOccurrencesOfString:@"uint pad[1]; " withString:@""];
    id<MTLLibrary> l = [d newLibraryWithSource:src options:nil error:&e]; if (!l) { printf("compile: %s\n", e.localizedDescription.UTF8String); return 1; }
    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new]; rd.vertexFunction = [l newFunctionWithName:@"vs"]; rd.fragmentFunction = [l newFunctionWithName:stage ? @"fsf" : @"fsv"];
    rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    id<MTLRenderPipelineState> ps = [d newRenderPipelineStateWithDescriptor:rd error:&e]; if (!ps) { printf("pipeline: %s\n", e.localizedDescription.UTF8String); return 1; }
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:4 height:4 mipmapped:NO]; td.usage = MTLTextureUsageRenderTarget; id<MTLTexture> rt = [d newTextureWithDescriptor:td];
    MTLRenderPassDescriptor *pd = [MTLRenderPassDescriptor new]; pd.colorAttachments[0].texture = rt; pd.colorAttachments[0].loadAction = MTLLoadActionClear; pd.colorAttachments[0].clearColor = MTLClearColorMake(9, 9, 9, 9); pd.colorAttachments[0].storeAction = MTLStoreActionStore;
    uint32_t u[16]; for (int k = 0; k < 16; k++) u[k] = 0x11111111 * (k + 1); u[off] = 0x817f7f7f;
    id<MTLCommandBuffer> cb = [[d newCommandQueue] commandBuffer]; id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:pd];
    [re setRenderPipelineState:ps]; [re setVertexBytes:u length:64 atIndex:17]; [re setFragmentBytes:u length:64 atIndex:17];
    [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; [re endEncoding]; [cb commit]; [cb waitUntilCompleted];
    float p[4]; [rt getBytes:p bytesPerRow:64 fromRegion:MTLRegionMake2D(2, 2, 1, 1) mipmapLevel:0];
    BOOL ok = fabsf(p[0]-1) < 1e-3 && fabsf(p[3]+1) < 1e-3;
    printf("%-8s offset %2d (reg c%d.%c) = %8.4f %8.4f %8.4f %8.4f  %s\n", stage ? "fragment" : "vertex", off * 4, off / 4, "xyzw"[off % 4], p[0], p[1], p[2], p[3], ok ? "ok" : "WRONG");
  } }}
