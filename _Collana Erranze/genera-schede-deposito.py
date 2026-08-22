#!/usr/bin/env python3
"""Dai registri genera le schede di metadati per Internet Archive e Zenodo.

Uso:
    python3 genera-schede-deposito.py

Scrive Deposito/schede-it.md e Deposito/schede-en.md: una scheda per volume,
con i campi gia' compilati da incollare nei due moduli di caricamento.

Niente e' scritto a mano qui dentro: titoli, sottotitoli, anno, quarta di
copertina e parole chiave vengono da serie.json e series-en.json. Se cambia il
registro, si rilancia questo script e le schede si aggiornano.
"""
import io
import json
import os
import re
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)
LICENZA = "CC BY-NC-SA 4.0"
LICENZA_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

LANGS = {
    "it": {"registry": "serie.json", "root": "", "serie": "Collana Erranze",
           "lingua": "Italian (ita)", "zlib_lingua": "Italian",
           "zlib_series": "Erranze", "file": "schede-it.md"},
    "en": {"registry": "series-en.json", "root": "English", "serie": "Errancies",
           "lingua": "English (eng)", "zlib_lingua": "English",
           "zlib_series": "Errancies", "file": "schede-en.md"},
}


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def anno(cfg, book):
    md = os.path.join(BASE, cfg["root"], book["folder"], book["file"] + ".md")
    m = re.search(r"\*© (\d{4})", io.open(md, encoding="utf-8").read(1200))
    return m.group(1) if m else "?"


PAPER_FACTOR = 0.0025  # carta avorio, come PAPER = "cream" in genera-stampa.py


def titolo_sottotitolo(cfg, book):
    md = os.path.join(BASE, cfg["root"], book["folder"], book["file"] + ".md")
    righe = io.open(md, encoding="utf-8").read().split("\n", 4)
    t = re.sub(r"^#\s*", "", righe[0]).strip()
    sub = righe[2].strip().strip("*")
    return t, sub


