#!/usr/bin/env python3
"""Ordina i volumi della Collana Erranze per densita' di fatti verificabili.

Non giudica la correttezza: conta la superficie esposta. Un volume che cita
molti titoli, molte date e molti nomi ha molte occasioni di sbagliare; un
volume che argomenta ne ha poche. Serve a decidere da dove partire con la
verifica dei fatti, non a dire dove ci sono errori.

Conta solo il corpo: testata, Sommario, Testi di riferimento e sezioni
automatiche restano fuori, perche' il rischio sta nelle affermazioni del testo,
non nell'elenco bibliografico.
"""
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)  # Progetti culturali/
REG = os.path.join(BASE, "_Collana Erranze", "serie.json")
ESCLUSE = {"sommario", "testi di riferimento", "nella stessa collana", "l'autore"}

RE_W = re.compile(r"[\wÀ-ÿ'’-]+")
RE_TITOLO = re.compile(r"\*([A-ZÀ-Ý][^*\n]{2,80})\*")
RE_ANNO = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")
RE_SECOLO = re.compile(r"\b[IVXL]{1,5} (?:sec\.|secolo)\b")
RE_NOME = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ']{2,} [A-ZÀ-Ý][a-zà-ÿ']{2,}\b")


def corpo(path):
    fuori, out = True, []
    for l in open(path, encoding="utf-8"):
        if l.startswith("#"):
            liv = len(l) - len(l.lstrip("#"))
            if liv <= 2:
                fuori = liv == 1 or l.lstrip("# ").strip().lower() in ESCLUSE
            continue
        if not fuori:
            out.append(l)
    return " ".join(out)


books = json.load(open(REG))["books"]
righe = []
for b in books:
    p = os.path.join(BASE, b["folder"], b["file"] + ".md")
    if not os.path.exists(p):
        continue
    t = corpo(p)
    w = len(RE_W.findall(t)) or 1
    tit = len(set(RE_TITOLO.findall(t)))
    ann = len(set(RE_ANNO.findall(t)))
    sec = len(RE_SECOLO.findall(t))
    nom = len(set(RE_NOME.findall(t)))
    fatti = tit + ann + sec + nom
    righe.append((b["n"], b["title"].split(" — ")[0], w, tit, ann, sec, nom,
                  fatti, 1000.0 * fatti / w))

righe.sort(key=lambda r: -r[8])
print(f"{'#':>3}  {'volume':<34} {'parole':>6} {'titoli':>6} {'date':>5} "
      f"{'sec.':>4} {'nomi':>5} {'tot':>5} {'/1000':>6}")
print("-" * 84)
for n, tit, w, a, b_, c, d, f, dens in righe:
    print(f"{n:>3}  {tit[:34]:<34} {w:>6} {a:>6} {b_:>5} {c:>4} {d:>5} {f:>5} {dens:>6.1f}")
med = sorted(r[8] for r in righe)[len(righe) // 2]
print("-" * 84)
print(f"mediana della collana: {med:.1f} fatti verificabili per mille parole")
