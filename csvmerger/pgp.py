"""Pure-Python PGP decryption (no GnuPG install required).

Wraps PGPy so the GUI can load a private key once and decrypt any
``.pgp`` / ``.gpg`` inputs the user adds. Both ASCII-armored and binary
OpenPGP messages are supported.
"""

from __future__ import annotations

import contextlib
import warnings
from pathlib import Path

# PGPy imports a few deprecated ciphers from `cryptography`; silence the noisy
# CryptographyDeprecationWarning it emits at import time.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pgpy  # noqa: E402


PGP_SUFFIXES = {".pgp", ".gpg", ".asc"}


class PGPError(Exception):
    """Raised for any key-loading or decryption problem, with a plain message."""


class KeyInfo:
    """Lightweight, display-friendly summary of a loaded private key."""

    def __init__(self, key: "pgpy.PGPKey") -> None:
        self.key_id = key.fingerprint.keyid
        self.fingerprint = str(key.fingerprint)
        self.is_protected = key.is_protected
        uids = [str(u.userid) if hasattr(u, "userid") else str(u) for u in key.userids]
        # PGPy's userid repr is not human friendly; fall back to the key id.
        self.user_id = next((u for u in uids if u and "PGPUID" not in u), "") or self.key_id

    def label(self) -> str:
        return f"{self.user_id}  (0x{self.key_id})"


def load_key(key_path: Path, passphrase: str | None = None) -> tuple["pgpy.PGPKey", KeyInfo]:
    """Load and (if needed) unlock a private key.

    Returns the unlocked ``PGPKey`` and a :class:`KeyInfo` summary. Raises
    :class:`PGPError` with a user-facing message on any failure.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            key, _ = pgpy.PGPKey.from_file(str(key_path))
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the UI
        raise PGPError(f"Could not read the key file:\n{exc}") from exc

    if key.is_public:
        raise PGPError(
            "That file is a public key. A private (secret) key is required "
            "to decrypt files."
        )

    if key.is_protected:
        if not passphrase:
            raise PGPError("This key is passphrase-protected. Enter the passphrase.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with key.unlock(passphrase):
                    pass
        except Exception as exc:  # noqa: BLE001
            raise PGPError("Wrong passphrase for this key.") from exc

    return key, KeyInfo(key)


def is_pgp_file(path: Path) -> bool:
    """Best-effort check that a path is an encrypted OpenPGP message."""
    if path.suffix.lower() in {".pgp", ".gpg"}:
        return True
    if path.suffix.lower() == ".asc":
        # Could be an armored message; peek for a MESSAGE header.
        with contextlib.suppress(Exception):
            head = path.read_bytes()[:64]
            return b"BEGIN PGP MESSAGE" in head
    return False


def decrypt_file(
    path: Path, key: "pgpy.PGPKey", passphrase: str | None = None
) -> bytes:
    """Decrypt an armored or binary OpenPGP file to plaintext bytes."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            message = pgpy.PGPMessage.from_file(str(path))
    except Exception as exc:  # noqa: BLE001
        raise PGPError(f"'{path.name}' is not a readable PGP message:\n{exc}") from exc

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if key.is_protected:
                with key.unlock(passphrase):
                    plaintext = key.decrypt(message).message
            else:
                plaintext = key.decrypt(message).message
    except Exception as exc:  # noqa: BLE001
        raise PGPError(
            f"Could not decrypt '{path.name}'. It may be encrypted for a "
            f"different key.\n{exc}"
        ) from exc

    if isinstance(plaintext, str):
        return plaintext.encode("utf-8")
    return bytes(plaintext)
