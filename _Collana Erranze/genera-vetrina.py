#!/usr/bin/env python3
"""Genera la pagina 'link in bio' del profilo Instagram dal registro.

Uso:
    python3 genera-vetrina.py            # -> ../Instagram/Vetrina/index.html
    python3 genera-vetrina.py --out <file>

E' la pagina pubblicata su https://erranze.netlify.app, l'unico link
cliccabile del profilo Instagram: l'elenco dei volumi, ognuno con il link al
cartaceo su Amazon.it. Non e' l'indice di genera-indice.py, che ha quarte,
pagine ed ebook: questa si scorre sul telefono in pochi secondi.

Entrano solo i volumi con l'ASIN, cioe' con il cartaceo in vendita: prima non
c'e' una pagina Amazon a cui puntare. Il titolo compare completo, con il
sottotitolo, come nel registro. Sotto va il campo 'instagram_line', una riga
che dice di che cosa parla il libro, solo dove aggiunge qualcosa al
sottotitolo: dove lo ripeterebbe manca, e la voce resta di una riga.

La pagina sta da sola nella sua cartella perche' Netlify carica cartelle
intere. Lo script genera e non pubblica: per ripubblicare si trascina la
cartella 'Vetrina' nella scheda Deploys del sito, come spiega
'Instagram/Come pubblicare su Instagram.md'.

genera-indice.py lo lancia da se' a ogni esecuzione per la collana italiana:
la pagina si era fermata al vol. 15 proprio perche' andava aggiornata a mano.
"""

import argparse
import html
import json
import re
import ssl
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
REGISTRO = BASE / "serie.json"
# Instagram/ resta nel repository privato. Nel clone pubblico la cartella non
# c'e', e lo script non la crea: li' la vetrina non serve.
INSTAGRAM = BASE.parent / "Instagram"
OUT = INSTAGRAM / "Vetrina" / "index.html"
AMAZON = "https://www.amazon.it/dp/"
SITO = "https://erranze.netlify.app"

# I colori sono quelli della copertina italiana: fondo #47698A sfumato come in
# genera-copertina.py, tutto in bianco, e un solo aspetto per tutti invece delle
# varianti chiaro e scuro, come i libri e i caroselli. Il bianco sul blu sta a
# 5,7:1, meno del blu notte di prima: per questo le righe in corsivo sotto i
# titoli sono passate da 11,5 a 12,5 pixel.
CSS = """
  :root {
    --bg:      #47698A;
    --text:    #FFFFFF;
    --muted:   #FFFFFF;
    --accent:  #FFFFFF;
    --num:     #DDE6EF;
    --border:  rgba(255,255,255,0.22);
    --hover:   #FFFFFF;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: linear-gradient(#47698A, #577694 50%, #456687);
    color: var(--text);
    font-family: Georgia, 'Times New Roman', serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-bottom: 56px;
  }

  .spirale {
    display: block;
    margin: 0 auto 18px;
    width: 54px;
    height: 60px;
  }

  /* ── Header ── */
  header {
    width: 100%;
    max-width: 480px;
    padding: 44px 28px 28px;
    text-align: center;
  }

  .eyebrow {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 10px;
    letter-spacing: 0.26em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 16px;
  }

  .brand {
    font-size: clamp(28px, 8vw, 36px);
    font-weight: normal;
    letter-spacing: -0.01em;
    color: var(--text);
    line-height: 1.15;
    text-wrap: balance;
    margin-bottom: 12px;
  }

  .brand em {
    color: var(--accent);
    font-style: italic;
  }

  .tagline {
    font-size: 13px;
    color: var(--muted);
    font-style: italic;
    line-height: 1.65;
  }

  /* ── Separator ── */
  .rule {
    width: 100%;
    max-width: 480px;
    height: 1px;
    background: var(--border);
  }

  /* ── Volume list ── */
  .volumes {
    width: 100%;
    max-width: 480px;
    padding: 0 28px;
  }

  .vol {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 17px 6px;
    border-bottom: 1px solid var(--border);
    text-decoration: none;
    color: inherit;
    transition: background 0.12s;
    margin: 0 -6px;
    border-radius: 3px;
  }

  .vol:last-child {
    border-bottom: none;
  }

  .vol:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .vol-n {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 9.5px;
    letter-spacing: 0.06em;
    color: var(--num);
    min-width: 20px;
    flex-shrink: 0;
    padding-top: 3px;
    font-variant-numeric: tabular-nums;
  }

  .vol-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .vol-title {
    font-size: 14.5px;
    color: var(--text);
    line-height: 1.4;
  }

  .vol-sub {
    font-size: 12.5px;
    color: var(--muted);
    font-style: italic;
    line-height: 1.45;
  }

  .vol-cta {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 9.5px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
    white-space: nowrap;
    flex-shrink: 0;
    padding-top: 3px;
    transition: color 0.15s;
  }

  .vol:hover .vol-cta,
  .vol:focus .vol-cta {
    color: var(--hover);
  }

  /* ── Footer ── */
  footer {
    width: 100%;
    max-width: 480px;
    padding: 28px 28px 0;
    text-align: center;
  }

  .footer-note {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--num);
    line-height: 1.9;
  }
"""

