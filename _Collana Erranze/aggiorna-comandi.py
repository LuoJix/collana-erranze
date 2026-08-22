#!/usr/bin/env python3
"""Rigenera 'Comandi Claude Code.pdf' a partire da 'Comandi Claude Code.md'.

Uso:
    python3 aggiorna-comandi.py
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # Progetti culturali/
MD_PATH = BASE / "Comandi Claude Code.md"
PDF_PATH = BASE / "Comandi Claude Code.pdf"
CALIBRE = "/Applications/calibre.app/Contents/MacOS/ebook-convert"


def main():
    if not MD_PATH.exists():
        sys.exit(f"Errore: non trovato {MD_PATH}")

    result = subprocess.run(
        [
            CALIBRE, str(MD_PATH), str(PDF_PATH),
            "--title", "Comandi Claude Code — Progetti culturali",
            "--authors", "Giovanni Martini",
            "--language", "it",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        sys.exit(f"Errore: {result.stderr[-500:]}")

    print(f"✓ {PDF_PATH.name} rigenerato")


if __name__ == "__main__":
    main()
