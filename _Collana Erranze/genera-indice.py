#!/usr/bin/env python3
"""Genera la pagina web dell'indice di una collana dal suo registro.

Uso:
    python3 genera-indice.py                 # italiano -> indice-collana.html
    python3 genera-indice.py --lang en       # inglese  -> indice-errancies.html
    python3 genera-indice.py --out <file>
    python3 genera-indice.py --verifica       # confronta il registro col foglio

Produce una pagina sola, da pubblicare come artifact, con tutti i volumi:
numero, titolo, sottotitolo, quarta di copertina, pagine, e i due link per
volume, l'ebook gratuito su Zenodo e il cartaceo su Amazon.

Non e' l'inventario interno: quello resta 'Elenco Progetti Culturali.pdf',
prodotto da aggiorna-elenco.py. Questa e' la vetrina rivolta a chi legge.

Monocroma come le copertine: il campo 'color' del registro non entra qui,
esattamente come non entra in genera-copertina.py. I volumi si distinguono
per numero e titolo, non per colore.
"""

import argparse
import csv
import html
import json
import sys
import unicodedata
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
MESI_EN = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def euro(v):
    return f"{v:.2f}".replace(".", ",") + " €"


def dollaro(v):
    return f"${v:.2f}"


def migliaia_it(n):
    return format(n, ",").replace(",", ".")


# Le due serie, con le loro etichette. La dichiarazione sull'uso dell'AI e'
# diversa: in inglese non e' rifinitura ma riscrittura, e la riga lo dice.
# Se cambia qui va cambiata anche in aggiorna-collana.py (AI_IT / AI_EN) e in
# genera-stampa.py, altrimenti le tre uscite dichiarano cose diverse.
LANGS = {
    "it": {
        "registry": "serie.json",
        "out": "indice-collana.html",
        "occhiello": "Collana",
        "strip": "Collana ",
        "amazon": "https://www.amazon.it/dp/",
        "prezzo": "price_paperback_eur",
        "money": euro,
        "mesi": MESI,
        "conta": "{n} volumi · {p} pagine · aggiornato al {d}",
        "testo": "Testo",
        "tema": {"auto": "Tema: automatico", "dark": "Tema: scuro",
                 "light": "Tema: chiaro"},
        "ebook": "Ebook", "gratis": "gratuito", "carta": "Cartaceo",
        "aria": ("Testo piccolo", "Testo medio", "Testo grande"),
        "origine": None,
        "programma": None,
        "licenza": ("Tutti i volumi sono pubblicati con licenza "
                    "<a href=\"{cc}\" target=\"_blank\" rel=\"noopener\">"
                    "CC BY-NC-SA 4.0</a>. L'ebook è gratuito e si scarica da "
                    "Zenodo, con DOI citabile. Il cartaceo ha un prezzo perché "
                    "è stampato su richiesta: quel che costa è la carta, non "
                    "il testo."),
        "ai": ("Il testo è stato scritto dall'autore; strumenti di "
               "intelligenza artificiale sono stati utilizzati come supporto "
               "editoriale (rifinitura linguistica e coerenza del testo)."),
    },
    "en": {
        "registry": "series-en.json",
        "out": "indice-errancies.html",
        "occhiello": "Series",
        "strip": "",
        "amazon": "https://www.amazon.com/dp/",
        "prezzo": "price_paperback_usd",
        "money": dollaro,
        "mesi": MESI_EN,
        "conta": "{n} volumes · {p} pages · updated {d}",
        "testo": "Text",
        "tema": {"auto": "Theme: automatic", "dark": "Theme: dark",
                 "light": "Theme: light"},
        "ebook": "Ebook", "gratis": "free", "carta": "Paperback",
        "aria": ("Small text", "Medium text", "Large text"),
        "origine": "Rewritten from {t} (Erranze, vol. {n})",
        "programma": "In preparation",
        "licenza": ("All volumes are published under "
                    "<a href=\"{cc}\" target=\"_blank\" rel=\"noopener\">"
                    "CC BY-NC-SA 4.0</a>. The ebook is free and can be "
                    "downloaded from Zenodo, with a citable DOI. The paperback "
                    "is priced because it is printed on demand: what costs is "
                    "the paper, not the text."),
        "ai": ("The Italian original was written by the author, who rewrote "
               "rather than translated it for this English edition, working "
               "with artificial intelligence tools throughout."),
    },
}
CC = "https://creativecommons.org/licenses/by-nc-sa/4.0/deed.it"