# La riga viewport non si tocca: senza, il telefono impagina come uno schermo
# da computer e rimpicciolisce tutto, e da Instagram si arriva col telefono.
TESTA = """<!DOCTYPE html>
<html lang="it">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Collana Erranze &mdash; Giovanni Martini</title>
<style>"""

CORPO = """</style>

<header>
  <!-- spirale -->
  <p class="eyebrow">Giovanni Martini</p>
  <h1 class="brand">Collana <em>Erranze</em></h1>
  <p class="tagline">Saggi di storia culturale, scienza e filosofia</p>
</header>

<div class="rule"></div>

<nav class="volumes" aria-label="Volumi della collana">
"""

PIEDE = """
</nav>

<footer>
  <p class="footer-note">Collana Erranze &middot; Giovanni Martini<br>Disponibili su Amazon KDP</p>
</footer>
"""


def spirale():
    """La spirale della collana, letta da genera-copertina.py.

    Si legge il testo invece di importare lo script, che richiede cairosvg e
    PIL: cosi' il disegno resta uno solo, e se cambia sui libri cambia anche qui.
    """
    src = (BASE / "genera-copertina.py").read_text(encoding="utf-8")
    d = re.search(r'SPIRAL_PATH = "([^"]+)"', src).group(1)
    return (f'<svg class="spirale" viewBox="105 125 191 211" aria-hidden="true">'
            f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="5" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def testo(t):
    """Apostrofi tipografici: il registro li tiene dritti."""
    return html.escape(t.replace("'", "’"), quote=False)


def voce(b):
    riga = b.get("instagram_line")
    sub = (f'\n      <span class="vol-sub">{testo(riga)}</span>'
           if riga else "")
    return f"""
  <a class="vol" href="{AMAZON}{html.escape(b['asin'])}" target="_blank" rel="noopener">
    <span class="vol-n">{b['n']:02d}</span>
    <span class="vol-body">
      <span class="vol-title">{testo(b['title'])}</span>{sub}
    </span>
    <span class="vol-cta">Amazon &rarr;</span>
  </a>
"""


def online():
    """La pagina pubblicata ora, o None se il sito non risponde."""
    # Il Python di python.org non vede i certificati di macOS e rifiuta ogni
    # sito https. certifi, che arriva con requests, gli da' i suoi.
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None
    try:
        with urllib.request.urlopen(SITO + "/", timeout=15, context=ctx) as r:
            return r.read().decode("utf-8")
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.out:
        out = Path(args.out)
    elif not INSTAGRAM.is_dir():
        print(f"vetrina saltata: manca la cartella {INSTAGRAM}")
        return
    else:
        out = OUT

    libri = json.loads(REGISTRO.read_text(encoding="utf-8"))["books"]
    in_vendita = [b for b in libri if b.get("asin")]
    doc = (TESTA + CSS + CORPO.replace("<!-- spirale -->", spirale()) + "".join(voce(b) for b in in_vendita)
           + PIEDE)

    out.parent.mkdir(exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"vetrina: {out}")
    print(f"  volumi in pagina: {len(in_vendita)}")
    senza = [str(b["n"]) for b in libri if not b.get("asin")]
    if senza:
        print(f"  senza ASIN, quindi fuori: vol. {', '.join(senza)}")
    if out != OUT:
        return
    # Il confronto e' con il sito, non con il file di prima: se una volta non
    # si ripubblica, il file locale e' gia' aggiornato e sembrerebbe tutto a
    # posto, mentre online resta la versione vecchia.
    pubblicata = online()
    if pubblicata is None:
        print(f"  non riesco a leggere {SITO}: controllare a mano")
    elif pubblicata == doc:
        print("  uguale a quella online: niente da ripubblicare")
    else:
        print(f"  diversa da quella online: da ripubblicare trascinando la "
              f"cartella 'Vetrina' nella scheda Deploys di {SITO}")


if __name__ == "__main__":
    main()
