#!/usr/bin/env python3
"""Rigenera 'Elenco Progetti Culturali.pdf' da serie.json e cartelle.

Uso:
    python3 aggiorna-elenco.py
"""

import json
import unicodedata
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # Progetti culturali/
REGISTRY = BASE / "_Collana Erranze" / "serie.json"
REGISTRY_EN = BASE / "_Collana Erranze" / "series-en.json"
PDF_PATH = BASE / "Elenco Progetti Culturali.pdf"

IGNORE = {"_Collana Erranze", "Progetti epub", "Progetti stampa", "Completati",
          "Traduzioni",
          "Instagram", "English"}

MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def load_completati():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)["books"]


def load_errancies():
    """Volumi usciti nella serie inglese, con il rimando all'originale italiano."""
    if not REGISTRY_EN.exists():
        return []
    with open(REGISTRY_EN, encoding="utf-8") as f:
        return json.load(f).get("books", [])


def nfc(s):
    return unicodedata.normalize("NFC", s)


def load_in_sviluppo(completati_folders):
    # serie.json usa NFC; macOS restituisce NFD — normalizziamo tutto
    completati_nfc = {nfc(f) for f in completati_folders}
    sviluppo = []
    for entry in sorted(BASE.iterdir(), key=lambda e: nfc(e.name)):
        if not entry.is_dir():
            continue
        if entry.suffix:
            # bundle macOS (.numbers, .pages, .key, ...) appaiono come directory
            continue
        if nfc(entry.name) in IGNORE or entry.name.startswith((".", "_")):
            continue
        if nfc(entry.name) not in completati_nfc:
            sviluppo.append(nfc(entry.name))
    return sviluppo


def split_title(full_title):
    """Ritorna (titolo, sottotitolo) separando al primo ' — '."""
    if " — " in full_title:
        t, s = full_title.split(" — ", 1)
        return t.strip(), s.strip()
    return full_title.strip(), None


def item_html(title_str):
    titolo, sottotitolo = split_title(title_str)
    if sottotitolo:
        return (f'<span class="titolo">{titolo}</span>'
                f' <span class="dash">—</span>'
                f' <em>{sottotitolo}</em>')
    return f'<span class="titolo">{titolo}</span>'


def errancies_item_html(book):
    """Titolo inglese, con l'origine italiana in coda quando è registrata."""
    html = item_html(book["title"])
    original = book.get("original") or {}
    if original.get("title"):
        n = original.get("n")
        vol = f", vol. {n}" if n else ""
        html += f' <span class="origine">(da {original["title"]}{vol})</span>'
    return html


def generate_html(completati, in_sviluppo, errancies):
    oggi = date.today()
    data_str = f"{oggi.day} {MESI[oggi.month]} {oggi.year}"

    completati_li = "\n".join(
        f"        <li>{item_html(b['title'])}</li>" for b in completati
    )
    sviluppo_li = "\n".join(
        f"        <li>{item_html(folder)}</li>" for folder in in_sviluppo
    )
    errancies_block = ""
    if errancies:
        errancies_li = "\n".join(
            f"        <li>{errancies_item_html(b)}</li>"
            for b in sorted(errancies, key=lambda b: b["n"])
        )
        errancies_block = (
            f'\n<h2>Errancies, edizione inglese '
            f'<span class="count">({len(errancies)})</span></h2>\n'
            f"<ol>\n{errancies_li}\n</ol>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2.8cm 2.5cm 2.5cm 2.5cm;
  }}
  body {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    color: #1a1a1a;
    line-height: 1.55;
  }}
  h1 {{
    font-size: 20pt;
    font-weight: 300;
    letter-spacing: 0.01em;
    margin: 0 0 0.15em 0;
  }}
  .subtitle {{
    font-style: italic;
    color: #666;
    font-size: 9pt;
    margin: 0 0 2em 0;
  }}
  h2 {{
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    border-bottom: 0.75pt solid #999;
    padding-bottom: 0.3em;
    margin: 1.8em 0 0.9em 0;
    color: #333;
  }}
  h2 .count {{
    font-weight: 400;
    font-style: italic;
    text-transform: none;
    letter-spacing: normal;
    color: #777;
  }}
  ol {{
    list-style: none;
    padding: 0;
    margin: 0;
    counter-reset: vol;
  }}
  ol li {{
    counter-increment: vol;
    display: flex;
    gap: 0.6em;
    padding: 0.22em 0;
  }}
  ol li::before {{
    content: counter(vol) ".";
    font-size: 7pt;
    color: #999;
    min-width: 1.4em;
    padding-top: 0.35em;
    flex-shrink: 0;
  }}
  ul {{
    list-style: none;
    padding: 0;
    margin: 0;
  }}
  ul li {{
    display: flex;
    gap: 0.6em;
    padding: 0.22em 0;
  }}
  ul li::before {{
    content: "·";
    color: #999;
    min-width: 1.4em;
    padding-left: 0.3em;
  }}
  .titolo {{
    font-weight: 500;
  }}
  .dash {{
    color: #aaa;
  }}
  .origine {{
    color: #999;
    font-size: 8.5pt;
    font-style: italic;
  }}
  em {{
    color: #555;
  }}
</style>
</head>
<body>

<h1>Progetti Culturali — Elenco</h1>
<p class="subtitle">Collana Erranze · aggiornato al {data_str}</p>

<h2>Completati <span class="count">({len(completati)})</span></h2>
<ol>
{completati_li}
</ol>

<h2>In sviluppo <span class="count">({len(in_sviluppo)})</span></h2>
<ul>
{sviluppo_li}
</ul>
{errancies_block}
</body>
</html>"""


def main():
    completati = load_completati()
    completati_folders = {b["folder"] for b in completati}
    in_sviluppo = load_in_sviluppo(completati_folders)
    errancies = load_errancies()

    html = generate_html(completati, in_sviluppo, errancies)

    tmp = BASE / "_Collana Erranze" / "_elenco_tmp.html"
    tmp.write_text(html, encoding="utf-8")

    try:
        from weasyprint import HTML
        HTML(filename=str(tmp)).write_pdf(str(PDF_PATH))
        print(f"✓ {PDF_PATH.name} rigenerato")
        print(f"  Completati: {len(completati)}")
        print(f"  In sviluppo: {len(in_sviluppo)}")
        print(f"  Errancies:   {len(errancies)}")
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
