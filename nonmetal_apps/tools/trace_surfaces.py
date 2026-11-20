"""
trace_surfaces.py PID SECONDS FUNC[,FUNC...]

Attaches lldb to PID, logs every call of the given IOSurface/CA functions for SECONDS, then detaches.
For each call: the IOSurface argument (or return value) as global ID and size, and the return value.
x86_64 SysV: args in rdi, rsi, rdx; result in rax. Return values are caught with a one-shot breakpoint on the
return address, restricted to the calling thread.

Run:   PYTHONPATH="$(lldb -P)" xcrun python3 trace_surfaces.py <pid> 8 IOSurfaceCreate,EGL_BindTexImage
Needs SIP's debugging restrictions off to attach to Apple apps. Lessons from using it:
- Names: exact C symbols, C++ method basenames (e.g. setContentsNeedsDisplay) or full names
  (WebCore::GraphicsLayerCA::updateSublayerList). Other names are counted per return value.
- Never use "re:" regex names across all modules: resolving them takes minutes with the target stopped,
  and killing the tracer then kills the target process too.
- A function that never fires is weak evidence: the same name can resolve in two copies of a framework
  (e.g. system WebCore and Safari's cryptex WebCore), and small methods may be inlined.
"""
import sys
import time

import lldb

# name -> (index of the IOSurfaceRef argument or None, whether the return value is an IOSurfaceRef)
FUNCS = {
    "IOSurfaceSetOwnershipIdentity": (0, False),
    "IOSurfaceCreateMachPort": (0, False),
    "IOSurfaceLookupFromMachPort": (None, True),
    "CAIOSurfaceCreate": (0, False),
    "IOSurfaceCreate": (None, True),
}
ARG_REGS = ["rdi", "rsi", "rdx"]


def reg(frame, name):
    return frame.FindRegister(name).GetValueAsUnsigned()


def describe(frame, ptr):
    if not ptr:
        return "NULL"
    out = []
    for f in ("IOSurfaceGetID", "IOSurfaceGetWidth", "IOSurfaceGetHeight", "IOSurfaceGetPixelFormat"):
        v = frame.EvaluateExpression(f"((unsigned long(*)(void*)){f})((void*){ptr:#x})")
        out.append(v.GetValueAsUnsigned() if v.GetError().Success() else -1)
    sid, w, h, fmt = out
    fourcc = fmt.to_bytes(4, "big").decode("latin1") if 0 < fmt < 2**32 else str(fmt)
    return f"id={sid:#x} {w}x{h} '{fourcc}'"


def main():
    pid, seconds, names = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3].split(",")
    dbg = lldb.SBDebugger.Create()
    dbg.SetAsync(True)
    target = dbg.CreateTarget("")
    err = lldb.SBError()
    listener = dbg.GetListener()
    process = target.AttachToProcessWithID(listener, pid, err)
    if not err.Success():
        print("attach failed:", err)
        return 1
    ev = lldb.SBEvent()
    # wait for the attach stop
    while listener.WaitForEvent(5, ev):
        if lldb.SBProcess.GetStateFromEvent(ev) == lldb.eStateStopped:
            break
    entry = {}
    for n in names:
        bp = target.BreakpointCreateByRegex(n[3:]) if n.startswith("re:") else target.BreakpointCreateByName(n)
        locs = sorted({bp.GetLocationAtIndex(i).GetAddress().GetModule().GetFileSpec().GetFilename() for i in range(bp.GetNumLocations())})
        print(f"breakpoint {n}: {bp.GetNumLocations()} locations in {locs}")
        entry[bp.GetID()] = n
    returns = {}   # bp id -> (name, text)
    counts = {}
    process.Continue()
    end = time.time() + seconds
    while time.time() < end:
        if not listener.WaitForEvent(1, ev):
            continue
        if lldb.SBProcess.GetStateFromEvent(ev) != lldb.eStateStopped:
            if lldb.SBProcess.GetStateFromEvent(ev) in (lldb.eStateExited, lldb.eStateDetached):
                print("process went away")
                return 0
            continue
        for thread in process:
            if thread.GetStopReason() != lldb.eStopReasonBreakpoint:
                continue
            bpid = thread.GetStopReasonDataAtIndex(0)
            frame = thread.GetFrameAtIndex(0)
            if bpid in entry:
                n = entry[bpid]
                if n not in FUNCS:
                    # C++/ObjC methods: name by the actual function, shortened
                    fn = frame.GetFunctionName() or n
                    n = fn.split("(")[0].replace("WebKit::", "").replace("WebCore::", "").replace("(anonymous namespace)::", "")
                argi, _ = FUNCS.get(n, (None, False))
                args = [reg(frame, r) for r in ARG_REGS]
                text = f"{n}("
                if argi is not None:
                    text += describe(frame, args[argi])
                if n == "IOSurfaceLookupFromMachPort":
                    text += f"port={args[0]:#x}"
                if n == "IOSurfaceSetOwnershipIdentity":
                    text += f", token={args[1]:#x}, tag={args[2]}"
                text += ")"
                err = lldb.SBError()
                ret_addr = process.ReadPointerFromMemory(reg(frame, "rsp"), err)
                rbp = target.BreakpointCreateByAddress(ret_addr)
                rbp.SetOneShot(True)
                rbp.SetThreadID(thread.GetThreadID())
                returns[rbp.GetID()] = (n, text)
            elif bpid in returns:
                n, text = returns.pop(bpid)
                rax = reg(frame, "rax")
                _, ret_is_surface = FUNCS.get(n, (None, False))
                result = describe(frame, rax) if ret_is_surface else f"{rax & 0xffffffff:#x}"
                key = (n, "123x77" in text or "123x77" in result) if n in FUNCS else (n, result)
                counts[key] = counts.get(key, 0) + 1
                if counts[key] <= 12:
                    print(f"{time.strftime('%H:%M:%S')} tid={thread.GetThreadID():#x} {text} -> {result}", flush=True)
        process.Continue()
    process.Stop()
    listener.WaitForEvent(5, ev)
    for bp_id in list(entry) + list(returns):
        target.BreakpointDelete(bp_id)
    process.Detach()
    print("detached; calls per function (name, is 123x77 canvas):")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
