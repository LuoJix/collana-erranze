#!/usr/bin/env python3
"""Genera la pagina 'link in bio' del profilo Instagram dal registro.

Uso:
    python3 genera-vetrina.py            # -> ../Instagram/Vetrina/index.html
    python3 genera-vetrina.py --out <file>
    python3 genera-vetrina.py --pubblica  # genera e, se diversa, pubblica

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
intere. Senza opzioni lo script genera e non pubblica. Con --pubblica, dal 24
ottobre 2026, manda la cartella al sito 'erranze' attraverso il servizio web
di Netlify, con il token salvato nel Portachiavi sotto il nome
'netlify-erranze': e' lo stesso caricamento che si fa trascinando la cartella
nella scheda Deploys, e non puo' finire su un sito nuovo come Netlify Drop.
Prima di partire lo script controlla che il sito trovato risponda proprio a
erranze.netlify.app; dopo, rilegge la pagina online e la confronta con quella
appena generata. Tutto in 'Instagram/Come pubblicare su Instagram.md'.

genera-indice.py lo lancia da se' a ogni esecuzione per la collana italiana:
la pagina si era fermata al vol. 15 proprio perche' andava aggiornata a mano.
"""

import argparse
import html
import json
import re
import io
import ssl
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
REGISTRO = BASE / "serie.json"
# Instagram/ resta nel repository privato. Nel clone pubblico la cartella non
# c'e', e lo script non la crea: li' la vetrina non serve.
INSTAGRAM = BASE.parent / "Instagram"
OUT = INSTAGRAM / "Vetrina" / "index.html"
AMAZON = "https://www.amazon.it/dp/"
SITO = "https://erranze.netlify.app"
API = "https://api.netlify.com/api/v1"
# Il nome della voce nel Portachiavi di macOS, dove sta il token personale di
# Netlify. Non sta in un file perche' il workspace e' su iCloud.
PORTACHIAVI = "netlify-erranze"

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


def contesto():
    # Il Python di python.org non vede i certificati di macOS e rifiuta ogni
    # sito https. certifi, che arriva con requests, gli da' i suoi.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


def online():
    """La pagina pubblicata ora, o None se il sito non risponde."""
    # Il parametro cambia a ogni lettura e scavalca la cache di Netlify, che
    # subito dopo una pubblicazione potrebbe dare ancora la versione vecchia.
    url = f"{SITO}/?v={int(time.time())}"
    try:
        with urllib.request.urlopen(url, timeout=15, context=contesto()) as r:
            return r.read().decode("utf-8")
    except OSError:
        return None


def netlify(percorso, dati=None, tipo=None):
    """Una chiamata al servizio web di Netlify, con il token del Portachiavi."""
    token = subprocess.run(
        ["security", "find-generic-password", "-s", PORTACHIAVI, "-w"],
        capture_output=True, text=True).stdout.strip()
    if not token:
        raise SystemExit(f"  manca il token: nel Portachiavi non c'e' la voce "
                         f"'{PORTACHIAVI}'")
    req = urllib.request.Request(API + percorso, data=dati,
                                 method="POST" if dati else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    if tipo:
        req.add_header("Content-Type", tipo)
    with urllib.request.urlopen(req, timeout=60, context=contesto()) as r:
        return json.loads(r.read().decode("utf-8"))


def pubblica(cartella):
    """Carica la cartella sul sito erranze e aspetta che sia online."""
    # Il sito si cerca per nome e si controlla l'indirizzo: se un giorno il
    # token fosse di un altro account, o il sito cambiasse nome, ci si ferma
    # invece di pubblicare altrove.
    siti = [s for s in netlify("/sites?filter=all")
            if s.get("ssl_url") == SITO or s.get("url") == SITO]
    if len(siti) != 1:
        raise SystemExit(f"  nessun sito risponde a {SITO}: non pubblico")
    sito = siti[0]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(cartella.rglob("*")):
            if f.is_file() and f.name != ".DS_Store":
                z.write(f, f.relative_to(cartella).as_posix())
    deploy = netlify(f"/sites/{sito['id']}/deploys", buf.getvalue(),
                     "application/zip")
    for _ in range(30):
        if deploy.get("state") in ("ready", "error"):
            break
        time.sleep(2)
        deploy = netlify(f"/deploys/{deploy['id']}")
    return deploy.get("state")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out")
    ap.add_argument("--pubblica", action="store_true",
                    help="se la pagina e' diversa da quella online, pubblicala")
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
    elif not args.pubblica:
        print("  diversa da quella online: da ripubblicare con "
              "'python3 genera-vetrina.py --pubblica'")
    else:
        print(f"  diversa da quella online: pubblico su {SITO}")
        stato = pubblica(out.parent)
        if stato != "ready":
            print(f"  Netlify risponde '{stato}': controllare nella scheda "
                  "Deploys")
        elif online() == doc:
            print("  pubblicata: la pagina online ora e' uguale a questa")
        else:
            print("  pubblicata, ma online risulta ancora diversa: "
                  "riprovare fra un minuto")


if __name__ == "__main__":
    main()
