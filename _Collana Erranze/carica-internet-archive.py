#!/usr/bin/env python3
"""Carica i volumi su Internet Archive prendendo i metadati dai registri.

Prima volta:
    ~/Library/Python/3.13/bin/ia configure      # email e password dell'account

Uso:
    python3 carica-internet-archive.py --prova                 # non carica: mostra
    python3 carica-internet-archive.py --volume 14
    python3 carica-internet-archive.py --lang en --volume 3
    python3 carica-internet-archive.py --tutti --pausa 120
    python3 carica-internet-archive.py --volume 14 --sostituisci   # ricarica dopo una correzione

Perche' da riga di comando e non dal browser: il client ha i ritentativi
automatici con attesa progressiva, quindi davanti al 503 «SlowDown» dell'Archive
insiste da solo invece di chiedere a te di premere un pulsante; riprende i
trasferimenti interrotti; e non dipende da una scheda aperta.

Salta i volumi gia' presenti invece di duplicarli: su Internet Archive un item
creato per sbaglio non si cancella, si puo' solo chiedere che venga oscurato.

Quando un volume viene corretto dopo la pubblicazione, i file sull'Archive
restano quelli vecchi e nessuna delle due modalita' normali li tocca: --completa
aggiunge solo cio' che manca. Serve --sostituisci, che riscrive sopra i file con
lo stesso nome. Il flag e' esplicito apposta: la sostituzione non cancella nulla,
le versioni precedenti restano nella cronologia dell'item e restano scaricabili.
"""
import io
import json
import os
import re
import sys
import time
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)
LICENZA_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

LANGS = {
    "it": {"registry": "serie.json", "root": "", "serie": "Collana Erranze", "iso": "ita"},
    "en": {"registry": "series-en.json", "root": "English", "serie": "Errancies", "iso": "eng"},
}


def slug(s):
    """Stessa logica di genera-schede-deposito.py: gli identificatori devono
    coincidere con quelli stampati nelle schede."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def anno(cartella, book):
    md = os.path.join(cartella, book["file"] + ".md")
    m = re.search(r"\*© (\d{4})", io.open(md, encoding="utf-8").read(1200))
    return m.group(1) if m else "2026"


def prepara(cfg, book):
    cartella = os.path.join(BASE, cfg["root"], book["folder"]) if cfg["root"] \
        else os.path.join(BASE, book["folder"])
    ident = f"{slug(cfg['serie'])}-{book['n']:02d}-{slug(book['file'])}"
    files = [p for p in (os.path.join(cartella, book["file"] + ".epub"),
                         os.path.join(cartella, book["file"] + " - Interno.pdf"))
             if os.path.exists(p)]
    meta = {
        "mediatype": "texts",
        "collection": "opensource",
        "title": book["title"],
        "creator": "Giovanni Martini",
        "date": anno(cartella, book),
        "language": cfg["iso"],
        "subject": book.get("keywords", []),
        "description": book.get("blurb", ""),
        "licenseurl": LICENZA_URL,
        "volume": str(book["n"]),
        "series": cfg["serie"],
    }
    return ident, files, meta


def main():
    argv = sys.argv[1:]

    def opt(nome, default=None):
        if nome in argv:
            i = argv.index(nome)
            return argv[i + 1] if i + 1 < len(argv) else default
        return default

    prova = "--prova" in argv
    sostituisci = "--sostituisci" in argv
    lang = opt("--lang", "it")
    vol = opt("--volume")
    pausa = int(opt("--pausa", "90"))
    cfg = LANGS[lang]

    with open(os.path.join(SCRIPT_DIR, cfg["registry"]), encoding="utf-8") as f:
        books = json.load(f)["books"]
    if vol:
        books = [b for b in books if b["n"] == int(vol)]
    elif "--tutti" not in argv:
        sys.exit("Serve --volume N oppure --tutti (e --prova per vedere senza caricare).")

    if not prova:
        try:
            from internetarchive import get_item, upload  # noqa: F401
        except ImportError:
            sys.exit("Manca la libreria: python3 -m pip install --user internetarchive")
        import internetarchive
        if not internetarchive.config.get_config().get("s3", {}).get("access"):
            sys.exit("Client non configurato: esegui prima  ia configure")

    for i, book in enumerate(books):
        ident, files, meta = prepara(cfg, book)
        print(f"\n[{book['n']:>2}] {ident}")
        for f_ in files:
            print(f"      {os.path.basename(f_)}  ({round(os.path.getsize(f_)/1024)} KB)")
        if not files:
            print("      NESSUN FILE TROVATO, salto")
            continue
        if prova:
            print("      metadati:", json.dumps(meta, ensure_ascii=False)[:300], "…")
            continue

        from internetarchive import get_item, upload
        item = get_item(ident)
        if item.exists:
            presenti = {f.name for f in item.get_files()}
            mancanti = [f_ for f_ in files if os.path.basename(f_) not in presenti]
            if sostituisci:
                print(f"      item presente, sostituisco {len(files)} file"
                      " (le versioni precedenti restano nella cronologia)")
            elif not mancanti:
                print("      item gia' completo sull'Archive, salto"
                      " (se il volume e' stato corretto serve --sostituisci)")
                continue
            elif "--completa" not in argv:
                print(f"      item presente ma incompleto ({len(mancanti)} file mancanti):"
                      " rilancia con --completa")
                continue
            else:
                print(f"      item presente, aggiungo {len(mancanti)} file mancanti")
                files = mancanti
        try:
            # upload() NON solleva eccezioni sugli errori HTTP: restituisce le
            # risposte. Senza controllarle si stamperebbe un successo falso.
            risposte = upload(ident, files=files, metadata=meta, retries=20,
                              retries_sleep=30, verbose=True)
            falliti = [r for r in risposte if getattr(r, "status_code", None) not in (200, 201)]
            if falliti:
                for r in falliti:
                    print(f"      ✗ {getattr(r, 'status_code', '?')} su "
                          f"{os.path.basename(getattr(r.request, 'url', '?'))}")
                print("      item incompleto: rilancia con --completa quando la coda si libera")
            else:
                print(f"      ✓ caricato ({len(risposte)} file)")
        except Exception as e:                                  # noqa: BLE001
            print(f"      ✗ errore: {e}")
        if i < len(books) - 1:
            print(f"      pausa di {pausa}s per non incappare nel limite di account")
            time.sleep(pausa)


if __name__ == "__main__":
    main()