# Esportazione di 'Collana Erranze - Stato pubblicazioni.numbers'. Il foglio e'
# una vista di lavoro, non una fonte: ASIN, pagine e prezzi comandano dal
# registro. --verifica serve a scoprire quando le due copie divergono, come e'
# successo col prezzo del Golem inglese e con la maiuscola di 'non Esiste'.
CSV_STATO = BASE.parent / "Collana Erranze - Stato pubblicazioni.csv"

# Il blu della collana, lo stesso che in copertina fa da fondo. In chiaro serve
# una variante piu' scura per il testo interattivo: #47698A su carta sta a
# 5,5:1, sotto la soglia che ci siamo dati per quello che va letto davvero.
CSS = """
:root{
  --ground:#FAF9F7; --raise:#EFEDE8; --ink:#1C1E22; --ink-dim:#33393F;
  --soft:#4A5A6E; --blue:#47698A; --accent:#3A5877; --rule:#E2E0DC;
  --fs:1.125rem; --lh:1.72;
  --serif:"Literata",Charter,"Iowan Old Style",Georgia,serif;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#191A1C; --raise:#212225; --ink:#E3E1DE; --ink-dim:#C6C3BF;
    --soft:#9BA3AD; --blue:#8FB0D4; --accent:#9DBCDD; --rule:#2C2D31;
  }
}
:root[data-theme="dark"]{
  --ground:#191A1C; --raise:#212225; --ink:#E3E1DE; --ink-dim:#C6C3BF;
  --soft:#9BA3AD; --blue:#8FB0D4; --accent:#9DBCDD; --rule:#2C2D31;
}
:root[data-mode="light"]{
  --ground:#FAF9F7; --raise:#EFEDE8; --ink:#1C1E22; --ink-dim:#33393F;
  --soft:#4A5A6E; --blue:#47698A; --accent:#3A5877; --rule:#E2E0DC;
}
:root[data-mode="dark"]{
  --ground:#191A1C; --raise:#212225; --ink:#E3E1DE; --ink-dim:#C6C3BF;
  --soft:#9BA3AD; --blue:#8FB0D4; --accent:#9DBCDD; --rule:#2C2D31;
}
:root[data-size="m"]{--fs:1.28rem}
:root[data-size="l"]{--fs:1.45rem;--lh:1.66}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--serif);
  font-size:var(--fs);line-height:var(--lh);margin:0;
  -webkit-text-size-adjust:100%;text-rendering:optimizeLegibility}
.wrap{max-width:43em;margin:0 auto;padding:2rem clamp(1.5rem,4vw,3rem) 6rem;
  display:flex;flex-direction:column;gap:1.5em}
.bar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;
  align-items:center;justify-content:space-between;gap:.5rem;padding:.45rem 0;
  background:var(--ground);border-bottom:1px solid var(--rule)}
.grp{display:flex;align-items:center;gap:.3rem}
.grplab{font-family:var(--mono);font-size:.8rem;color:var(--soft);
  margin-right:.3rem}
.bar button{font-family:var(--mono);line-height:1;color:var(--soft);
  background:transparent;border:1px solid var(--rule);border-radius:3px;
  cursor:pointer;min-height:44px;min-width:44px;padding:0 .7rem}
.bar button[data-s="s"]{font-size:.85rem}
.bar button[data-s="m"]{font-size:1rem}
.bar button[data-s="l"]{font-size:1.2rem}
.bar .tema{font-size:.8rem;padding:0 .9rem}
.bar button[aria-pressed="true"]{color:var(--ground);background:var(--soft);
  border-color:var(--soft)}
.bar button:focus-visible,a:focus-visible{outline:2px solid var(--accent);
  outline-offset:2px}
.occhiello{font-family:var(--mono);font-size:.75em;letter-spacing:.16em;
  text-transform:uppercase;color:var(--blue);font-weight:500}
h1{font-family:var(--sans);font-weight:600;font-size:2.3em;line-height:1.1;
  letter-spacing:-.02em;margin:.05em 0 0;color:var(--blue)}
.autore{font-family:var(--sans);font-size:.9em;color:var(--soft)}
.manifesto{font-size:1.02em;line-height:1.68;color:var(--ink-dim);
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  padding:1.2em 0}
.conta{font-family:var(--mono);font-size:.78em;color:var(--soft)}
.vol{display:grid;grid-template-columns:3.2em 1fr;gap:0 1.2em;
  padding-top:1.6em;border-top:1px solid var(--rule)}
.n{font-family:var(--mono);font-size:1.5em;font-weight:500;color:var(--blue);
  line-height:1.1;font-variant-numeric:tabular-nums}
.testa{display:flex;flex-direction:column;gap:.15em}
.vol h2{font-family:var(--sans);font-weight:600;font-size:1.24em;
  line-height:1.24;letter-spacing:-.008em;margin:0;text-wrap:balance}
.sottotitolo{font-style:italic;font-size:1em;color:var(--ink-dim);
  line-height:1.4}
.corpo{grid-column:2;display:flex;flex-direction:column;gap:.85em;
  margin-top:.75em}
.quarta{margin:0;line-height:1.66}
.origine{margin:0;font-family:var(--sans);font-size:.8em;color:var(--soft);
  letter-spacing:.01em}
.programma{padding-top:1.6em;border-top:1px solid var(--rule)}
.programma h2{font-family:var(--sans);font-weight:600;font-size:1.1em;
  margin:0 0 .6em;color:var(--blue)}
.programma ul{margin:0;padding-left:1.15em;display:flex;
  flex-direction:column;gap:.55em}
.programma li{line-height:1.5}
.programma li::marker{color:var(--soft)}
.programma .da{display:block;font-family:var(--sans);font-size:.78em;
  color:var(--soft)}
.meta{font-family:var(--mono);font-size:.76em;color:var(--soft);
  font-variant-numeric:tabular-nums}
.azioni{display:flex;flex-wrap:wrap;gap:.5em .6em}
.azioni a{font-family:var(--sans);font-size:.84em;line-height:1.2;
  text-decoration:none;color:var(--accent);border:1px solid var(--rule);
  border-radius:3px;padding:.6em .85em;display:flex;align-items:center;
  gap:.45em;min-height:44px}
.azioni a:hover{border-color:var(--accent);background:var(--raise)}
.azioni .prezzo{font-family:var(--mono);font-size:.92em;color:var(--soft)}
footer{border-top:1px solid var(--rule);padding-top:1.2em;
  font-family:var(--sans);font-size:.83em;line-height:1.6;color:var(--ink-dim);
  display:flex;flex-direction:column;gap:.6em}
footer a{color:var(--accent)}
@media (max-width:520px){
  .wrap{padding:1.25rem 1.15rem 4rem}
  h1{font-size:1.85em}
  .vol{grid-template-columns:1fr;gap:0}
  .corpo{grid-column:1}
  .n{font-size:1.15em;margin-bottom:.2em}
}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

JS = """
(function(){
  var root=document.documentElement,
      btns=[].slice.call(document.querySelectorAll('.bar button[data-s]'));
  function apply(v){
    root.setAttribute('data-size',v);
    btns.forEach(function(b){
      b.setAttribute('aria-pressed',String(b.dataset.s===v));});
  }
  var saved='s';
  try{saved=localStorage.getItem('erranze-size')||'s';}catch(e){}
  apply(saved);
  btns.forEach(function(b){
    b.addEventListener('click',function(){
      apply(b.dataset.s);
      try{localStorage.setItem('erranze-size',b.dataset.s);}catch(e){}
    });
  });
  var t=document.getElementById('tema'),modes=['auto','dark','light'],
      lab=ETICHETTE,mi=0;
  function mode(m){
    if(m==='auto'){root.removeAttribute('data-mode');}
    else{root.setAttribute('data-mode',m);}
    t.textContent=lab[m];
  }
  try{mi=Math.max(0,modes.indexOf(localStorage.getItem('erranze-mode')||'auto'));}
  catch(e){}
  mode(modes[mi]);
  t.addEventListener('click',function(){
    mi=(mi+1)%modes.length; mode(modes[mi]);
    try{localStorage.setItem('erranze-mode',modes[mi]);}catch(e){}
  });
})();
"""


def spezza(titolo):
    """Il registro tiene 'Titolo — Sottotitolo' in un campo solo."""
    parti = titolo.split(" — ", 1)
    return (parti[0], parti[1] if len(parti) > 1 else "")


def volume(b, cfg):
    titolo, sottotitolo = spezza(b["title"])
    e = html.escape
    z = b.get("zenodo", {})
    doi = z.get("concept_doi") or z.get("doi")
    azioni = []
    if doi:
        azioni.append(
            f'<a href="https://doi.org/{e(doi)}" target="_blank" rel="noopener">'
            f'{cfg["ebook"]} <span class="prezzo">{cfg["gratis"]}</span></a>')
    prezzo = b.get(cfg["prezzo"])
    if b.get("asin") and prezzo is not None:
        azioni.append(
            f'<a href="{cfg["amazon"]}{e(b["asin"])}" target="_blank" '
            f'rel="noopener">{cfg["carta"]} '
            f'<span class="prezzo">{e(cfg["money"](prezzo))}</span></a>')
    meta = []
    if b.get("pages"):
        pag = "pagine" if cfg["mesi"] is MESI else "pages"
        meta.append(f'{b["pages"]} {pag}')
    if doi:
        meta.append(f"DOI {e(doi)}")
    sub = (f'<span class="sottotitolo">{e(sottotitolo)}</span>'
           if sottotitolo else "")
    # Nella serie inglese ogni volume dichiara da quale italiano nasce: e' il
    # dato che spiega che cosa sia Errancies, e sta gia' in 'original'.
    orig = ""
    if cfg["origine"] and b.get("original"):
        o = b["original"]
        orig = ('<p class="origine">' +
                e(cfg["origine"].format(t=spezza(o["title"])[0], n=o["n"])) +
                "</p>")
    return f"""<section class="vol">
  <div class="n">{b['n']:02d}</div>
  <div class="testa"><h2>{e(titolo)}</h2>{sub}</div>
  <div class="corpo">
    {orig}
    <p class="quarta">{e(b['blurb'])}</p>
    <p class="meta">{' · '.join(meta)}</p>
    <div class="azioni">{''.join(azioni)}</div>
  </div>
