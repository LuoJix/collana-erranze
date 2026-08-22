#!/usr/bin/env python3
"""Riallinea il Sommario alle intestazioni reali del volume.

Il Sommario deve rispecchiare la struttura del file: `##` come voci in
grassetto, `###` come trattini indentati. Ogni volta che si rinomina o si
sposta una sottosezione il Sommario resta indietro, e verifica-standard.py
lo segnala. Questo script lo riscrive dalle intestazioni.

**Attenzione alla direzione.** Lo script fa vincere il corpo sul Sommario.
Se il Sommario e' piu' ricco delle intestazioni (`- Borges: *El Golem*`
contro `### Borges`) la voce ricca viene persa: in quel caso conviene
arricchire le intestazioni a mano, non lanciare questo script. Per questo
la modalita' predefinita e' la sola anteprima.

Uso:
    python3 rigenera-sommario.py --volume 10            # anteprima del diff
    python3 rigenera-sommario.py --volume 10 --scrivi   # applica
    python3 rigenera-sommario.py --lang en --volume 1
"""

import difflib
import io
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)

LANGS = {
    "it": {
        "registry": "serie.json", "root": "",
        "toc": "Sommario", "biblio": "Testi di riferimento",
        "escluse": ["Sommario", "Testi di riferimento", "Nella stessa collana", "L'autore"],
    },
    "en": {
        "registry": "series-en.json", "root": "English",
        "toc": "Contents", "biblio": "Further Reading",
        "escluse": ["Contents", "Further Reading", "Also in This Series", "About the Author"],
    },
}

RE_HEADING = re.compile(r"^(#{1,6}) +(.*?)\s*$")


def load_books(cfg):
    with open(os.path.join(SCRIPT_DIR, cfg["registry"]), encoding="utf-8") as f:
        return json.load(f)["books"]


def voce_h2(titolo):
    """`Parte Prima: La linea` -> `**Parte Prima**: La linea`."""
    if ": " in titolo:
        etichetta, resto = titolo.split(": ", 1)
        return f"**{etichetta}**: {resto}"
    return f"**{titolo}**"


def costruisci(cfg, righe):
    """Il nuovo blocco di Sommario, dalle intestazioni del file."""
    escluse = {t.lower() for t in cfg["escluse"]}
    biblio = cfg["biblio"].lower()

    blocchi, corrente = [], None
    dentro_codice = False
    for l in righe:
        if l.startswith("```"):
            dentro_codice = not dentro_codice
            continue
        if dentro_codice:
            continue
        m = RE_HEADING.match(l)
        if not m:
            continue
        liv, titolo = len(m.group(1)), m.group(2)
        if liv == 2:
            basso = titolo.strip().lower()
            if basso in escluse and basso != biblio:
                corrente = None
                continue
            corrente = (titolo, [])
            blocchi.append(corrente)
        elif liv == 3 and corrente is not None:
            # i Testi di riferimento hanno sottosezioni tematiche, non voci di indice
            if corrente[0].strip().lower() != biblio:
                corrente[1].append(titolo)

    out = []
    for titolo, figli in blocchi:
        out.append(voce_h2(titolo))
        out.extend(f"- {f}" for f in figli)
        out.append("")
    return out


def rigenera(cfg, book, scrivi):
    path = os.path.join(ROOT, cfg["root"], book["folder"], book["file"] + ".md")
    if not os.path.exists(path):
        print(f"  ! file non trovato: {path}", file=sys.stderr)
        return False

    righe = io.open(path, encoding="utf-8").read().split("\n")

    inizio = fine = None
    for i, l in enumerate(righe):
        m = RE_HEADING.match(l)
        if not m:
            continue
        if inizio is None and len(m.group(1)) == 2 and m.group(2).strip() == cfg["toc"]:
            inizio = i
        elif inizio is not None and len(m.group(1)) <= 2:
            fine = i
            break
    if inizio is None:
        print(f"  ! `## {cfg['toc']}` non trovato", file=sys.stderr)
        return False
    fine = fine if fine is not None else len(righe)

    vecchio = righe[inizio + 1:fine]
    separatore = ["---", ""] if "---" in [r.strip() for r in vecchio] else []
    nuovo = [""] + costruisci(cfg, righe) + separatore

    while nuovo and nuovo[-1] == "":
        nuovo.pop()
    nuovo.append("")

    if vecchio == nuovo:
        print(f"Vol. {book['n']} — {book['title']}: gia' allineato")
        return True

    diff = difflib.unified_diff(vecchio, nuovo, lineterm="",
                                fromfile=f"{cfg['toc']} attuale", tofile=f"{cfg['toc']} rigenerato")
    print(f"Vol. {book['n']} — {book['title']}")
    for l in diff:
        print("  " + l)

    if scrivi:
        righe[inizio + 1:fine] = nuovo
        io.open(path, "w", encoding="utf-8").write("\n".join(righe))
        print("  ✓ scritto")
    else:
        print("  (anteprima: rilancia con --scrivi per applicare)")
    return True


def main():
    argv = sys.argv[1:]

    def opt(nome, default=None):
        if nome in argv:
            i = argv.index(nome)
            return argv[i + 1] if i + 1 < len(argv) else default
        return default

    lang = opt("--lang", "it") or "it"
    if lang not in LANGS:
        print(f"Errore: lingua '{lang}' sconosciuta", file=sys.stderr)
        sys.exit(1)
    cfg = LANGS[lang]

    books = load_books(cfg)
    vol = opt("--volume")
    if vol:
        target = [b for b in books if b["n"] == int(vol)]
        if not target:
            print(f"Errore: volume {vol} non trovato", file=sys.stderr)
            sys.exit(1)
    else:
        target = books

    for b in target:
        rigenera(cfg, b, "--scrivi" in argv)
        print()


if __name__ == "__main__":
    main()
