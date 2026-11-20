// angle_scene.c: drives Safari's own libANGLE-shared (Metal backend) outside WebKit and checks an ES 3.0 scene:
// matrix uniform, two attributes, a varying, texture sampling, indexed draws and depth testing.
// Stock Ivy Bridge/Haswell on Tahoe draw nothing (every pixel stays the clear colour); with libmetal3802-angle, ALL OK.
// The binary's name must start with com.apple.WebKit: OCLP's Metal wrapper applies its WebKit workarounds by name.
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mach-o/dyld.h>
#include <mach-o/nlist.h>
#include <mach-o/loader.h>
// What OCLP's Metal wrapper does for WebKit when ANGLE is already loaded: skip ANGLE's MacBookPro model check.
static void preset_machine_model(void) {
    for (uint32_t i = 0; i < _dyld_image_count(); i++) {
        if (!strstr(_dyld_get_image_name(i), "libANGLE-shared.dylib")) continue;
        const struct mach_header_64 *mh = (const void *)_dyld_get_image_header(i); intptr_t slide = _dyld_get_image_vmaddr_slide(i);
        const struct load_command *lc = (const void *)(mh + 1); const struct symtab_command *st = 0; const struct segment_command_64 *le = 0;
        for (uint32_t k = 0; k < mh->ncmds; k++, lc = (const void *)((const char *)lc + lc->cmdsize)) {
            if (lc->cmd == LC_SYMTAB) st = (const void *)lc;
            if (lc->cmd == LC_SEGMENT_64 && !strcmp(((const struct segment_command_64 *)lc)->segname, "__LINKEDIT")) le = (const void *)lc; }
        uintptr_t base = le->vmaddr + slide - le->fileoff; const struct nlist_64 *sy = (const void *)(base + st->symoff); const char *str = (const char *)(base + st->stroff);
        for (uint32_t k = 0; k < st->nsyms; k++) if (sy[k].n_un.n_strx && !strcmp(str + sy[k].n_un.n_strx, "__ZZN5angle24IsMetalRendererAvailableEvE19queriedMachineModel")) {
            if (!*(char *)(sy[k].n_value + slide)) { *(char *)(sy[k].n_value + slide) = 1; printf("preset ANGLE queriedMachineModel\n"); } return; }
        printf("queriedMachineModel not found\n"); return;
    }
}
typedef void *P; typedef int I; typedef unsigned U;
#define F(r, n, ...) static r (*n)(__VA_ARGS__);
F(P, EGL_GetPlatformDisplayEXT, U, P, const I *) F(U, EGL_Initialize, P, I *, I *) F(U, EGL_ChooseConfig, P, const I *, P *, I, I *)
F(U, EGL_BindAPI, U) F(P, EGL_CreateContext, P, P, P, const I *) F(P, EGL_CreatePbufferSurface, P, P, const I *) F(U, EGL_MakeCurrent, P, P, P, P)
F(I, EGL_GetError, void) F(const char *, glGetString, U) F(void, glClearColor, float, float, float, float) F(void, glClear, U)
F(void, glReadPixels, I, I, I, I, U, U, void *) F(U, glCreateShader, U) F(void, glShaderSource, U, I, const char **, const I *)
F(void, glCompileShader, U) F(void, glGetShaderiv, U, U, I *) F(U, glCreateProgram, void) F(void, glAttachShader, U, U)
F(void, glBindAttribLocation, U, U, const char *) F(void, glLinkProgram, U) F(void, glUseProgram, U) F(void, glGenBuffers, I, U *)
F(void, glBindBuffer, U, U) F(void, glBufferData, U, long, const void *, U) F(void, glEnableVertexAttribArray, U)
F(void, glVertexAttribPointer, U, I, U, U, I, const void *) F(I, glGetUniformLocation, U, const char *) F(void, glUniform4f, I, float, float, float, float)
F(void, glGenTextures, I, U *) F(void, glBindTexture, U, U) F(void, glTexImage2D, U, I, I, I, I, I, U, U, const void *) F(void, glTexParameteri, U, U, I)
F(void, glUniformMatrix4fv, I, I, U, const float *) F(void, glUniform1i, I, I) F(void, glEnable, U) F(void, glDrawElements, U, I, U, const void *) F(void, glDepthFunc, U) F(void, glClearDepthf, float)
F(void, glGetShaderInfoLog, U, I, I *, char *)
F(void, glDrawArrays, U, I, I) F(U, glGetError, void) F(void, glFinish, void) F(void, glViewport, I, I, I, I)
static void *L(void *h, const char *n) { void *p = dlsym(h, n); if (!p) { fprintf(stderr, "missing %s\n", n); exit(1); } return p; }
static void px(const char *what) { unsigned char p[4] = {9, 9, 9, 9}; glReadPixels(32, 32, 1, 1, 0x1908, 0x1401, p); printf("%-28s %3u,%3u,%3u,%3u  glError=0x%x\n", what, p[0], p[1], p[2], p[3], glGetError()); }
static U sh(U t, const char *s) { U o = glCreateShader(t); glShaderSource(o, 1, &s, 0); glCompileShader(o); I ok; glGetShaderiv(o, 0x8B81, &ok); if (!ok) printf("shader compile failed\n"); return o; }

