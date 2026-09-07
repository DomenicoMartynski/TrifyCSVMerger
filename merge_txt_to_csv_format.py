import argparse
import csv
import io
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def normalize_date(raw_date: str) -> str:
    """
    Convert DDMMYYYY or DD.MM.YYYY to YYYY-MM-DD.
    If parsing fails, return the original value.
    """
    value = raw_date.strip()
    for fmt in ("%d%m%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def normalize_amount(raw_amount: str) -> str:
    """
    Normalize amount to dot decimal (e.g. '2 000,50' -> '2000.50').
    """
    value = raw_amount.strip().replace(" ", "").replace(",", ".")
    return value


def format_amount_polish(raw_amount: str) -> str:
    """
    Ensure amount uses comma decimal separator for Polish CSV conventions.
    """
    normalized = normalize_amount(raw_amount)
    return normalized.replace(".", ",")


def format_account_with_spaces(raw_account: str) -> str:
    """
    Format account number as: 2 digits + groups of 4 digits.
    Example: 57109000045085000020260212 -> 57 1090 0004 5085 0000 2026 0212
    """
    account = re.sub(r"\s+", "", raw_account.strip().strip("'"))
    if not account.isdigit():
        return raw_account.strip().strip("'")
    if len(account) != 26:
        return account
    return f"{account[:2]} {' '.join(account[i:i + 4] for i in range(2, 26, 4))}"


def read_text_with_fallback(file_path: Path) -> str:
    """
    Read file content with common Central European encodings.
    """
    data = file_path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Final fallback keeps processing possible even for mixed encodings.
    return data.decode("cp1250", errors="replace")


def build_output_row_from_txt(parts: list[str]) -> list[str]:
    """
    Input TXT columns (sample):
    0 id
    1 transfer date
    2 amount
    3 who
    4 source account
    5 destination account
    6 transfer title
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


def read_rows_from_txt(input_txt_path: Path) -> list[list[str]]:
    rows: list[list[str]] = []

    content = read_text_with_fallback(input_txt_path)
    reader = csv.reader(io.StringIO(content), delimiter="|")
    for index, parts in enumerate(reader):
        # Skip first row from source TXT (header/summary row).
        if index == 0:
            continue
        if not parts or all(not p.strip() for p in parts):
            continue
        if len(parts) < 7:
            continue
        rows.append(build_output_row_from_txt(parts))
    return rows


def read_rows_from_csv(input_csv_path: Path) -> list[list[str]]:
    rows: list[list[str]] = []

    content = read_text_with_fallback(input_csv_path)
    reader = csv.reader(io.StringIO(content), delimiter=";")
    for parts in reader:
        if not parts or all(not p.strip() for p in parts):
            continue
        if is_bank_operation_row(parts):
            rows.append(build_output_row_from_csv(parts))
    return rows


def merge_files(input_txt_path: Path, input_csv_path: Path, output_path: Path) -> None:
    csv_rows = read_rows_from_csv(input_csv_path)
    txt_rows = read_rows_from_txt(input_txt_path)
    rows = csv_rows + txt_rows
    rows.sort(key=lambda row: (row[0], row[1]))

    # utf-8-sig keeps Polish characters and opens cleanly in Excel.
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows)


def discover_input_files(auto_input_dir: Path) -> tuple[Path, Path]:
    txt_files = sorted(
        {p.resolve() for p in auto_input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"}
    )
    csv_files = sorted(
        {p.resolve() for p in auto_input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".csv"}
    )

    if len(txt_files) != 1 or len(csv_files) != 1:
        raise ValueError(
            f"Folder '{auto_input_dir}' must contain exactly 1 TXT and 1 CSV file. "
            f"Found TXT={len(txt_files)}, CSV={len(csv_files)}."
        )
    return txt_files[0], csv_files[0]


def decrypt_pgp_files_in_folder(
    folder: Path, passphrase: str | None = None
) -> tuple[list[Path], list[Path]]:
    encrypted_files = sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in {".pgp", ".gpg"}
    )
    if not encrypted_files:
        return [], []

    gpg_path = shutil.which("gpg")
    if not gpg_path:
        raise RuntimeError(
            "PGP files found, but 'gpg' command is not available. "
            "Install GnuPG/Gpg4win and ensure gpg is in PATH."
        )

    decrypted_files: list[Path] = []
    processed_encrypted_files: list[Path] = []

    for encrypted_file in encrypted_files:
        output_file = encrypted_file.with_suffix("")
        command = [gpg_path, "--batch", "--yes", "--output", str(output_file), "--decrypt"]
        if passphrase:
            command.extend(["--pinentry-mode", "loopback", "--passphrase", passphrase])
        command.append(str(encrypted_file))

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(
                f"Failed to decrypt '{encrypted_file.name}'. "
                f"GPG error: {stderr or 'Unknown error'}"
            )

        decrypted_files.append(output_file)
        processed_encrypted_files.append(encrypted_file)

    return decrypted_files, processed_encrypted_files


def move_processed_to_historical(
    files_to_archive: list[Path], historical_root: Path
) -> Path:
    batch_dir = historical_root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    batch_dir.mkdir(parents=True, exist_ok=True)

    for source_file in files_to_archive:
        if source_file.exists():
            shutil.move(str(source_file), str(batch_dir / source_file.name))
    return batch_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge TXT transfers with bank CSV into one normalized CSV. "
            "Default mode reads from ./to_be_merged and writes to ./output."
        )
    )
    parser.add_argument("input_txt", nargs="?", help="Path to input TXT file")
    parser.add_argument("input_csv", nargs="?", help="Path to source CSV file")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output CSV file",
    )
    parser.add_argument(
        "--pgp-passphrase",
        default=None,
        help=(
            "Optional passphrase for decrypting .pgp/.gpg files. "
            "If omitted, gpg uses your default key setup."
        ),
    )
    args = parser.parse_args()

    files_to_archive: list[Path] = []

    if args.input_txt and args.input_csv:
        input_txt_path = Path(args.input_txt)
        input_csv_path = Path(args.input_csv)
        if not input_txt_path.exists():
            raise FileNotFoundError(f"Input TXT file does not exist: {input_txt_path}")
        if not input_csv_path.exists():
            raise FileNotFoundError(f"Input CSV file does not exist: {input_csv_path}")
        output_path = (
            Path(args.output)
            if args.output
            else input_txt_path.with_name("merged_output.csv")
        )
    elif args.input_txt or args.input_csv:
        raise ValueError("Provide both input_txt and input_csv, or provide none.")
    else:
        base_dir = Path.cwd()
        to_be_merged_dir = base_dir / "to_be_merged"
        output_dir = base_dir / "output"
        historical_dir = base_dir / "historical"
        to_be_merged_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        historical_dir.mkdir(parents=True, exist_ok=True)

        _, encrypted_source_files = decrypt_pgp_files_in_folder(
            to_be_merged_dir, passphrase=args.pgp_passphrase
        )
        input_txt_path, input_csv_path = discover_input_files(to_be_merged_dir)
        files_to_archive = [input_txt_path, input_csv_path] + encrypted_source_files
        today_str = datetime.today().strftime("%Y-%m-%d")
        output_path = (
            Path(args.output)
            if args.output
            else output_dir / f"transfers_{today_str}.csv"
        )

    merge_files(input_txt_path, input_csv_path, output_path)
    print(f"Done. Output written to: {output_path}")
    if not (args.input_txt and args.input_csv):
        archived_batch_path = move_processed_to_historical(files_to_archive, historical_dir)
        print(f"Archived source files to: {archived_batch_path}")


if __name__ == "__main__":
    main()
