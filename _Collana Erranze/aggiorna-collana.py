#!/usr/bin/env python3
"""Aggiorna la Collana Erranze (it) o la serie Errancies (en).

Uso normale (nuovo volume):
    python3 aggiorna-collana.py
    → elabora solo l'ultimo volume del registro

Volume singolo o rebuild completo:
    python3 aggiorna-collana.py --volume 4
    python3 aggiorna-collana.py --tutti

Edizione inglese (registro series-en.json, cartelle sotto English/):
    python3 aggiorna-collana.py --lang en --volume 1
    python3 aggiorna-collana.py --lang en --tutti
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)          # Progetti culturali/
CALIBRE = "/Applications/calibre.app/Contents/MacOS/ebook-convert"

BIO_IT = (
    "Giovanni Martini, sociologo, vive in Trentino sull'Altopiano di Pine'. "
    "Lettore onnivoro con una predilezione per la narrativa speculativa, la "
    "filosofia e la scienza, coltiva da sempre la ricerca di connessioni tra "
    "discipline distanti: fisica e coscienza, Oriente e Occidente, mito e "
    "tecnologia. Preferisce le tensioni irrisolte alle sintesi facili. "
    "La *Collana Erranze* è il luogo in cui raccoglie questi sconfinamenti."
)

BIO_EN = (
    "Giovanni Martini is a sociologist living in Trentino, on the Pine' plateau "
    "in northern Italy. An omnivorous reader with a preference for speculative "
    "fiction, philosophy and science, he has always looked for connections "
    "between distant disciplines: physics and consciousness, East and West, myth "
    "and technology. He prefers unresolved tensions to easy syntheses. "
    "*Errancies* is the English counterpart of his Italian series *Collana "
    "Erranze*, and the place where he collects these border crossings."
)

# Dichiarazione sull'uso dell'AI. Dice cose diverse nelle due collane perche'
# diverso e' il lavoro: in italiano gli strumenti rifiniscono un testo gia'
# scritto, in inglese la riscrittura e' fatta insieme. Tenere allineata alla
# riga corrispondente in genera-stampa.py (pagina del copyright del cartaceo).
AI_IT = (
    "*Il testo è stato scritto dall'autore; strumenti di intelligenza "
    "artificiale sono stati utilizzati come supporto editoriale (rifinitura "
    "linguistica e coerenza del testo).*"
)

AI_EN = (
    "*The Italian original was written by the author, who rewrote rather than "
    "translated it for this English edition, working with artificial "
    "intelligence tools throughout.*"
)

# Descrizione e data scritte nei metadati dell'epub. Servono a distinguere le
# copie: su Z-Library non si sostituisce un file, si aggiunge, quindi versioni
# diverse dello stesso volume convivono con identici titolo, autore e anno. La
# data e' quella di generazione, cosi' la riga resta vera a ogni rebuild.
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

MESI_EN = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]

LANGS = {
    "it": {
        "registry": "serie.json",
        "root": "",                       # relativo a ROOT
        "epub_dest": "Progetti epub",
        "series": "Collana Erranze",
        "header_re": r"\*Collana Erranze(?: · (?:\d+|\[N\]))? — Giovanni Martini\*",
        "header_fmt": "*Collana Erranze · {n} — Giovanni Martini*",
        "also_heading": "## Nella stessa collana",
        "author_heading": "## L'autore",
        "toc_title": "Sommario",
        "bio": BIO_IT,
        "colophon_fmt": None,
        "ai_line": AI_IT,
        "ai_re": r"^\*Il testo è stato scritto dall'autore.*$",
        "months": MESI_IT,
        "note_fmt": "Edizione aggiornata al {day} {month} {year}.",
    },
    "en": {
        "registry": "series-en.json",
        "root": "English",
        "epub_dest": os.path.join("Progetti epub", "English"),
        "series": "Errancies",
        "header_re": r"\*Errancies(?: · (?:\d+|\[N\]))? — Giovanni Martini\*",
        "header_fmt": "*Errancies · {n} — Giovanni Martini*",
        "also_heading": "## Also in This Series",
        "author_heading": "## About the Author",
        "toc_title": "Contents",
        "bio": BIO_EN,
        "colophon_fmt": (
            "*Originally published in Italian as* {title} "
            "*(Collana Erranze, vol. {n}).*"
        ),
        "ai_line": AI_EN,
        "ai_re": r"^\*The Italian original was written by the author.*$",
        "months": MESI_EN,
        "note_fmt": "Edition updated {day} {month} {year}.",
    },
}

COLOPHON_RE = re.compile(r"^\*Originally published in Italian as\*.*$", re.MULTILINE)
COPYRIGHT_RE = re.compile(r"^\*© .*$", re.MULTILINE)


def load_books(cfg):
    with open(os.path.join(SCRIPT_DIR, cfg["registry"]), encoding="utf-8") as f:
        return json.load(f)["books"]


def book_dir(cfg, book):
    return os.path.join(ROOT, cfg["root"], book["folder"])


def set_colophon(content, cfg, book):
    """Inserisce (o aggiorna) la riga di colophon sotto il copyright."""
    if not cfg["colophon_fmt"] or "original" not in book:
        return content

    line = cfg["colophon_fmt"].format(
        title=book["original"]["title"], n=book["original"]["n"]
    )

    if COLOPHON_RE.search(content):
        return COLOPHON_RE.sub(lambda _: line, content, count=1)

    m = COPYRIGHT_RE.search(content)
    if not m:
        print("  ! riga di copyright non trovata: colophon non inserito", file=sys.stderr)
        return content
    return content[: m.end()] + "\n\n" + line + content[m.end():]


def set_ai_notice(content, cfg):
    """Inserisce (o aggiorna) la dichiarazione sull'AI in fondo alla testata.

    Va dopo il copyright e, se c'e', dopo il colophon dell'edizione inglese:
    e' l'ultima riga prima del separatore. Il cartaceo non ne risente, perche'
    genera-stampa.py legge il .md solo dal Prologo in poi e costruisce la sua
    pagina del copyright per conto suo.
    """
    line = cfg["ai_line"]
    ai_re = re.compile(cfg["ai_re"], re.MULTILINE)

    if ai_re.search(content):
        return ai_re.sub(lambda _: line, content, count=1)

    anchor = COLOPHON_RE.search(content) or COPYRIGHT_RE.search(content)
    if not anchor:
        print("  ! riga di copyright non trovata: dichiarazione AI non inserita", file=sys.stderr)
        return content
    return content[: anchor.end()] + "\n\n" + line + content[anchor.end():]


def update_md(cfg, book, all_books):
    path = os.path.join(book_dir(cfg, book), book["file"] + ".md")
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Imposta il numero nella riga della collana
    content = re.sub(
        cfg["header_re"], cfg["header_fmt"].format(n=book["n"]), content
    )

    # Riga di origine dell'edizione italiana (solo edizione inglese)
    content = set_colophon(content, cfg, book)

    # Dichiarazione sull'uso dell'AI, ultima riga della testata
    content = set_ai_notice(content, cfg)

    # Rimuovi sezioni finali esistenti (verranno riscritte)
    for marker in ["\n\n" + cfg["also_heading"], "\n\n" + cfg["author_heading"]]:
        if marker in content:
            content = content[: content.index(marker)]
    content = content.rstrip()

    # Aggiungi l'elenco dei volumi precedenti
    previous = [b for b in all_books if b["n"] < book["n"]]
    if previous:
        lines = [f"{b['n']}. *{b['title']}*" for b in previous]
        content += "\n\n" + cfg["also_heading"] + "\n\n" + "\n".join(lines)

    # Aggiungi la biografia
    content += "\n\n" + cfg["author_heading"] + "\n\n" + cfg["bio"] + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def epub_description(cfg, book, oggi):
    """Descrizione dell'epub: quarta di copertina piu' data della versione.

    Testo semplice, non HTML: calibre scrive questa stringa in <dc:description>
    escapando quello che riceve, quindi un <p> arriverebbe al lettore come tag
    visibile invece che come paragrafo.
    """
    nota = cfg["note_fmt"].format(
        day=oggi.day, month=cfg["months"][oggi.month - 1], year=oggi.year
    )
    blurb = (book.get("blurb") or "").strip()
    return f"{blurb}\n\n{nota}" if blurb else nota


def build_epub(cfg, lang, book, md_path):
    folder = book_dir(cfg, book)
    epub_path = os.path.join(folder, book["file"] + ".epub")
    cover = os.path.join(folder, "Bozze", "Copertina", "cover.png")
    oggi = date.today()

    result = subprocess.run(
        [
            CALIBRE, md_path, epub_path,
            "--title", book["title"],
            "--authors", "Giovanni Martini",
            "--language", lang,
            "--cover", cover,
            # parole chiave del registro, le stesse che finiscono nelle schede
            # di caricamento generate da genera-schede-deposito.py
            "--tags", ", ".join(book.get("keywords", [])),
            # distinguono questa copia da quelle gia' in circolazione
            "--comments", epub_description(cfg, book, oggi),
            # mezzogiorno e non mezzanotte: calibre converte in UTC, e l'ora
            # locale 00:00 tornerebbe indietro al giorno prima
            "--pubdate", oggi.isoformat() + "T12:00:00",
            "--series", cfg["series"],
            "--series-index", str(book["n"]),
            "--level1-toc", "//h:h2",
            "--level2-toc", "//h:h3",
            "--toc-title", cfg["toc_title"],
            "--epub-version", "3",
            # ai default di calibre (footnotes, tables, toc) si aggiunge nl2br:
            # nei Testi di riferimento e nei versi citati le righe sono separate
            # da un solo a capo, che senza questa estensione viene fuso in un
            # unico paragrafo. Tenere allineato a genera-stampa.py.
            "--markdown-extensions", "footnotes,tables,toc,nl2br",
        ]
        # CSS in piu' per un volume solo, dal campo epub_extra_css del registro.
        # Nato per il vol. 25, la cui foto (500 px) senza width:100% compare
        # piccola sullo schermo; non va reso generale, perche' cambierebbe anche
        # l'immagine del vol. 24.
        + (["--extra-css", book["epub_extra_css"]] if book.get("epub_extra_css") else []),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  ✗ Errore epub: {result.stderr[-300:]}", file=sys.stderr)
        return None

    return epub_path


def copy_epub(cfg, epub_path, book):
    dest_dir = os.path.join(ROOT, cfg["epub_dest"])
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(epub_path, os.path.join(dest_dir, book["file"] + ".epub"))


def process(cfg, lang, book, all_books):
    print(f"Vol. {book['n']} — {book['title']}")
    md_path = update_md(cfg, book, all_books)
    print(f"  ✓ .md aggiornato")
    epub_path = build_epub(cfg, lang, book, md_path)
    if epub_path:
        copy_epub(cfg, epub_path, book)
        print(f"  ✓ .epub generato e copiato")
        return True
    return False


def main():
    argv = sys.argv[1:]

    lang = "it"
    if "--lang" in argv:
        idx = argv.index("--lang")
        try:
            lang = argv[idx + 1]
        except IndexError:
            print("Errore: --lang richiede un codice (it | en)", file=sys.stderr)
            sys.exit(1)
    if lang not in LANGS:
        print(f"Errore: lingua '{lang}' sconosciuta (attese: {', '.join(LANGS)})", file=sys.stderr)
        sys.exit(1)
    cfg = LANGS[lang]

    tutti = "--tutti" in argv
    volume = None
    if "--volume" in argv:
        idx = argv.index("--volume")
        try:
            volume = int(argv[idx + 1])
        except (IndexError, ValueError):
            print("Errore: --volume richiede un numero (es. --volume 4)", file=sys.stderr)
            sys.exit(1)

    books = load_books(cfg)
    if not books:
        print(f"{cfg['series']}: nessun volume in {cfg['registry']} (books e' vuoto).")
        return

    if tutti:
        print(f"{cfg['series']} — rebuild completo ({len(books)} volumi)\n")
        targets = books
    elif volume is not None:
        targets = [b for b in books if b["n"] == volume]
        if not targets:
            print(f"Errore: volume {volume} non trovato in {cfg['registry']}", file=sys.stderr)
            sys.exit(1)
        print(f"{cfg['series']} — aggiornamento volume {volume}\n")
    else:
        targets = [books[-1]]
        print(f"{cfg['series']} — nuovo volume\n")

    errors = []
    for book in targets:
        if not process(cfg, lang, book, books):
            errors.append(book["n"])
        print()

    if errors:
        print(f"Errori nei volumi: {errors}")
        sys.exit(1)
    else:
        print("Fatto.")


if __name__ == "__main__":
    main()