</section>"""


def in_programma(reg, cfg):
    """Solo la serie inglese tiene i titoli futuri in 'planned'."""
    voci = reg.get("planned") or []
    if not (cfg["programma"] and voci):
        return ""
    e = html.escape
    righe = []
    for v in voci:
        t = e(spezza(v["title"])[0])
        o = v.get("original", {})
        da = (" <span class=\"da\">" +
              e(cfg["origine"].format(t=spezza(o["title"])[0], n=o["n"])) +
              "</span>") if o else ""
        righe.append(f"<li>{t}{da}</li>")
    return (f'<section class="programma"><h2>{e(cfg["programma"])}</h2>'
            f'<ul>{"".join(righe)}</ul></section>')


def _norm(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _prezzo(cella):
    c = cella.replace("€", "").replace("$", "").replace(",", ".").strip()
    return float(c) if c else None


def blocchi_csv():
    """Il foglio mette di seguito le due serie, e la numerazione riparte da 1."""
    with CSV_STATO.open(encoding="utf-8") as f:
        righe = list(csv.DictReader(f, delimiter=";"))
    blocchi, corrente, prec = [], [], 0
    for r in righe:
        n = int(r["Volume"])
        if n <= prec and corrente:
            blocchi.append(corrente)
            corrente = []
        corrente.append(r)
        prec = n
    if corrente:
        blocchi.append(corrente)
    return blocchi


def verifica():
    if not CSV_STATO.exists():
        print(f"manca {CSV_STATO.name}: esportalo da Numbers "
              f"(Archivio > Esporta come > CSV)")
        return 1
    blocchi = blocchi_csv()
    trovate = 0
    for lang, blocco in zip(("it", "en"), blocchi):
        cfg = LANGS[lang]
        libri = json.loads(
            (BASE / cfg["registry"]).read_text(encoding="utf-8"))["books"]
        print(f"\n[{lang}] {len(blocco)} righe nel foglio, "
              f"{len(libri)} nel registro")
        if len(blocco) != len(libri):
            print("  ! conteggi diversi, confronto solo i volumi in comune")
            trovate += 1
        for r, b in zip(blocco, libri):
            eti = f"  vol. {b['n']:>2}"
            ct = r["Titolo"].split(" — ")[0].strip()
            rt = b["title"].split(" — ")[0].strip()
            if _norm(ct) != _norm(rt):
                print(f"{eti} titolo:  foglio «{ct}»  registro «{rt}»")
                trovate += 1
            elif ct != rt:
                print(f"{eti} titolo, sole maiuscole:  foglio «{ct}»  "
                      f"registro «{rt}»")
                trovate += 1
            if r["ASIN"].strip() != (b.get("asin") or ""):
                print(f"{eti} ASIN:    foglio {r['ASIN'].strip()}  "
                      f"registro {b.get('asin')}")
                trovate += 1
            if int(r["Pagine"]) != b.get("pages"):
                print(f"{eti} pagine:  foglio {r['Pagine']}  "
                      f"registro {b.get('pages')}")
                trovate += 1
            cp, rp = _prezzo(r["Prezzo pdf"]), b.get(cfg["prezzo"])
            if cp is not None and rp is not None and abs(cp - rp) > 0.001:
                print(f"{eti} prezzo:  foglio {cp:.2f}  registro {rp:.2f}")
                trovate += 1
    print(f"\n{trovate} differenze." if trovate
          else "\nnessuna differenza: foglio e registri concordano.")
    return 1 if trovate else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(LANGS), default="it")
    ap.add_argument("--out")
    ap.add_argument("--verifica", action="store_true",
                    help="confronta i registri col foglio, senza scrivere")
    args = ap.parse_args()
    if args.verifica:
        sys.exit(verifica())
    cfg = LANGS[args.lang]
    out = Path(args.out) if args.out else BASE / cfg["out"]

    reg = json.loads((BASE / cfg["registry"]).read_text(encoding="utf-8"))
    serie, libri = reg["series"], reg["books"]
    e = html.escape
    oggi = date.today()
    if args.lang == "it":
        data = f"{oggi.day} {cfg['mesi'][oggi.month]} {oggi.year}"
    else:
        data = f"{cfg['mesi'][oggi.month]} {oggi.day}, {oggi.year}"

    pagine = sum(b.get("pages", 0) for b in libri)
    conta = cfg["conta"].format(n=len(libri), p=migliaia_it(pagine), d=data)
    nome = serie["name"].replace(cfg["strip"], "") if cfg["strip"] \
        else serie["name"]

    doc = f"""<title>{e(serie['name'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;1,7..72,400&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>

<div class="wrap">
  <div class="bar">
    <div class="grp" role="group" aria-label="{e(cfg['testo'])}">
      <span class="grplab">{e(cfg['testo'])}</span>
      <button type="button" data-s="s" aria-label="{e(cfg['aria'][0])}">A</button>
      <button type="button" data-s="m" aria-label="{e(cfg['aria'][1])}">A</button>
      <button type="button" data-s="l" aria-label="{e(cfg['aria'][2])}">A</button>
    </div>
    <button type="button" class="tema" id="tema">{e(cfg['tema']['auto'])}</button>
  </div>

  <div>
    <div class="occhiello">{e(cfg['occhiello'])}</div>
    <h1>{e(nome)}</h1>
    <div class="autore">{e(serie['author'])}</div>
  </div>

  <p class="manifesto">{e(serie['description'])}</p>

  <p class="conta">{e(conta)}</p>

  {''.join(volume(b, cfg) for b in libri)}

  {in_programma(reg, cfg)}

  <footer>
    <div>{cfg['licenza'].format(cc=CC)}</div>
    <div>{e(cfg['ai'])}</div>
  </footer>
</div>

<script>
var ETICHETTE = {json.dumps(cfg['tema'], ensure_ascii=False)};
{JS}</script>
"""
    out.write_text(doc, encoding="utf-8")
    print(f"scritto {out}")
    print(f"  volumi: {len(libri)}  pagine: {pagine}"
          f"  in programma: {len(reg.get('planned') or [])}")
    print(f"  con ASIN: {sum(1 for b in libri if b.get('asin'))}"
          f"  con DOI: {sum(1 for b in libri if b.get('zenodo'))}")


if __name__ == "__main__":
    main()
