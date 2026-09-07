"""High-level pipeline: classify inputs, decrypt if needed, merge.

Keeps the GUI thin — it just hands over a list of file paths and receives
the merged CSV bytes plus a per-file report.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import merge, pgp


@dataclass
class FileResult:
    name: str
    kind: str          # "txt", "csv", or "skipped"
    encrypted: bool
    rows: int
    note: str = ""


def _sniff_kind(content: str) -> str:
    """Guess whether decoded text is a pipe TXT or a semicolon CSV."""
    for line in content.splitlines():
        if not line.strip():
            continue
        pipe_fields = line.count("|")
        semi_fields = line.count(";")
        if pipe_fields >= 6 and pipe_fields >= semi_fields:
            return "txt"
        if semi_fields >= 6:
            return "csv"
        # Inspect only the first non-empty line.
        break
    # Fall back to whichever separator appears at all.
    if "|" in content:
        return "txt"
    return "csv"


def _kind_from_name(name: str) -> str | None:
    lower = name.lower()
    # Strip a trailing encryption suffix to reveal the real extension.
    for enc in (".pgp", ".gpg", ".asc"):
        if lower.endswith(enc):
            lower = lower[: -len(enc)]
            break
    if lower.endswith(".txt"):
        return "txt"
    if lower.endswith(".csv"):
        return "csv"
    return None


def process_files(
    paths: list[Path],
    key=None,
    passphrase: str | None = None,
) -> tuple[bytes, list[FileResult], list[list[str]]]:
    """Decrypt, classify and merge a set of input files.

    Returns ``(csv_bytes, per_file_results, merged_rows)``.
    Raises :class:`pgp.PGPError` if an encrypted file cannot be decrypted.
    """
    sources: list[tuple[str, str]] = []
    results: list[FileResult] = []

    for path in paths:
        encrypted = pgp.is_pgp_file(path)

        if encrypted:
            if key is None:
                raise pgp.PGPError(
                    f"'{path.name}' is encrypted but no PGP key is configured."
                )
            data = pgp.decrypt_file(path, key, passphrase)
            content = merge.decode_bytes_with_fallback(data)
        else:
            content = merge.read_text_with_fallback(path)

        kind = _kind_from_name(path.name) or _sniff_kind(content)

        if kind == "txt":
            rows = merge.rows_from_txt_content(content)
        elif kind == "csv":
            rows = merge.rows_from_csv_content(content)
        else:  # pragma: no cover - _sniff always returns txt/csv
            results.append(FileResult(path.name, "skipped", encrypted, 0, "unknown format"))
            continue

        sources.append((kind, content))
        results.append(FileResult(path.name, kind, encrypted, len(rows)))

    merged_rows = merge.merge_sources(sources)
    csv_bytes = merge.rows_to_csv_bytes(merged_rows)
    return csv_bytes, results, merged_rows
