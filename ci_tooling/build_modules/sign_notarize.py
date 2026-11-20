"""
sign_notarize.py: Sign and Notarize a file
"""

import subprocess
import mac_signing_buddy
import macos_pkg_builder

from pathlib import Path

import macos_pkg_builder.utilities.signing


class SignAndNotarize:

    def __init__(self, path: Path, signing_identity: str, notarization_apple_id: str, notarization_password: str, notarization_team_id: str, entitlements: str = None) -> None:
        """
        Initialize
        """
        self._path = path
        self._signing_identity = signing_identity
        self._notarization_apple_id = notarization_apple_id
        self._notarization_password = notarization_password
        self._notarization_team_id = notarization_team_id
        self._entitlements = entitlements


    def sign_and_notarize(self) -> None:
        """
        Sign and Notarize
        """
        if not all([self._signing_identity, self._notarization_apple_id, self._notarization_password, self._notarization_team_id]):
            if self._signing_identity and not self._path.name.endswith(".pkg"):
                self._sign_only()
                return
            print("Signing and Notarization details not provided, skipping")
            return

        print(f"Signing {self._path.name}")
        if self._path.name.endswith(".pkg"):
            macos_pkg_builder.utilities.signing.SignPackage(
                identity=self._signing_identity,
                pkg=self._path,
            ).sign()
        else:
            mac_signing_buddy.Sign(
                identity=self._signing_identity,
                file=self._path,
                **({"entitlements": self._entitlements} if self._entitlements else {}),
            ).sign()

        print(f"Notarizing {self._path.name}")
        mac_signing_buddy.Notarize(
            apple_id=self._notarization_apple_id,
            password=self._notarization_password,
            team_id=self._notarization_team_id,
            file=self._path,
        ).sign()


    def _sign_only(self) -> None:
        """
        Sign without notarizing (opencore-bloxed: self-signed key, see ci_tooling/signing)

        Same codesign arguments as mac_signing_buddy.Sign, which refuses identities macOS does not trust
        """
        print(f"Signing {self._path.name} (no notarization)")
        arguments = ["/usr/bin/codesign", "--force", "--verify", "--verbose", "--options=runtime", "--sign", self._signing_identity]
        if self._path.is_dir():
            arguments.insert(1, "--deep")
        if self._entitlements:
            arguments += ["--entitlements", str(Path(self._entitlements).resolve())]
        subprocess.run(arguments + [str(self._path.resolve())], check=True)