def pagine_e_peso(cfg, book):
    """Pagine dal PDF dell'interno, peso dall'epub. Letti dai file, non dal registro:
    cambiano a ogni rigenerazione e una copia nel registro invecchierebbe da sola."""
    d = os.path.join(BASE, cfg["root"], book["folder"]) if cfg["root"] \
        else os.path.join(BASE, book["folder"])
    pdf = os.path.join(d, book["file"] + " - Interno.pdf")
    epub = os.path.join(d, book["file"] + ".epub")
    pagine = "?"
    if os.path.exists(pdf):
        raw = io.open(pdf, "rb").read()
        # /Count della radice dell'albero delle pagine: e' il totale dichiarato dal PDF.
        # Contare le occorrenze di /Type /Page sovrastima, perche' ne intercetta altre.
        conteggi = [int(n) for n in re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", raw, re.S)]
        conteggi += [int(n) for n in re.findall(rb"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", raw, re.S)]
        if conteggi:
            pagine = max(conteggi)
    peso = "?"
    if os.path.exists(epub):
        peso = f"{round(os.path.getsize(epub) / 1024)} KB"
    return pagine, peso


def scheda(cfg, book, lang):
    titolo = book["title"]
    ident = f"{slug(cfg['serie'])}-{book['n']:02d}-{slug(book['file'])}"
    y = anno(cfg, book)
    kw = book.get("keywords", [])
    orig = book.get("original")
    cartella = os.path.join(cfg["root"], book["folder"]) if cfg["root"] else book["folder"]

    p = [f"## {cfg['serie']} · {book['n']} — {titolo}", ""]

    p += ["### Internet Archive", "",
          "| campo | valore |", "|---|---|",
          f"| Identifier | `{ident}` |",
          f"| Title | {titolo} |",
          "| Creator | Giovanni Martini |",
          f"| Date | {y} |",
          f"| Language | {cfg['lingua']} |",
          f"| Subject tags | {', '.join(kw)} |",
          f"| Licence | {LICENZA} — {LICENZA_URL} |",
          f"| Collection | Community texts |", "",
          "Description:", "",
          "> " + book.get("blurb", "(manca il blurb nel registro)"), "",
          "File da caricare:", "",
          f"- `{cartella}/{book['file']}.epub`",
          f"- `{cartella}/{book['file']} - Interno.pdf`", ""]

    p += ["### Zenodo", "",
          "| campo | valore |", "|---|---|",
          "| Upload type | Publication → Book |",
          f"| Title | {titolo} |",
          "| Authors | Martini, Giovanni |",
          f"| Publication date | {y} |",
          f"| Language | {cfg['lingua']} |",
          "| Version | 1.0 |",
          f"| Keywords | {', '.join(kw)} |",
          f"| Licence | {LICENZA} |",
          f"| Additional notes | {cfg['serie']}, volume {book['n']} |"]
    if orig:
        p += [f"| Related identifiers | *is derived from* → DOI di «{orig['title']}» "
              f"({'Collana Erranze'}, vol. {orig['n']}), da inserire dopo aver depositato l'italiano |"]
    p += ["", "Description (abstract):", "",
          "> " + book.get("blurb", "(manca il blurb nel registro)"), ""]

    pagine, peso = pagine_e_peso(cfg, book)
    p += ["### Z-Library", "",
          "| campo | valore |", "|---|---|",
          f"| Title | {titolo} |",
          "| Author | Giovanni Martini |",
          "| Content type | Books |",
          f"| Series | {cfg['zlib_series']} |",
          f"| Volume | {book['n']} |",
          f"| Year | {y} |",
          f"| Language | {cfg['zlib_lingua']} |",
          f"| Pages | {pagine} |",
          f"| Categories | {book.get('zlib_category', '—')} *(da confermare sul menu del sito)* |",
          f"| Tags | {', '.join(kw)} |", "",
          f"File: `{cartella}/{book['file']}.epub` — EPUB, {peso}", "",
          "Description:", "",
          "> " + book.get("blurb", "(manca il blurb nel registro)"), ""]

    t_kdp, sub_kdp = titolo_sottotitolo(cfg, book)
    dorso = round(max(pagine if isinstance(pagine, int) else 24, 24) * PAPER_FACTOR, 3)
    p += ["### KDP (cartaceo)", "",
          "| campo | valore |", "|---|---|",
          f"| Language | {cfg['zlib_lingua']} |",
          f"| Book Title | {t_kdp} |",
          f"| Subtitle | {sub_kdp} |",
          f"| Series | {cfg['serie']} — volume {book['n']} |",
          "| Author | Giovanni Martini |",
          "| Publishing rights | I own the copyright |",
          f"| Keywords (max 7) | {' · '.join(kw[:7])} |",
          f"| Categories (BISAC) | {' · '.join(book.get('kdp_categories', []))} |",
          "| ISBN | Get a free KDP ISBN |",
          "| Print type | Black & white, **cream paper** |",
          "| Trim | 6 × 9 in, con bleed |",
          f"| Interior | `{cartella}/{book['file']} - Interno.pdf` — {pagine} pagine |",
          f"| Cover | `{cartella}/{book['file']} - Copertina.pdf` — dorso {dorso} in |",
          f"| Price | USD {book.get('price_paperback_usd', '—')} · "
          f"EUR {book.get('price_paperback_eur', '—')} |", "",
          "La **carta avorio** non e' una preferenza: il dorso e' calcolato su quel fattore,",
          "e con la carta bianca KDP ne chiederebbe uno piu' stretto e rifiuterebbe la copertina.",
          "",
          "Description: la stessa del blocco Z-Library qui sopra.", ""]
    return "\n".join(p)


def main():
    dest_dir = os.path.join(SCRIPT_DIR, "Deposito")
    os.makedirs(dest_dir, exist_ok=True)
    for lang, cfg in LANGS.items():
        with open(os.path.join(SCRIPT_DIR, cfg["registry"]), encoding="utf-8") as f:
            reg = json.load(f)
        books = reg["books"]
        testa = [
            f"# Schede di deposito — {cfg['serie']}",
            "",
            "Generato da `genera-schede-deposito.py`. **Non modificare a mano**: i dati",
            "vengono dal registro, quindi si corregge quello e si rilancia lo script.",
            "",
            "## Prima di cominciare",
            "",
            "**Zenodo e' definitivo.** Un DOI non si cancella: si puo' limitare l'accesso al",
            "file, ma il record resta. Deposita un volume solo quando e' fermo, e da li' in",
            "poi usa il versionamento, che assegna un DOI nuovo a ogni versione tenendo un",
            "DOI «concettuale» che punta sempre all'ultima. Internet Archive e' piu'",
            "tollerante: li' si corregge.",
            "",
            "**Ordine consigliato: prima l'italiano, poi l'inglese.** I volumi di *Errancies*",
            "dichiarano su Zenodo la relazione *is derived from* verso il volume italiano di",
            "origine, e per compilarla serve il DOI dell'italiano gia' assegnato. Farlo",
            "nell'ordine inverso costringe a tornare indietro su tre record.",
            "",
            f"**Licenza per tutti i volumi**: {LICENZA} — {LICENZA_URL}",
            "",
            "---",
            "",
        ]
        corpo = "\n---\n\n".join(scheda(cfg, b, lang) for b in books)
        dest = os.path.join(dest_dir, cfg["file"])
        io.open(dest, "w", encoding="utf-8").write("\n".join(testa) + corpo)
        print(f"  ✓ {len(books)} schede → Deposito/{cfg['file']}")


if __name__ == "__main__":
    main()
