"""Tests for the core merge logic (no PGP / GUI needed).

Run:  python -m pytest   (or)   python tests/test_merge.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csvmerger import merge  # noqa: E402


def test_normalize_date_variants():
    assert merge.normalize_date("13042025") == "2025-04-13"
    assert merge.normalize_date("13.04.2025") == "2025-04-13"
    assert merge.normalize_date("2025-04-13") == "2025-04-13"
    assert merge.normalize_date("garbage") == "garbage"


def test_amount_polish():
    assert merge.format_amount_polish("2 000,50") == "2000,50"
    assert merge.format_amount_polish("1000.00") == "1000,00"


def test_account_spacing():
    acc = "57109000045085000020260212"
    assert merge.format_account_with_spaces(acc) == "57 1090 0004 5085 0000 2026 0212"
    # Non-26-digit values are left compact.
    assert merge.format_account_with_spaces("12345") == "12345"


def test_txt_rows_skip_header_and_short_rows():
    content = (
        "HEADER|ignored\n"
        "1|13042025|2 000,50|Jan Kowalski|11|57109000045085000020260212|Zwrot\n"
        "too|short\n"
    )
    rows = merge.rows_from_txt_content(content)
    assert len(rows) == 1
    assert rows[0][0] == "2025-04-13"
    assert rows[0][2] == "PRZELEW Z DNIA 2025-04-13"
    assert rows[0][4] == "Jan Kowalski"
    assert rows[0][6] == "2000,50"


def test_csv_rows_only_operations():
    content = (
        "title;row\n"
        "2025-03-05;2025-03-05;OP;Tytul;Firma;12 3456 7890 1234 5678 9012 3456;500,00\n"
        "notadate;x;y;z;a;b;c\n"
    )
    rows = merge.rows_from_csv_content(content)
    assert len(rows) == 1
    assert rows[0][0] == "2025-03-05"


def test_merge_sorts_and_accepts_any_counts():
    txt = "H|x\n1|31122024|9 999,99|Enc|33|57109000045085000020260212|Secret\n"
    csv = "t;l\n2025-03-05;2025-03-05;OP;Tytul;Firma;12 3456 7890 1234 5678 9012 3456;500,00\n"
    # Two TXT + one CSV.
    rows = merge.merge_sources([("txt", txt), ("txt", txt), ("csv", csv)])
    assert len(rows) == 3
    assert [r[0] for r in rows] == ["2024-12-31", "2024-12-31", "2025-03-05"]

    # Zero of everything is valid and yields no rows.
    assert merge.merge_sources([]) == []
    # Only CSV, zero TXT.
    assert len(merge.merge_sources([("csv", csv)])) == 1


def test_csv_bytes_have_bom_and_semicolons():
    rows = [["2025-01-01", "2025-01-01", "T", "who", "acc", "500,00", ""]]
    data = merge.rows_to_csv_bytes(rows)
    assert data.startswith(b"\xef\xbb\xbf")  # utf-8-sig BOM
    assert b";" in data


if __name__ == "__main__":
    import traceback

    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError:
            failed += 1
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
