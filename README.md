# Trify CSV Merger

A small desktop app (Windows & macOS) that merges bank transaction exports —
any number of **CSV** and **TXT** files, including **PGP-encrypted**
(`.pgp` / `.gpg`) ones — into a **single normalized CSV** you can save with one
click.

The merge output is identical to the original command-line tool: 7 columns,
`;`-separated, `utf-8-sig` (opens cleanly in Excel), sorted by date.

<p align="center"><img src="assets/icon.png" width="120" alt="app icon"></p>

---

## How it works (for the person using it)

1. **Configure your PGP key** (once). Click **Configure key…** and pick your
   private key file (`.asc`). If it has a passphrase, you'll be asked for it and
   can choose to remember it. The key is stored **only on your computer** and is
   never uploaded anywhere.
2. **Add files.** Click **Add files…** and select as many CSV / TXT / encrypted
   files as you like — 0 or many of each. Encrypted files are decrypted
   automatically using your key.
3. **Merge & save.** Click **Merge files**, then **Save merged CSV…** to choose
   where the single output file goes.

No GnuPG installation is required — decryption runs in pure Python.

---

## Getting the app

### macOS
1. Double-click **`build_mac.command`**. It builds `dist/Trify CSV Merger.app`.
2. Drag the app into **Applications**.
3. First launch only: **right-click → Open** (to get past Gatekeeper for an
   unsigned app), then **Open**. After that, open it normally.

### Windows
1. Copy this folder to a Windows machine with
   [Python 3.10+](https://www.python.org/downloads/) installed
   (tick *"Add Python to PATH"* during install).
2. Double-click **`build_windows.bat`**. It builds
   `dist\Trify CSV Merger.exe`.
3. Double-click the `.exe` to run it. To share it, just send that single file.
   (SmartScreen may warn on first run: **More info → Run anyway**.)

> A Windows `.exe` can only be built on Windows — it cannot be cross-compiled
> from a Mac. The `.bat` above does it in one double-click.

---

## Running from source (developers)

```bash
# Use a Python that includes Tkinter (the python.org installer does).
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Run the tests:

```bash
python tests/test_merge.py         # or: python -m pytest
```

Regenerate the app icon after tweaking `build/make_icon.py`:

```bash
pip install pillow
python build/make_icon.py
```

---

## Project layout

```
app.py                     Entry point (launches the GUI)
csvmerger/
  merge.py                 Core normalization + merge (0..N CSV/TXT)
  pgp.py                   Pure-Python PGP key loading & decryption (PGPy)
  pipeline.py              Classify → decrypt → merge glue
  config.py               Stores the key locally between launches
  gui.py                   Tkinter/ttk desktop UI
build/
  CSVMerger.spec           PyInstaller build recipe (mac .app / win .exe)
  make_icon.py             Generates the app icon
build_mac.command          One-click macOS build
build_windows.bat          One-click Windows build
tests/test_merge.py        Unit tests for the merge logic
assets/                    App icon (png/icns/ico)
```

The legacy folder-based command-line script (`merge_txt_to_csv_format.py` and
`run_merge.*`) still works for the old "exactly one TXT + one CSV in
`to_be_merged/`" workflow, but the desktop app above replaces it.

---

## Notes on data & security

- Your **private key never leaves your computer**. It's copied into a per-user
  config folder (`%APPDATA%\TrifyCSVMerger` on Windows, `~/.trify_csvmerger` on
  macOS) so the app stays configured between launches.
- The **built app does not contain any key** — each user loads their own.
- Merging happens entirely offline; nothing is sent over the network.
