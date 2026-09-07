"""Trify CSV Merger — core package.

Merges bank transaction exports (pipe-delimited TXT and semicolon CSV,
optionally PGP-encrypted) into a single normalized CSV, keeping the exact
column layout and formatting used by the original command-line tool.
"""

__all__ = ["merge", "pgp", "config"]
__version__ = "2.0.0"