static U sh2(U t, const char *s) { U o = glCreateShader(t); glShaderSource(o, 1, &s, 0); glCompileShader(o); I ok; glGetShaderiv(o, 0x8B81, &ok); if (!ok) { char b[2048]; glGetShaderInfoLog(o, 2048, 0, b); printf("compile: %s\n", b); } return o; }
static int bad;
static void chk(int x, int y, int r, int g, int b, const char *what) { unsigned char p[4]; glReadPixels(x, y, 1, 1, 0x1908, 0x1401, p);
  int ok = abs(p[0]-r) < 8 && abs(p[1]-g) < 8 && abs(p[2]-b) < 8; bad += !ok; printf("  %-40s (%2d,%2d) = %3u,%3u,%3u  want %3d,%3d,%3d  %s\n", what, x, y, p[0], p[1], p[2], r, g, b, ok ? "ok" : "WRONG"); }
int main(int argc, char **argv) {
    void *h = dlopen("/System/Library/Frameworks/WebKit.framework/Versions/A/Frameworks/WebCore.framework/Versions/A/Frameworks/libANGLE-shared.dylib", RTLD_NOW);
    preset_machine_model();
#define G(n) *(void **)&n = L(h, #n);
#define H(n, s) *(void **)&n = L(h, s);
    G(EGL_GetPlatformDisplayEXT) G(EGL_Initialize) G(EGL_ChooseConfig) G(EGL_BindAPI) G(EGL_CreateContext) G(EGL_CreatePbufferSurface) G(EGL_MakeCurrent) G(EGL_GetError)
    H(glGetString,"GL_GetString") H(glClearColor,"GL_ClearColor") H(glClear,"GL_Clear") H(glReadPixels,"GL_ReadPixels") H(glCreateShader,"GL_CreateShader") H(glShaderSource,"GL_ShaderSource")
    H(glCompileShader,"GL_CompileShader") H(glGetShaderiv,"GL_GetShaderiv") H(glCreateProgram,"GL_CreateProgram") H(glAttachShader,"GL_AttachShader") H(glBindAttribLocation,"GL_BindAttribLocation")
    H(glLinkProgram,"GL_LinkProgram") H(glUseProgram,"GL_UseProgram") H(glGenBuffers,"GL_GenBuffers") H(glBindBuffer,"GL_BindBuffer") H(glBufferData,"GL_BufferData")
    H(glEnableVertexAttribArray,"GL_EnableVertexAttribArray") H(glVertexAttribPointer,"GL_VertexAttribPointer") H(glGetUniformLocation,"GL_GetUniformLocation") H(glUniform4f,"GL_Uniform4f")
    H(glDrawArrays,"GL_DrawArrays") H(glGetError,"GL_GetError") H(glFinish,"GL_Finish") H(glViewport,"GL_Viewport") H(glGenTextures,"GL_GenTextures") H(glBindTexture,"GL_BindTexture")
    H(glTexImage2D,"GL_TexImage2D") H(glTexParameteri,"GL_TexParameteri") H(glUniformMatrix4fv,"GL_UniformMatrix4fv") H(glUniform1i,"GL_Uniform1i") H(glEnable,"GL_Enable")
    H(glDrawElements,"GL_DrawElements") H(glDepthFunc,"GL_DepthFunc") H(glClearDepthf,"GL_ClearDepthf") H(glGetShaderInfoLog,"GL_GetShaderInfoLog")
    I da[] = {0x3203, 0x3489, 0x3038}; P dpy = EGL_GetPlatformDisplayEXT(0x3202, 0, da); I ma, mi; if (!EGL_Initialize(dpy, &ma, &mi)) { printf("EGL init failed\n"); return 1; }
    I ca[] = {0x3033, 1, 0x3040, 0x40, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3025, 24, 0x3038}; P cfg; I n; EGL_ChooseConfig(dpy, ca, &cfg, 1, &n); EGL_BindAPI(0x30A0);
    I xa[] = {0x3098, 3, 0x3038}; P ctx = EGL_CreateContext(dpy, cfg, 0, xa); I sa[] = {0x3057, 64, 0x3056, 64, 0x3038}; P srf = EGL_CreatePbufferSurface(dpy, cfg, sa);
    if (!ctx || !srf || !EGL_MakeCurrent(dpy, srf, srf, ctx)) { printf("ES3 context failed 0x%x\n", EGL_GetError()); return 1; }
    printf("%s | %s\n", glGetString(0x1F02), glGetString(0x8B8C));
    U pr = glCreateProgram();
    glAttachShader(pr, sh2(0x8B31, "#version 300 es\nlayout(location=0) in vec3 p; layout(location=1) in vec2 t; uniform mat4 m; out vec2 vt; void main(){ vt = t; gl_Position = m * vec4(p, 1.0); }"));
    glAttachShader(pr, sh2(0x8B30, "#version 300 es\nprecision mediump float; in vec2 vt; uniform sampler2D s; uniform vec4 tint; out vec4 o; void main(){ o = texture(s, vt) * tint; }"));
    glLinkProgram(pr); glUseProgram(pr);
    // two quads: back one (z=0.5) full red-textured, front one (z=-0.5) covers the left half
    float v[] = { -1,-1,0.5, 0,0,  1,-1,0.5, 1,0,  1,1,0.5, 1,1,  -1,1,0.5, 0,1,   -1,-1,-0.5, 0,0,  0,-1,-0.5, 1,0,  0,1,-0.5, 1,1,  -1,1,-0.5, 0,1 };
    unsigned short idx[] = {4,5,6, 4,6,7, 0,1,2, 0,2,3};   // front first: depth test must keep it
    U b[2]; glGenBuffers(2, b); glBindBuffer(0x8892, b[0]); glBufferData(0x8892, sizeof v, v, 0x88E4); glBindBuffer(0x8893, b[1]); glBufferData(0x8893, sizeof idx, idx, 0x88E4);
    glEnableVertexAttribArray(0); glVertexAttribPointer(0, 3, 0x1406, 0, 20, 0); glEnableVertexAttribArray(1); glVertexAttribPointer(1, 2, 0x1406, 0, 20, (void *)12);
    // 2x2 texture: left column white, right column green; nearest filtering
    unsigned char tx[] = {255,255,255,255, 0,255,0,255, 255,255,255,255, 0,255,0,255}; U tex; glGenTextures(1, &tex); glBindTexture(0x0DE1, tex);
    glTexImage2D(0x0DE1, 0, 0x1908, 2, 2, 0, 0x1908, 0x1401, tx); glTexParameteri(0x0DE1, 0x2801, 0x2600); glTexParameteri(0x0DE1, 0x2800, 0x2600);
    glUniform1i(glGetUniformLocation(pr, "s"), 0); glUniform4f(glGetUniformLocation(pr, "tint"), 1, 0.5, 1, 1);
    float m[16] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1}; glUniformMatrix4fv(glGetUniformLocation(pr, "m"), 1, 0, m);
    glViewport(0, 0, 64, 64); glEnable(0x0B71); glDepthFunc(0x0201); glClearDepthf(1); glClearColor(0, 0, 0, 1); glClear(0x4000 | 0x0100);
    glDrawElements(4, 12, 0x1403, 0); glFinish();
    chk( 8, 32, 255, 128, 255, "front quad, texel white * tint");
    chk(24, 32,   0, 128,   0, "front quad, texel green * tint");
    chk(40, 32,   0, 128,   0, "back quad (u=0.63), green * tint");
    chk(56, 32,   0, 128,   0, "back quad (depth), green * tint");
    // transformed: scale 0.5 -> only the centre is covered; uniform matrix + y orientation
    float m2[16] = {0.5,0,0,0, 0,0.5,0,0, 0,0,1,0, 0,0.5,0,1}; glUniformMatrix4fv(glGetUniformLocation(pr, "m"), 1, 0, m2);
    glClear(0x4000 | 0x0100); glDrawElements(4, 12, 0x1403, 0); glFinish();
    chk(32,  8,   0,   0,   0, "below the shifted quads: background");
    chk(20, 44, 255, 128, 255, "shifted up (+y is up in GL)");
    printf("glError=0x%x  %s\n", glGetError(), bad ? "SOME WRONG" : "ALL OK");
    return bad;
}
