#!/usr/bin/env python3
"""Elenco dei volumi da ricaricare su KDP dopo un giro di rigenerazione.

Scrive Diagnosi/da-ricaricare.txt con, per ogni volume delle due collane, le
pagine e la larghezza del dorso. Le pagine sono LETTE DAI PDF appena generati,
non dall'output dello script che li ha fatti ne' dal campo 'pages' dei registri:
un elenco compilato a mano nell'agosto 2026 riportava valori piu' bassi di 2-10
pagine per volume, mai riprodotti da nessuna configurazione, e nessuno se n'era
accorto perche' nessuno li aveva ricontrollati.

    python3 elenco-da-ricaricare.py --motivo "Quarta di copertina rifatta"
    python3 elenco-da-ricaricare.py --solo-copertina --motivo "..."

--solo-copertina lo annota nell'intestazione: quando l'interno non e' cambiato
(stesse pagine, stesso dorso) su KDP basta sostituire la copertina.
"""

import datetime
import json
import os
import sys

from pypdf import PdfReader

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)
OUT = os.path.join(SCRIPT_DIR, "Diagnosi", "da-ricaricare.txt")

SPINE_FACTOR = 0.0025  # crema, come PAPER in genera-stampa.py

COLLANE = [
    ("Erranze", "serie.json", os.path.join(BASE, "Progetti stampa")),
    ("Errancies", "series-en.json", os.path.join(BASE, "Progetti stampa", "English")),
]


def pagine_del_pdf(path):
    return len(PdfReader(path).pages)


def raccogli():
    righe, mancanti, divergenze = [], [], []
    for collana, registro, dest in COLLANE:
        books = json.load(open(os.path.join(SCRIPT_DIR, registro), encoding="utf-8"))["books"]
        for b in sorted(books, key=lambda b: b["n"]):
            pdf = os.path.join(dest, b["file"] + " - Interno.pdf")
            if not os.path.exists(pdf):
                mancanti.append(f"{collana} {b['n']}: manca {pdf}")
                continue
            pagine = pagine_del_pdf(pdf)
            dorso = max(pagine, 24) * SPINE_FACTOR
            if b.get("pages") and b["pages"] != pagine:
                divergenze.append(f"{collana} {b['n']}: registro {b['pages']}, pdf {pagine}")
            righe.append((collana, b["n"], pagine, dorso, b["title"]))
    return righe, mancanti, divergenze


def main():
    motivo = ""
    if "--motivo" in sys.argv:
        i = sys.argv.index("--motivo")
        motivo = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    solo_cop = "--solo-copertina" in sys.argv

    righe, mancanti, divergenze = raccogli()
    oggi = datetime.date.today().isoformat()

    out = [f"Volumi da ricaricare su KDP — elenco del {oggi}", ""]
    if motivo:
        out += [motivo, ""]
    out += [
        "Pagine LETTE DAI PDF generati, non dall'output dello script.",
        "",
    ]
    out.append(
        "VA RICARICATA LA SOLA COPERTINA: l'interno non e' cambiato, pagine e dorso"
        "\nsono quelli gia' online."
        if solo_cop else
        "VANNO RICARICATI interno E copertina: il dorso dipende dalle pagine."
    )
    out += ["", "Su KDP c'e' la sola scheda Paperback (le schede Kindle sono state",
            "eliminate il 2026-08-16): copertina-stampa.pdf e Interno.pdf, entrambi",
            "anche in Progetti stampa/.", ""]
    out.append(f" {'Collana':<11} {'Vol':>3} {'pagine':>7} {'dorso':>8}   titolo")
    for collana, n, pagine, dorso, titolo in righe:
        out.append(f" {collana:<11} {n:>3} {pagine:>7} {dorso:>7.3f}in   {titolo}")

    if divergenze:
        out += ["", "Il campo 'pages' dei registri non concorda con i PDF:"] + \
               [f"  {d}" for d in divergenze]
    if mancanti:
        out += ["", "PDF non trovati (volume non rigenerato?):"] + \
               [f"  {m}" for m in mancanti]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    print(f"✓ {len(righe)} volumi in Diagnosi/da-ricaricare.txt")
    for d in divergenze:
        print(f"  ! registro da correggere: {d}")
    for m in mancanti:
        print(f"  ! {m}")


if __name__ == "__main__":
    main()
