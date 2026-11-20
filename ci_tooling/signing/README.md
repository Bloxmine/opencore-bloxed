# opencore-bloxed signing

Root patching goes through `/Library/PrivilegedHelperTools/com.dortania.opencore-legacy-patcher.privileged-helper`, a
setuid-root tool. Upstream's helper only serves apps carrying Dortania's Team ID, so it rejects this fork's builds
(`OCLP_PHT_ERROR_INVALID_TEAM_ID`, 166). This fork's helper ([main.m](../privileged_helper_tool/main.m)) serves an app
only when the app's signature is valid and made with the helper's own certificate: this fork's key.

| Script | When | What |
|---|---|---|
| `setup.sh` | once, on the Mac you build on | creates the key in `~/Library/Keychains/opencore-bloxed-signing.keychain-db`, locked with a password you choose; writes the public `opencore-bloxed.pem` here |
| `build.sh` | every build | asks for that password, rebuilds the helper, builds and signs everything, checks the helper accepts the app, locks the keychain |

Then install `dist/OpenCore-Patcher.pkg` on each Mac. It replaces the official app and helper. The other Macs don't
need the key.

- Keep the keychain password; it's the only way to sign new builds. A new key also works, but each Mac then needs the
  `.pkg` signed with it.
- The keychain locks itself after 10 minutes idle and on sleep. Nothing is added to the Mac's trusted certificates.
- The certificate is self-signed, so macOS warns the first time you open the app or package: right-click, **Open**.
