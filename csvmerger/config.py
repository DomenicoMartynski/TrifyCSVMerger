"""Persistent app configuration.

Stores the user's private key and (optionally) its passphrase under a
per-user config directory so the app stays "configured" between launches.

Location:
  * Windows:  %APPDATA%\\TrifyCSVMerger
  * macOS/Linux:  ~/.trify_csvmerger
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

APP_DIR_NAME = "TrifyCSVMerger"
KEY_FILENAME = "private_key.asc"
CONFIG_FILENAME = "config.json"


def config_dir() -> Path:
    """Return (creating if needed) the per-user config directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        path = base / APP_DIR_NAME
    else:
        path = Path.home() / ".trify_csvmerger"
    path.mkdir(parents=True, exist_ok=True)
    return path


def key_path() -> Path:
    return config_dir() / KEY_FILENAME


def _config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def load() -> dict:
    """Load the config dict, or an empty default if none exists yet."""
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save(data: dict) -> None:
    _config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _lock_down(path: Path) -> None:
    """Best-effort: restrict a file to the current user (POSIX only)."""
    if os.name != "nt":
        with _suppress_os_error():
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def store_key(source_key: Path, passphrase: str | None, remember: bool, label: str) -> None:
    """Copy the key into the config dir and record its settings."""
    dest = key_path()
    shutil.copyfile(source_key, dest)
    _lock_down(dest)
    save(
        {
            "has_key": True,
            "key_label": label,
            "remember_passphrase": bool(remember and passphrase),
            "passphrase": passphrase if (remember and passphrase) else None,
        }
    )


def has_key() -> bool:
    return bool(load().get("has_key")) and key_path().exists()


def stored_passphrase() -> str | None:
    data = load()
    if data.get("remember_passphrase"):
        return data.get("passphrase")
    return None


def key_label() -> str:
    return load().get("key_label", "")


def clear_key() -> None:
    """Remove the stored key and its settings."""
    with _suppress_os_error():
        key_path().unlink()
    save({})


class _suppress_os_error:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return exc_type is not None and issubclass(exc_type, OSError)
