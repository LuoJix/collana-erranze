#!/usr/bin/env python3
"""Dai CSV di verifica genera una scheda stampabile per volume.

Uso:
    python3 schede-verifica.py

Genera <volume>/Bozze/Note/verifica-fatti.html per ogni volume che abbia un
verifica-fatti.csv accanto. Si apre nel browser e si stampa (togliere la
spunta a "Stampa intestazioni e pie' di pagina").

Una tabella a nove colonne su A4 non e' leggibile: o rimpicciolisci il corpo
o sfori in larghezza. Qui ogni rilievo diventa un blocco verticale, con le
caselle da barrare e una riga per gli appunti. Si apre nel browser e si stampa.
"""
import csv
import html
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(os.path.dirname(SCRIPT_DIR), "Completati")

# I volumi da lavorare sono quelli che hanno un verifica-fatti.csv in
# Bozze/Note/: la scheda si genera per quelli e per nessun altro. A volume
# chiuso il CSV si cancella, e questo script smette da solo di occuparsene.
VOLUMI = sorted(
    (d, d.split(" — ")[0])
    for d in os.listdir(BASE)
    if os.path.exists(os.path.join(BASE, d, "Bozze", "Note", "verifica-fatti.csv"))
)

CSS = """
@page { size: A4; margin: 16mm 15mm 14mm 15mm; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.38 Charter, Georgia, serif; color: #000; margin: 0;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1 { font-size: 15pt; margin: 0 0 2mm; letter-spacing: .01em; }
.guida { font-size: 8.5pt; color: #444; margin: 0 0 6mm; padding-bottom: 3mm;
         border-bottom: .5pt solid #999; }
.guida b { color: #000; }
.scheda { border-left: 2.2pt solid #000; padding: 0 0 0 3.5mm;
          margin: 0 0 5.5mm; page-break-inside: avoid; break-inside: avoid; }
.scheda.bassa { border-left-color: #b0b0b0; }
.scheda.media { border-left-color: #6a6a6a; }
.testa { font-size: 8pt; letter-spacing: .06em; text-transform: uppercase;
         color: #555; margin-bottom: 1.2mm; }
.testa .id { font-weight: 700; color: #000; letter-spacing: .04em; }
.testa .alta { font-weight: 700; color: #000; }
.cit { font-style: italic; margin: 0 0 1.2mm; }
p { margin: 0 0 1.2mm; }
.et { font-variant: small-caps; font-style: normal; color: #555;
      letter-spacing: .03em; }
.caselle { margin-top: 2.2mm; font-size: 9pt; color: #333; }
.caselle span { margin-right: 7mm; white-space: nowrap; }
.q { font-size: 13pt; vertical-align: -1.5pt; letter-spacing: .5mm; }
.note { margin-top: 1.6mm; border-bottom: .5pt dotted #999; height: 5mm; }
"""

for cartella, titolo in VOLUMI:
    src = os.path.join(BASE, cartella, "Bozze", "Note", "verifica-fatti.csv")
    if not os.path.exists(src):        # volume gia' chiuso: niente CSV, niente scheda
        continue
    with open(src, encoding="utf-8-sig", newline="") as f:
        righe = list(csv.DictReader(f, delimiter=";"))

    n_alte = sum(1 for r in righe if r["Gravita"] == "ALTA")
    parti = [
        "<!doctype html><html lang='it'><meta charset='utf-8'>",
        f"<title>Verifica dei fatti — {html.escape(titolo)}</title>",
        f"<style>{CSS}</style>",
        f"<h1>Verifica dei fatti — {html.escape(titolo)}</h1>",
        "<p class='guida'>"
        f"{len(righe)} rilievi, {n_alte} di gravità alta, in ordine di riga nel testo. "
        "Per ciascuno: <b>da correggere</b> se l'errore c'è, "
        "<b>lascia com'è</b> se il rilievo è sbagliato o la scelta era voluta, "
        "<b>da vedere</b> se vuoi guardarci meglio. "
        "La riga punteggiata è per una correzione diversa da quella proposta. "
        "Poi basta rimandarmi le sigle.</p>",
    ]

    for r in righe:
        grav = r["Gravita"]
        cls = {"ALTA": "alta", "MEDIA": "media", "BASSA": "bassa"}[grav]
        cat = r["Categoria"]
        cat_txt = ("contraddizione interna" if cat.startswith("CONTRAD") else cat)
        g = (f"<span class='alta'>{grav}</span>" if grav == "ALTA" else grav)
        parti += [
            f"<div class='scheda {cls}'>",
            f"<div class='testa'><span class='id'>{html.escape(r['ID'])}</span> · "
            f"riga {html.escape(r['Riga'])} · {html.escape(cat_txt)} · {g}</div>",
            f"<p class='cit'>{html.escape(r['Nel libro'])}</p>",
            f"<p><span class='et'>perché è sbagliata</span> &nbsp;"
            f"{html.escape(r['Perche e sbagliata'])}</p>",
            f"<p><span class='et'>correzione</span> &nbsp;"
            f"{html.escape(r['Correzione proposta'])}</p>",
            "<div class='caselle'>"
            "<span><span class='q'>☐</span> da correggere</span>"
            "<span><span class='q'>☐</span> lascia com'è</span>"
            "<span><span class='q'>☐</span> da vedere</span></div>",
            "<div class='note'></div>",
            "</div>",
        ]

    dest = os.path.join(BASE, cartella, "Bozze", "Note", "verifica-fatti.html")
    open(dest, "w", encoding="utf-8").write("\n".join(parti))
    print(f"  ✓ {titolo}: {len(righe)} schede → {dest}")
