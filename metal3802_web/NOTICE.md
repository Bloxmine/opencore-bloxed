# Third-party source

[src/hao](src/hao) is from [hao-patcher](https://github.com/lythka/hao-patcher) by lythka, commit
`5b0276f1816423d83b348e7623edd7e784b52f1a`, under the MIT license ([src/hao/LICENSE](src/hao/LICENSE)):

| File | From |
|---|---|
| `src/hao/metalold_selectors.m` | `patches/metalold-selectors/build/src/metalold_selectors.m` |
| `src/hao/argbuf/` | `tools/metal-argbuf/src/` (`argbuf_config.h`, `device/`, `compiler/` without `igil_tool.c`) |

`add_weak_dylibs` in `opencore_legacy_patcher/sys_patch/utilities/metal3802_web.py` is ported from
`patches/metalold-selectors/src/add_weak_dylib.py`.

Local changes are listed in [README.md](README.md#what-gets-installed-tahoe-only).
