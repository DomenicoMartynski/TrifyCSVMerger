"""Trify CSV Merger — desktop GUI (Tkinter/ttk).

Flow:
  1. Configure a PGP private key (once; remembered between launches).
  2. Add any number of CSV / TXT / encrypted (.pgp/.gpg) files.
  3. Merge, then save the single normalized CSV.
"""

from __future__ import annotations

import queue
import threading
from datetime import date
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    Tk,
    X,
    Y,
    filedialog,
    messagebox,
    simpledialog,
)
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from . import __version__, config, pgp, pipeline

APP_TITLE = "Trify CSV Merger"

# Palette
BG = "#eef1f6"
CARD = "#ffffff"
INK = "#1f2933"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_DK = "#1d4ed8"
OK = "#15803d"
WARN = "#b45309"
ERR = "#b91c1c"
BORDER = "#d7dce5"


class MergerApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.key = None
        self.passphrase: str | None = None
        self.files: list[Path] = []
        self.merged_bytes: bytes | None = None
        self._queue: queue.Queue = queue.Queue()

        root.title(APP_TITLE)
        root.geometry("760x680")
        root.minsize(680, 600)
        root.configure(bg=BG)

        self._build_styles()
        self._build_ui()
        self._load_saved_key()
        self._refresh_state()
        self.root.after(100, self._drain_queue)

    # ------------------------------------------------------------------ styles
    def _build_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD, relief="flat")
        style.configure("TLabel", background=CARD, foreground=INK, font=("Segoe UI", 11))
        style.configure("Bg.TLabel", background=BG, foreground=INK, font=("Segoe UI", 11))
        style.configure("H1.TLabel", background=BG, foreground=INK, font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=CARD, foreground=INK, font=("Segoe UI", 11))
        style.configure("CardTitle.TLabel", background=CARD, foreground=INK, font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Step.TLabel", background=ACCENT, foreground="#ffffff", font=("Segoe UI", 11, "bold"))

        style.configure(
            "Accent.TButton",
            background=ACCENT, foreground="#ffffff", font=("Segoe UI", 11, "bold"),
            borderwidth=0, focusthickness=0, padding=(16, 9),
        )
        style.map("Accent.TButton",
                  background=[("active", ACCENT_DK), ("disabled", "#9db4e8")])
        style.configure(
            "Ghost.TButton",
            background=CARD, foreground=ACCENT, font=("Segoe UI", 10, "bold"),
            borderwidth=1, padding=(12, 7),
        )
        style.map("Ghost.TButton",
                  foreground=[("disabled", "#9aa4b2")],
                  bordercolor=[("!disabled", BORDER)])

    # ------------------------------------------------------------------- layout
    def _card(self, parent):
        outer = ttk.Frame(parent, style="Card.TFrame")
        outer.pack(fill=X, pady=(0, 14))
        inner = ttk.Frame(outer, style="Card.TFrame", padding=18)
        inner.pack(fill=BOTH, expand=True)
        return inner

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=22)
        container.pack(fill=BOTH, expand=True)

        header = ttk.Frame(container)
        header.pack(fill=X, pady=(0, 18))
        ttk.Label(header, text=APP_TITLE, style="H1.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Merge bank exports (CSV + TXT, including PGP-encrypted) into one CSV.",
            style="Sub.TLabel",
        ).pack(anchor="w")

        # --- Step 1: PGP key -------------------------------------------------
        card1 = self._card(container)
        row = ttk.Frame(card1, style="Card.TFrame")
        row.pack(fill=X)
        ttk.Label(row, text="  1  ", style="Step.TLabel").pack(side=LEFT)
        ttk.Label(row, text="  PGP key", style="CardTitle.TLabel").pack(side=LEFT)

        self.key_status = ttk.Label(card1, text="", style="Card.TLabel")
        self.key_status.pack(anchor="w", pady=(12, 2))
        self.key_hint = ttk.Label(card1, text="", style="Muted.TLabel", wraplength=640, justify=LEFT)
        self.key_hint.pack(anchor="w", pady=(0, 12))

        keybtns = ttk.Frame(card1, style="Card.TFrame")
        keybtns.pack(anchor="w")
        self.btn_config_key = ttk.Button(keybtns, text="Configure key…", style="Accent.TButton", command=self.on_configure_key)
        self.btn_config_key.pack(side=LEFT)
        self.btn_remove_key = ttk.Button(keybtns, text="Remove key", style="Ghost.TButton", command=self.on_remove_key)
        self.btn_remove_key.pack(side=LEFT, padx=(10, 0))

        # --- Step 2: Files ---------------------------------------------------
        card2 = self._card(container)
        row = ttk.Frame(card2, style="Card.TFrame")
        row.pack(fill=X)
        ttk.Label(row, text="  2  ", style="Step.TLabel").pack(side=LEFT)
        ttk.Label(row, text="  Files to merge", style="CardTitle.TLabel").pack(side=LEFT)
        ttk.Label(card2, text="Add any number of CSV and TXT files. Encrypted .pgp / .gpg files are decrypted automatically.",
                  style="Muted.TLabel", wraplength=640, justify=LEFT).pack(anchor="w", pady=(8, 10))

        listwrap = ttk.Frame(card2, style="Card.TFrame")
        listwrap.pack(fill=BOTH, expand=True)
        import tkinter as tk
        self.filelist = tk.Listbox(
            listwrap, height=7, activestyle="none", highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT, relief="flat",
            font=("Segoe UI", 10), fg=INK, selectbackground="#dbeafe", selectforeground=INK,
            bd=0,
        )
        self.filelist.pack(side=LEFT, fill=BOTH, expand=True)
        sb = ttk.Scrollbar(listwrap, command=self.filelist.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.filelist.config(yscrollcommand=sb.set)

        filebtns = ttk.Frame(card2, style="Card.TFrame")
        filebtns.pack(anchor="w", pady=(12, 0))
        self.btn_add = ttk.Button(filebtns, text="Add files…", style="Accent.TButton", command=self.on_add_files)
        self.btn_add.pack(side=LEFT)
        self.btn_remove = ttk.Button(filebtns, text="Remove selected", style="Ghost.TButton", command=self.on_remove_selected)
        self.btn_remove.pack(side=LEFT, padx=(10, 0))
        self.btn_clear = ttk.Button(filebtns, text="Clear all", style="Ghost.TButton", command=self.on_clear_files)
        self.btn_clear.pack(side=LEFT, padx=(10, 0))

        # --- Step 3: Merge ---------------------------------------------------
        card3 = self._card(container)
        row = ttk.Frame(card3, style="Card.TFrame")
        row.pack(fill=X)
        ttk.Label(row, text="  3  ", style="Step.TLabel").pack(side=LEFT)
        ttk.Label(row, text="  Merge & save", style="CardTitle.TLabel").pack(side=LEFT)

        mergebtns = ttk.Frame(card3, style="Card.TFrame")
        mergebtns.pack(anchor="w", pady=(12, 0))
        self.btn_merge = ttk.Button(mergebtns, text="Merge files", style="Accent.TButton", command=self.on_merge)
        self.btn_merge.pack(side=LEFT)
        self.btn_save = ttk.Button(mergebtns, text="Save merged CSV…", style="Ghost.TButton", command=self.on_save)
        self.btn_save.pack(side=LEFT, padx=(10, 0))

        self.log = ScrolledText(card3, height=7, font=("Menlo", 10), relief="flat",
                                bg="#0f172a", fg="#e2e8f0", insertbackground="#e2e8f0",
                                highlightthickness=1, highlightbackground=BORDER, bd=0)
        self.log.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.log.configure(state="disabled")

        ttk.Label(container, text=f"v{__version__} · pure-Python PGP · no GnuPG required",
                  style="Sub.TLabel").pack(anchor="e", pady=(4, 0))

    # ------------------------------------------------------------------- helpers
    def _log(self, text: str, tag: str = "") -> None:
        self.log.configure(state="normal")
        self.log.insert(END, text + "\n")
        self.log.see(END)
        self.log.configure(state="disabled")

    def _kind_badge(self, path: Path) -> str:
        if pgp.is_pgp_file(path):
            inner = pipeline._kind_from_name(path.name)
            return f"🔒 {inner.upper() if inner else 'PGP'}"
        k = pipeline._kind_from_name(path.name)
        return f"   {k.upper()}" if k else "   ?"

    def _refresh_filelist(self) -> None:
        self.filelist.delete(0, END)
        for p in self.files:
            self.filelist.insert(END, f" {self._kind_badge(p)}   {p.name}")
        self._refresh_state()

    def _refresh_state(self) -> None:
        have_key = self.key is not None
        have_files = len(self.files) > 0
        self.btn_add.state(["!disabled"] if have_key else ["disabled"])
        self.btn_remove.state(["!disabled"] if have_key else ["disabled"])
        self.btn_clear.state(["!disabled"] if have_key else ["disabled"])
        self.btn_merge.state(["!disabled"] if (have_key and have_files) else ["disabled"])
        self.btn_save.state(["!disabled"] if self.merged_bytes else ["disabled"])
        self.btn_remove_key.state(["!disabled"] if config.has_key() else ["disabled"])

        if have_key:
            self.key_status.configure(text=f"✓  Configured:  {config.key_label()}", foreground=OK)
            self.key_hint.configure(text="Your key is stored on this computer only. You can now add files below.")
        else:
            self.key_status.configure(text="✗  No key configured", foreground=WARN)
            self.key_hint.configure(text="Select your private key file (.asc) to unlock the app. It is stored locally and never uploaded anywhere.")

    # --------------------------------------------------------------------- key
    def _load_saved_key(self) -> None:
        if not config.has_key():
            return
        try:
            passphrase = config.stored_passphrase()
            key, _ = pgp.load_key(config.key_path(), passphrase)
        except pgp.PGPError:
            # Stored key needs a passphrase we don't have; ask on demand later.
            self._log("A saved key was found but needs a passphrase. Click ‘Configure key…’.")
            return
        self.key = key
        self.passphrase = passphrase
        self._log(f"Loaded saved key: {config.key_label()}")

    def on_configure_key(self) -> None:
        path = filedialog.askopenfilename(
            title="Select your PGP private key",
            filetypes=[("PGP key files", "*.asc *.key *.gpg *.pgp"), ("All files", "*.*")],
        )
        if not path:
            return
        key_path = Path(path)
        passphrase = None
        try:
            key, info = pgp.load_key(key_path, None)
        except pgp.PGPError as exc:
            if "passphrase" in str(exc).lower():
                passphrase = simpledialog.askstring(
                    "Key passphrase", "Enter the passphrase for this key:", show="•", parent=self.root
                )
                if passphrase is None:
                    return
                try:
                    key, info = pgp.load_key(key_path, passphrase)
                except pgp.PGPError as exc2:
                    messagebox.showerror("Key error", str(exc2), parent=self.root)
                    return
            else:
                messagebox.showerror("Key error", str(exc), parent=self.root)
                return

        remember = True
        if passphrase:
            remember = messagebox.askyesno(
                "Remember passphrase?",
                "Save the passphrase on this computer so you don't have to type it "
                "each time?\n\n(Stored locally in your user profile.)",
                parent=self.root,
            )
        try:
            config.store_key(key_path, passphrase, remember, info.label())
        except OSError as exc:
            messagebox.showerror("Save error", f"Could not store the key locally:\n{exc}", parent=self.root)
            return

        self.key = key
        self.passphrase = passphrase
        self._log(f"Key configured: {info.label()}")
        self._refresh_state()

    def on_remove_key(self) -> None:
        if not messagebox.askyesno("Remove key", "Remove the stored key from this computer?", parent=self.root):
            return
        config.clear_key()
        self.key = None
        self.passphrase = None
        self._log("Key removed.")
        self._refresh_state()

    # ------------------------------------------------------------------- files
    def on_add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Add CSV / TXT / encrypted files",
            filetypes=[
                ("Supported files", "*.csv *.txt *.pgp *.gpg *.asc"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("Encrypted files", "*.pgp *.gpg *.asc"),
                ("All files", "*.*"),
            ],
        )
        added = 0
        existing = {p.resolve() for p in self.files}
        for p in paths:
            rp = Path(p)
            if rp.resolve() not in existing:
                self.files.append(rp)
                existing.add(rp.resolve())
                added += 1
        if added:
            self.merged_bytes = None
            self._log(f"Added {added} file(s).")
        self._refresh_filelist()

    def on_remove_selected(self) -> None:
        for idx in reversed(self.filelist.curselection()):
            del self.files[idx]
        self.merged_bytes = None
        self._refresh_filelist()

    def on_clear_files(self) -> None:
        self.files.clear()
        self.merged_bytes = None
        self._refresh_filelist()

    # ------------------------------------------------------------------- merge
    def on_merge(self) -> None:
        if not self.files or self.key is None:
            return
        self.btn_merge.state(["disabled"])
        self._log("Merging…")
        files = list(self.files)
        threading.Thread(target=self._merge_worker, args=(files,), daemon=True).start()

    def _merge_worker(self, files: list[Path]) -> None:
        try:
            data, results, rows = pipeline.process_files(files, self.key, self.passphrase)
            self._queue.put(("merged", data, results, rows))
        except pgp.PGPError as exc:
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("error", f"Unexpected error:\n{exc}"))

    def _drain_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg[0] == "merged":
                    _, data, results, rows = msg
                    self.merged_bytes = data
                    for r in results:
                        lock = "🔒 " if r.encrypted else ""
                        self._log(f"  {lock}{r.name}: {r.rows} row(s) [{r.kind}]")
                    if rows:
                        self._log(f"Done. {len(rows)} total row(s) — click ‘Save merged CSV…’.")
                    else:
                        self._log("Done, but no matching rows were found in these files.")
                    self.btn_merge.state(["!disabled"])
                    self._refresh_state()
                elif msg[0] == "error":
                    self.merged_bytes = None
                    self._log("Merge failed.")
                    messagebox.showerror("Merge failed", msg[1], parent=self.root)
                    self.btn_merge.state(["!disabled"])
                    self._refresh_state()
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def on_save(self) -> None:
        if not self.merged_bytes:
            return
        default = f"transfers_{date.today().isoformat()}.csv"
        path = filedialog.asksaveasfilename(
            title="Save merged CSV",
            defaultextension=".csv",
            initialfile=default,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_bytes(self.merged_bytes)
        except OSError as exc:
            messagebox.showerror("Save error", str(exc), parent=self.root)
            return
        self._log(f"Saved: {path}")
        messagebox.showinfo("Saved", f"Merged CSV saved to:\n{path}", parent=self.root)


def main() -> None:
    root = Tk()
    MergerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
