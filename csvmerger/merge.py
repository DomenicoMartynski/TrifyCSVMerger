"""Core merge logic.

This preserves the exact normalization and output format of the original
``merge_txt_to_csv_format.py`` script, but is generalized to accept *any*
number of TXT and CSV inputs (0 or more of each) instead of exactly one of
each.

Output layout (7 columns, ``;`` delimited, ``utf-8-sig``), sorted by the two
date columns::

    date, date, "PRZELEW Z DNIA <date>", title, who, account, amount
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path


# --------------------------------------------------------------------------
# Field normalization helpers (unchanged behavior from the original script)
# --------------------------------------------------------------------------

def normalize_date(raw_date: str) -> str:
    """Convert DDMMYYYY / DD.MM.YYYY / YYYY-MM-DD to YYYY-MM-DD.

    If parsing fails, the original value is returned unchanged.
    """
    value = raw_date.strip()
    for fmt in ("%d%m%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def normalize_amount(raw_amount: str) -> str:
    """Normalize amount to dot decimal (e.g. ``'2 000,50'`` -> ``'2000.50'``)."""
    return raw_amount.strip().replace(" ", "").replace(",", ".")


def format_amount_polish(raw_amount: str) -> str:
    """Ensure amount uses a comma decimal separator (Polish CSV convention)."""
    return normalize_amount(raw_amount).replace(".", ",")


def format_account_with_spaces(raw_account: str) -> str:
    """Format a 26-digit account as ``2 + groups of 4`` digits.

    Example: ``57109000045085000020260212`` ->
    ``57 1090 0004 5085 0000 2026 0212``. Non-standard values are returned
    trimmed but otherwise untouched.
    """
    account = re.sub(r"\s+", "", raw_account.strip().strip("'"))
    if not account.isdigit():
        return raw_account.strip().strip("'")
    if len(account) != 26:
        return account
    return f"{account[:2]} {' '.join(account[i:i + 4] for i in range(2, 26, 4))}"


# --------------------------------------------------------------------------
# Reading helpers
# --------------------------------------------------------------------------

def read_text_with_fallback(file_path: Path) -> str:
    """Decode a file trying common Central-European encodings in turn."""
    data = file_path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Final fallback keeps processing possible even for mixed encodings.
    return data.decode("cp1250", errors="replace")


def decode_bytes_with_fallback(data: bytes) -> str:
    """Same as :func:`read_text_with_fallback` but for in-memory bytes.

    Used for decrypted PGP payloads that never touch disk.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("cp1250", errors="replace")


# --------------------------------------------------------------------------
# Row builders (unchanged column mapping from the original script)
# --------------------------------------------------------------------------

def build_output_row_from_txt(parts: list[str]) -> list[str]:
    """Map a pipe-delimited TXT record to the 7-column output row.

    TXT columns (source order):
    ``0 id | 1 date | 2 amount | 3 who | 4 src account | 5 dst account | 6 title``
    """
    transfer_date = normalize_date(parts[1])
    amount = format_amount_polish(parts[2])
    who = parts[3].strip()
    destination_account = format_account_with_spaces(parts[5])
    title = parts[6].strip()

    return [
        transfer_date,
        transfer_date,
        f"PRZELEW Z DNIA {transfer_date}",
        title,
        who,
        destination_account,
        amount,
    ]


def is_bank_operation_row(parts: list[str]) -> bool:
    """True when a CSV row looks like a real operation (two ISO dates up front)."""
    if len(parts) < 7:
        return False
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    return bool(
        re.match(date_pattern, parts[0].strip())
        and re.match(date_pattern, parts[1].strip())
    )


def build_output_row_from_csv(parts: list[str]) -> list[str]:
    return [
        normalize_date(parts[0]),
        normalize_date(parts[1]),
        parts[2].strip(),
        parts[3].strip().strip('"'),
        parts[4].strip().strip('"'),
        format_account_with_spaces(parts[5]),
        format_amount_polish(parts[6]),
    ]


# --------------------------------------------------------------------------
# Per-source row extraction
# --------------------------------------------------------------------------

def rows_from_txt_content(content: str) -> list[list[str]]:
    rows: list[list[str]] = []
    reader = csv.reader(io.StringIO(content), delimiter="|")
    for index, parts in enumerate(reader):
        # Skip first row from each TXT source (header/summary row).
        if index == 0:
            continue
        if not parts or all(not p.strip() for p in parts):
            continue
        if len(parts) < 7:
            continue
        rows.append(build_output_row_from_txt(parts))
    return rows


def rows_from_csv_content(content: str) -> list[list[str]]:
    rows: list[list[str]] = []
    reader = csv.reader(io.StringIO(content), delimiter=";")
    for parts in reader:
        if not parts or all(not p.strip() for p in parts):
            continue
        if is_bank_operation_row(parts):
            rows.append(build_output_row_from_csv(parts))
    return rows


# --------------------------------------------------------------------------
# Public merge API
# --------------------------------------------------------------------------

def merge_sources(sources: list[tuple[str, str]]) -> list[list[str]]:
    """Merge a list of ``(kind, content)`` pairs into sorted output rows.

    ``kind`` is either ``"txt"`` or ``"csv"``. Any number of each (including
    zero) is accepted. Rows are combined and sorted by the two date columns,
    exactly as the original tool did.
    """
    rows: list[list[str]] = []
    # CSV rows first, then TXT rows — matches the original ordering before the
    # stable sort (only relevant for rows sharing identical dates).
    for kind, content in sources:
        if kind == "csv":
            rows.extend(rows_from_csv_content(content))
    for kind, content in sources:
        if kind == "txt":
            rows.extend(rows_from_txt_content(content))

    rows.sort(key=lambda row: (row[0], row[1]))
    return rows


def write_rows(rows: list[list[str]], output_path: Path) -> None:
    """Write rows as a ``;``-delimited, ``utf-8-sig`` CSV (Excel-friendly)."""
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows)


def rows_to_csv_bytes(rows: list[list[str]]) -> bytes:
    """Serialize rows to CSV bytes (``utf-8-sig``) without touching disk."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")
