#!/usr/bin/env python3
"""Genera l'edizione a stampa (KDP paperback) di un volume della Collana Erranze
(it) o di Errancies (en).

Produce due PDF pronti per il caricamento su KDP:
    - interno: testo del libro, formato 6x9", margini secondo le fasce KDP
    - copertina: wrap completo (retro + dorso + fronte) con bleed 0.125"

Uso normale (nuovo volume, l'ultimo del registro):
    python3 genera-stampa.py

Un volume specifico:
    python3 genera-stampa.py --volume 3

Edizione inglese (cartelle sotto English/, copertina a fondo chiaro):
    python3 genera-stampa.py --lang en --volume 1

Rebuild completo:
    python3 genera-stampa.py --tutti

I temi delle due serie ripetono quelli di genera-copertina.py, così che la
copertina a stampa e quella dell'ebook restino lo stesso oggetto: 'it' bianco su
fondo blu, 'en' il negativo, blu sullo stesso fondo bianco. Entrambe monocrome:
il colore del volume non entra in copertina.
"""

import json
import os
import re
import shutil
import sys
import textwrap

import cairosvg
import markdown
import weasyprint
from pypdf import PdfReader, PdfWriter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)
COPERTINE_DIR = os.path.join(SCRIPT_DIR, "Copertine")

TRIM_W = 6.0
TRIM_H = 9.0
BLEED = 0.125
PAPER = "cream"
SPINE_FACTOR = {"white": 0.002252, "cream": 0.0025}
TOP_MARGIN = 0.75
BOTTOM_MARGIN = 0.75

# Quarta di copertina. KDP chiede che nessun testo stia a meno di 0.375" dai
# tagli e riserva l'angolo in basso a destra al codice a barre (2 x 1.2").
# Il 6 settembre 2026 ha respinto la copertina del vol. 21: il testo era a
# 0.275" dal taglio e la biografia finiva addirittura fuori dal foglio.
BACK_MARGIN = 0.45       # margine del testo dai tagli, con respiro sul minimo
BARCODE_RESERVE = 1.35   # fascia bassa lasciata libera per il codice a barre
BACK_TOP = 1.10          # prima riga della quarta dal bordo del file (bleed compreso)
BACK_MIN_SCALE = 0.60    # sotto questa riduzione del corpo il blurb e' da riscrivere

# (pagine massime della fascia, margine interno, margine esterno)
# Valori KDP minimi → raddoppiati per leggibilità: interno 0.75", esterno 0.50"
MARGIN_TABLE = [
    (150, 0.75, 0.50),
    (300, 0.875, 0.50),
    (500, 1.00, 0.50),
    (700, 1.00, 0.50),
    (828, 1.00, 0.50),
]

BIO_IT = (
    "Giovanni Martini, sociologo, vive in Trentino sull'Altopiano di Pine'. "
    "Lettore onnivoro con una predilezione per la narrativa speculativa, la "
    "filosofia e la scienza, coltiva da sempre la ricerca di connessioni tra "
    "discipline distanti: fisica e coscienza, Oriente e Occidente, mito e "
    "tecnologia. Preferisce le tensioni irrisolte alle sintesi facili."
)

BIO_EN = (
    "Giovanni Martini is a sociologist living in Trentino, on the Pine' plateau "
    "in northern Italy. An omnivorous reader with a preference for speculative "
    "fiction, philosophy and science, he has always looked for connections "
    "between distant disciplines: physics and consciousness, East and West, myth "
    "and technology. He prefers unresolved tensions to easy syntheses."
)

# I campi grafici (stops, ink, accent_factor, rule_factor, label) sono gli stessi
# di THEMES in genera-copertina.py e vanno tenuti allineati a quelli: se cambia
# la copertina dell'ebook deve cambiare qui, altrimenti le due edizioni dello
# stesso volume smettono di somigliarsi.
LANGS = {
    "it": {
        "registry": "serie.json",
        "root": "",                       # relativo a BASE
        "dest": os.path.join(BASE, "Progetti stampa"),
        "series": "Collana Erranze",
        "label": "COLLANA ERRANZE",
        "prefix": "",
        "html_lang": "it",
        "body_start": "## Prologo",
        "toc_title": "Sommario",
        "bio": BIO_IT,
        "stops": ("#47698A", "#577694", "#456687"),
        "ink": "#FFFFFF",
        "accent_factor": 1.0,
        "rule_factor": 0.55,
        "mono": True,                     # vedi THEMES in genera-copertina.py
        "back_label": "#D6E1EA",          # occhiello e nome dell'autore sul retro
        "back_rule": "#8AA2B8",
        "back_text": "#FFFFFF",           # quarta di copertina
        "back_bio": "#EDF2F6",
    },
    "en": {
        "registry": "series-en.json",
        "root": "English",
        "dest": os.path.join(BASE, "Progetti stampa", "English"),
        "series": "Errancies",
        "label": "ERRANCIES",
        "prefix": "en-",
        "html_lang": "en",
        "body_start": "## Prologue",
        "toc_title": "Contents",
        "bio": BIO_EN,
        # Negativo esatto della copertina italiana, vedi THEMES in
        # genera-copertina.py: i due dizionari vanno tenuti allineati.
        "stops": ("#FFFFFF", "#FFFFFF", "#FFFFFF"),
        "ink": "#47698A",
        "accent_factor": 1.0,
        "rule_factor": 0.62,
        "mono": True,
        "back_label": "#5F7D9B",          # occhiello e nome dell'autore sul retro
        "back_rule": "#AFC1D2",
        "back_text": "#47698A",           # quarta di copertina
        "back_bio": "#5A7A99",
    },
}

SPIRAL_PATH = "M 210.0,248.8 L 209.7,249.2 L 209.3,249.0 L 209.0,249.2 L 208.5,249.4 L 208.1,250.0 L 207.9,250.2 L 207.2,250.0 L 206.8,250.5 L 206.3,250.6 L 205.9,250.2 L 205.3,250.4 L 205.0,250.4 L 204.6,250.5 L 204.2,250.2 L 203.7,249.7 L 202.4,249.6 L 201.6,249.8 L 201.3,249.4 L 200.9,249.0 L 200.3,248.9 L 199.8,249.0 L 199.4,248.9 L 199.0,248.8 L 198.2,248.3 L 197.5,248.2 L 196.9,248.5 L 196.2,247.7 L 195.9,247.7 L 195.6,247.4 L 195.5,246.8 L 194.5,246.1 L 194.3,245.1 L 193.9,244.6 L 193.3,244.3 L 193.1,244.3 L 192.8,243.4 L 192.3,242.4 L 192.2,241.5 L 191.8,241.0 L 191.3,240.2 L 190.5,239.1 L 190.2,238.4 L 190.4,237.7 L 190.4,236.9 L 190.6,236.3 L 190.5,235.2 L 190.7,234.5 L 191.0,233.6 L 191.5,232.6 L 191.8,231.8 L 191.6,230.6 L 191.6,230.1 L 191.9,229.4 L 191.3,228.7 L 191.7,227.6 L 191.7,226.7 L 192.5,225.5 L 192.7,225.0 L 193.0,224.0 L 193.4,222.8 L 194.0,221.7 L 194.7,220.9 L 195.9,220.2 L 196.8,219.1 L 197.2,218.5 L 198.3,217.4 L 199.1,216.9 L 200.1,216.5 L 200.7,215.7 L 201.0,215.2 L 201.7,215.2 L 202.4,214.6 L 202.8,213.9 L 203.8,213.6 L 205.2,213.1 L 205.9,212.7 L 207.1,212.4 L 207.9,212.3 L 209.0,212.1 L 210.5,211.9 L 211.7,212.2 L 212.9,211.7 L 214.0,211.9 L 215.2,211.7 L 216.7,211.4 L 217.4,211.3 L 218.6,211.1 L 220.1,211.3 L 221.0,211.5 L 222.2,211.2 L 223.6,211.4 L 224.6,211.8 L 226.0,212.0 L 227.3,212.7 L 228.3,213.2 L 229.5,214.3 L 230.2,215.0 L 231.3,215.4 L 233.1,216.0 L 234.9,216.5 L 236.0,217.1 L 236.8,217.9 L 237.7,218.8 L 238.1,220.3 L 239.1,221.6 L 239.9,222.6 L 241.7,223.3 L 242.2,224.2 L 243.2,225.5 L 244.3,226.5 L 244.6,227.6 L 245.7,229.0 L 245.8,230.2 L 246.8,232.2 L 247.5,233.5 L 247.6,234.6 L 248.1,236.1 L 248.7,237.4 L 248.7,238.6 L 248.7,240.3 L 248.3,241.7 L 248.8,243.7 L 249.0,245.5 L 249.0,246.8 L 248.9,248.8 L 249.2,250.4 L 250.0,251.9 L 249.9,253.5 L 249.5,255.7 L 249.5,256.7 L 248.8,258.4 L 248.5,259.5 L 247.2,260.5 L 246.5,262.1 L 245.9,263.4 L 244.8,264.5 L 244.1,266.2 L 243.5,268.0 L 242.5,269.9 L 241.4,271.1 L 240.2,272.3 L 238.4,273.8 L 237.4,275.0 L 236.0,276.4 L 235.2,277.7 L 233.7,278.7 L 232.3,279.5 L 230.8,280.7 L 229.9,282.0 L 228.5,282.8 L 227.0,283.5 L 225.4,284.5 L 223.4,285.9 L 221.7,286.1 L 220.1,286.6 L 218.2,287.4 L 216.4,287.4 L 214.1,288.1 L 212.5,289.1 L 211.1,288.8 L 209.2,288.5 L 207.6,288.9 L 205.1,289.6 L 203.2,289.0 L 201.2,288.8 L 199.1,288.6 L 197.4,288.0 L 195.3,288.3 L 193.0,288.0 L 191.0,287.4 L 189.1,286.9 L 186.8,286.8 L 185.0,285.9 L 182.8,284.9 L 181.3,284.0 L 179.4,282.9 L 177.7,281.9 L 176.0,280.7 L 174.4,279.7 L 172.5,278.2 L 170.5,276.6 L 168.6,275.5 L 167.0,274.4 L 166.1,272.8 L 164.1,271.0 L 162.6,268.9 L 161.2,267.2 L 159.8,265.2 L 158.4,263.9 L 157.3,261.7 L 156.2,260.0 L 155.0,258.0 L 154.4,256.1 L 154.0,253.8 L 153.6,251.4 L 152.7,249.5 L 152.4,247.2 L 151.5,245.1 L 150.9,242.4 L 150.4,240.2 L 149.7,237.9 L 149.7,235.4 L 150.0,233.2 L 150.0,230.6 L 150.4,227.8 L 150.6,225.2 L 151.0,223.0 L 151.5,221.0 L 152.1,218.5 L 152.5,216.4 L 153.4,214.5 L 154.1,212.1 L 155.0,209.7 L 156.1,206.9 L 157.5,204.9 L 159.0,203.4 L 160.2,201.1 L 161.6,199.5 L 162.6,197.5 L 163.8,194.6 L 164.9,192.3 L 167.1,190.2 L 169.0,188.1 L 171.1,186.1 L 173.5,184.3 L 175.4,182.8 L 177.5,181.8 L 179.7,180.1 L 181.8,178.6 L 184.4,177.5 L 186.7,176.7 L 189.0,175.5 L 191.6,175.0 L 194.1,173.9 L 196.3,173.3 L 198.8,172.7 L 201.0,172.3 L 203.4,171.5 L 206.6,170.7 L 209.4,170.4 L 211.9,170.6 L 215.2,169.9 L 217.6,170.2 L 220.1,170.2 L 223.0,170.7 L 225.8,171.0 L 228.5,171.8 L 231.2,172.4 L 233.9,173.1 L 236.7,173.8 L 239.3,174.9 L 242.5,175.9 L 245.4,177.2 L 248.3,178.4 L 250.9,179.9 L 253.4,181.0 L 255.9,181.9 L 258.3,183.7 L 260.9,185.5 L 263.4,187.3 L 265.3,188.9 L 267.1,190.6 L 269.4,192.7 L 271.5,195.0 L 273.7,197.7 L 275.3,200.0 L 276.8,202.0 L 278.6,205.0 L 280.1,207.5 L 281.9,209.5 L 283.2,212.4 L 284.2,215.7 L 285.6,218.5 L 286.5,221.3 L 287.2,224.0 L 288.4,227.3 L 289.2,230.1 L 290.2,233.8 L 290.6,236.6 L 290.5,239.9 L 290.3,243.0 L 290.7,245.8 L 291.1,249.4 L 290.4,252.2 L 290.0,255.1 L 289.4,257.7 L 288.7,261.5 L 287.7,264.6 L 286.5,268.0 L 285.5,271.7 L 284.6,274.6 L 283.6,277.5 L 281.9,280.6 L 280.5,283.5 L 279.1,286.3 L 277.6,289.6 L 275.5,292.8 L 273.6,295.2 L 272.4,297.8 L 270.6,300.6 L 267.8,303.0 L 265.3,305.0 L 262.4,307.3 L 260.1,309.6 L 257.5,311.5 L 254.5,313.4 L 251.5,315.3 L 248.7,316.9 L 245.8,318.4 L 242.8,320.2 L 239.9,321.9 L 236.3,323.2 L 233.3,324.6 L 229.6,325.8 L 226.7,326.8 L 223.4,327.7 L 220.1,328.7 L 216.7,329.3 L 213.1,329.6 L 210.0,329.9 L 206.4,329.9 L 203.1,329.7 L 199.8,329.4 L 195.9,329.3 L 192.4,329.0 L 189.1,328.4 L 185.7,327.6 L 182.4,327.0 L 179.0,326.1 L 175.2,325.0 L 171.9,323.8 L 168.5,322.1 L 165.1,320.5 L 161.5,318.9 L 157.7,317.4 L 154.8,315.5 L 151.5,313.3 L 148.5,310.5 L 145.6,308.6 L 142.7,306.2 L 140.0,303.8 L 137.7,301.3 L 134.9,298.5 L 132.5,296.2 L 130.1,293.0 L 127.6,289.4 L 125.6,286.0 L 123.3,282.3 L 121.1,279.4 L 119.1,275.6 L 117.6,272.3 L 116.4,269.1 L 115.1,265.3 L 113.9,261.9 L 112.7,257.9 L 112.2,254.2 L 111.3,250.5 L 111.0,246.9 L 110.4,243.3 L 110.7,239.9 L 110.7,235.6 L 111.6,231.4 L 111.5,227.3 L 112.0,223.6 L 111.9,219.8 L 112.5,215.8 L 112.8,211.8 L 113.6,208.0 L 114.4,204.4 L 115.4,200.1 L 116.6,196.8 L 118.0,193.7 L 119.8,189.6 L 121.5,186.1 L 123.2,183.2 L 125.1,179.8 L 127.9,176.2 L 130.1,172.7 L 132.8,169.7 L 135.5,166.1 L 138.4,162.8 L 140.7,159.7 L 143.5,157.0 L 147.3,154.8 L 150.5,152.0 L 154.1,149.8 L 157.5,147.4 L 161.8,145.1 L 165.3,143.0 L 169.2,140.8 L 172.9,138.7 L 176.8,137.6 L 181.0,136.1 L 184.7,134.6 L 189.1,133.3 L 193.7,131.9 L 197.7,131.6 L 201.4,131.3 L 205.1,130.7 L 209.5,130.5"


def registry_path(cfg):
    return os.path.join(SCRIPT_DIR, cfg["registry"])


def load_books(cfg):
    with open(registry_path(cfg), encoding="utf-8") as f:
        return json.load(f)


def margins_for(pages):
    for max_p, inside, outside in MARGIN_TABLE:
        if pages <= max_p:
            return inside, outside
    return MARGIN_TABLE[-1][1], MARGIN_TABLE[-1][2]


def darken(hex_color, factor=0.5):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r*factor):02X}{int(g*factor):02X}{int(b*factor):02X}"


def slugify(title):
    s = re.sub(r"[^\w\s-]", "", title)
    return re.sub(r"\s+", "-", s.strip())


def set_pdf_metadata(path, title, subject, year):
    """Sostituisce i metadati generici del renderer (titolo/autore mancanti,
    data di generazione odierna identica per tutti i volumi) con quelli
    editoriali del libro. La data viene impostata al 1° gennaio dell'anno
    di edizione, non al momento in cui il file è stato prodotto."""
    reader = PdfReader(path)
    writer = PdfWriter()
    writer.append(reader)
    writer.add_metadata({
        "/Title": title,
        "/Author": "Giovanni Martini",
        "/Subject": subject,
        "/Creator": "Collana Erranze",
        "/Producer": "Collana Erranze",
        "/CreationDate": f"D:{year}0101000000",
        "/ModDate": f"D:{year}0101000000",
    })
    with open(path, "wb") as f:
        writer.write(f)


# ---------------------------------------------------------------------------
# Sorgente .md
# ---------------------------------------------------------------------------

def parse_md(cfg, book):
    folder = os.path.join(BASE, cfg["root"], book["folder"])
    candidates = [f for f in os.listdir(folder) if f.endswith(".md")]
    if len(candidates) != 1:
        sys.exit(f"Errore: trovati {len(candidates)} file .md in '{folder}', attesi 1.")
    md_path = os.path.join(folder, candidates[0])
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    subtitle_m = re.search(r"^\*([^*\n]+)\*\s*$", content, re.MULTILINE)
    year_m = re.search(r"©\s*(\d{4})", content)
    if not title_m or not subtitle_m or not year_m:
        sys.exit(f"Errore: titolo, sottotitolo o anno di copyright non trovati in {md_path}")

    if cfg["body_start"] not in content:
        sys.exit(f"Errore: '{cfg['body_start']}' non trovato in {md_path}")
    idx = content.index(cfg["body_start"])
    body_md = content[idx:]

    return {
        "md_path": md_path,
        "folder": folder,
        "title": title_m.group(1).strip(),
        "subtitle": subtitle_m.group(1).strip(),
        "year": year_m.group(1),
        "body_md": body_md,
    }


def extract_blurb(cfg, body_md, limit=650):
    pattern = rf"^{re.escape(cfg['body_start'])}[^\n]*\n+(.+?)(?=\n## )"
    m = re.search(pattern, body_md, re.DOTALL)
    raw = m.group(1) if m else body_md[:limit]
    raw = re.sub(r"^###.*$", "", raw, flags=re.MULTILINE)  # rimuove i titoli ###

    paragraphs = []
    for p in raw.split("\n\n"):
        p = re.sub(r"\[(.+?)\]\([^)]+\)", r"\1", p)  # link -> testo
        p = re.sub(r"[*_#]", "", p).strip()           # markup residuo
        if not p:
            continue
        if p[-1] not in ".!?…\"”»":
            p += "."
        paragraphs.append(p)

    text = re.sub(r"\s+", " ", " ".join(paragraphs)).strip()
    if len(text) > limit:
        cut = text.rfind(". ", 0, limit)
        text = text[: cut + 1] if cut > 200 else text[:limit].rstrip() + "…"
    return text


# ---------------------------------------------------------------------------
# Interno (PDF testo)
# ---------------------------------------------------------------------------

def build_body_html(body_md):
    # nl2br: nei Testi di riferimento e nei versi citati le righe sono separate
    # da un solo a capo. Senza questa estensione markdown le fonde in un unico
    # paragrafo e la bibliografia esce come un blocco continuo.
    md = markdown.Markdown(extensions=["extra", "toc", "nl2br"], extension_configs={"toc": {"permalink": False}})
    html_body = md.convert(body_md)
    html_body = re.sub(r'<h2 id="([^"]+)">', r'<h2 id="\1" class="chapter-open">', html_body)
    # Immagine + paragrafo in corsivo che la segue = figura con didascalia.
    # Senza questo passaggio le regole CSS di img/figure/didascalia restano
    # inerti: la didascalia esce in corpo pieno e puo' spezzarsi sulla pagina
    # dopo (successo con l'edizione inglese del vol. 24, ottobre 2026).
    html_body = re.sub(
        r'<p>(<img [^>]+>)</p>\s*<p><em>(.*?)</em></p>',
        r'<figure>\1<p class="didascalia">\2</p></figure>',
        html_body, flags=re.DOTALL)

    toc_rows = []
    for tok in md.toc_tokens:
        if tok["level"] not in (2, 3):
            continue
        cls = "lvl1" if tok["level"] == 2 else "lvl2"
        toc_rows.append(
            f'<li class="{cls}"><a href="#{tok["id"]}">{tok["name"]}</a></li>'
        )
    toc_html = "<ul>" + "".join(toc_rows) + "</ul>"
    return html_body, toc_html


def render_css(cfg, inside, outside, title):
    header = title.upper()
    return f"""
@page {{
  size: {TRIM_W}in {TRIM_H}in;
  margin-top: {TOP_MARGIN}in;
  margin-bottom: {BOTTOM_MARGIN}in;
  @top-center {{ content: "{header} · Giovanni Martini"; font-family: Georgia; font-size: 8pt;
                 letter-spacing: 0.5px; color: #666; }}
  @bottom-center {{ content: counter(page); font-family: Georgia; font-size: 9pt; color: #333; }}
}}
@page :right {{ margin-left: {inside}in; margin-right: {outside}in; }}
@page :left  {{ margin-left: {outside}in; margin-right: {inside}in; }}
/* le pagine bianche inserite prima dei capitoli che aprono a destra devono
   essere mute: niente testatina, niente numero di pagina */
@page :blank {{ @top-center {{ content: none; }} @bottom-center {{ content: none; }} }}
@page front  {{ margin: 1in; @top-center {{ content: none; }} @bottom-center {{ content: none; }} }}
@page toc    {{ @top-center {{ content: none; }} }}

html {{ lang: {cfg["html_lang"]}; }}
body {{ font-family: Georgia, "Times New Roman", serif; font-size: 10.5pt; line-height: 1.45;
        text-align: justify; hyphens: auto; -webkit-hyphens: auto; color: #111; }}
p {{ margin: 0 0 0.8em 0; orphans: 3; widows: 3; }}
h2 {{ font-size: 18pt; font-weight: bold; margin: 0 0 0.8em 0; text-align: left; }}
h2.chapter-open {{ page-break-before: right; margin-top: 1.6in; }}
h3 {{ font-size: 12.5pt; font-style: italic; margin: 1.8em 0 0.6em 0; }}
blockquote {{ margin: 1em 1.8em; font-style: italic; color: #333; }}
/* immagini nel corpo: introdotte con il vol. 24, che riproduce un documento.
   L'immagine non supera mai la gabbia di testo e non si spezza fra due pagine;
   la didascalia e' il paragrafo in corsivo che la segue. */
img {{ display: block; max-width: 100%; max-height: 5.8in; height: auto; margin: 1.4em auto 0.5em auto; }}
p.didascalia {{ font-size: 8.5pt; font-style: italic; text-align: center; color: #444; margin: 0 0 1.6em 0; }}
figure {{ break-inside: avoid; margin: 0; }}
a {{ color: inherit; text-decoration: none; }}

.front {{ page: front; }}
.titlepage {{ text-align: center; padding-top: 2.2in; }}
.titlepage h1 {{ font-size: 27pt; margin-bottom: 0.4em; }}
.titlepage .subtitle {{ font-style: italic; font-size: 13pt; margin-bottom: 2.5in; }}
.titlepage .collana {{ font-size: 10pt; color: #555; }}
.copyrightpage {{ font-size: 9pt; line-height: 1.7; padding-top: 3.2in;
                  text-align: left; hyphens: none; -webkit-hyphens: none; }}

.tocpage {{ page: toc; }}
.tocpage h2 {{ margin-bottom: 1em; }}
.tocpage ul {{ list-style: none; margin: 0; padding: 0; }}
.tocpage li {{ margin: 0.5em 0; }}
.tocpage li.lvl1 {{ font-weight: bold; }}
.tocpage li.lvl2 {{ margin-left: 1.3em; font-size: 9.5pt; font-weight: normal; }}
.tocpage a {{ display: flex; justify-content: space-between; }}
.tocpage a::after {{ content: target-counter(attr(href), page); margin-left: 0.5em; }}
"""


def copyright_page(cfg, book, parsed):
    """Pagina dei diritti nella lingua della serie. Nell'edizione inglese porta
    anche il rimando all'originale italiano, che è l'informazione che il lettore
    anglofono non ricava da nessun'altra parte del volume a stampa."""
    year = parsed["year"]
    if cfg["html_lang"] == "en":
        original = book.get("original") or {}
        colophon = ""
        if original.get("title"):
            vol = f", vol. {original['n']}" if original.get("n") else ""
            colophon = (
                f"  <p>Originally published in Italian as <em>{original['title']}</em>"
                f" (Collana Erranze{vol}).</p>\n"
            )
        return (
            f"  <p>© {year} Giovanni Martini</p>\n"
            f"  <p>Distributed under a Creative Commons BY-NC-SA 4.0 licence<br>\n"
            f"     creativecommons.org/licenses/by-nc-sa/4.0</p>\n"
            f"  <p>Print edition — Errancies, vol. {book['n']}</p>\n"
            f"{colophon}"
            f"  <p>The Italian original was written by the author, who rewrote rather than\n"
            f"     translated it for this English edition, working with artificial\n"
            f"     intelligence tools throughout.</p>\n"
            f"  <p>First edition: {year}</p>"
        )
    return (
        f"  <p>© {year} Giovanni Martini</p>\n"
        f"  <p>Distribuito con licenza Creative Commons BY-NC-SA 4.0<br>\n"
        f"     creativecommons.org/licenses/by-nc-sa/4.0</p>\n"
        f"  <p>Edizione cartacea — Collana Erranze, vol. {book['n']}</p>\n"
        f"  <p>Il testo è stato scritto dall'autore; strumenti di intelligenza artificiale sono stati\n"
        f"     utilizzati come supporto editoriale (rifinitura linguistica e coerenza del testo).</p>\n"
        f"  <p>Prima edizione: {year}</p>"
    )


def build_interior_html(cfg, book, parsed, toc_html, body_html):
    return f"""<!doctype html>
<html lang="{cfg['html_lang']}"><head><meta charset="utf-8"></head><body>
<div class="front titlepage">
  <h1>{parsed['title']}</h1>
  <p class="subtitle">{parsed['subtitle']}</p>
  <p class="collana">{cfg['series']} · {book['n']} — Giovanni Martini</p>
</div>
<div class="front copyrightpage">
{copyright_page(cfg, book, parsed)}
</div>
<div class="front tocpage">
  <h2>{cfg['toc_title']}</h2>
  {toc_html}
</div>
{body_html}
</body></html>"""


def build_interior_pdf(cfg, book, parsed):
    body_html, toc_html = build_body_html(parsed["body_md"])

    inside, outside = margins_for(150)  # ipotesi iniziale, fascia più piccola
    for attempt in range(2):
        css = render_css(cfg, inside, outside, parsed["title"])
        html_doc = build_interior_html(cfg, book, parsed, toc_html, body_html)
        document = weasyprint.HTML(string=html_doc, base_url=parsed["folder"]).render(
            stylesheets=[weasyprint.CSS(string=css)]
        )
        page_count = len(document.pages)
        new_inside, new_outside = margins_for(page_count)
        if (new_inside, new_outside) == (inside, outside):
            break
        inside, outside = new_inside, new_outside

    out_path = os.path.join(parsed["folder"], book["file"] + " - Interno.pdf")
    document.write_pdf(out_path)
    return out_path, page_count


# ---------------------------------------------------------------------------
# Copertina (PDF wrap: retro + dorso + fronte)
# ---------------------------------------------------------------------------

def split_title(title):
    words = title.upper().split()
    if len(words) == 1 or len(" ".join(words)) <= 9:
        return [" ".join(words)]
    best = None
    for i in range(1, len(words)):
        line1, line2 = " ".join(words[:i]), " ".join(words[i:])
        diff = abs(len(line1) - len(line2))
        if best is None or diff < best[0]:
            best = (diff, line1, line2)
    return [best[1], best[2]]


def front_panel_svg(cfg, title_lines, subtitle, color):
    """Riusa esattamente la grafica della copertina ebook (coordinate 0-400 x 0-600)."""
    if cfg.get("mono"):
        color = cfg["ink"]
    accent = darken(color, cfg["accent_factor"])
    line_color = darken(color, cfg["rule_factor"])
    ink = cfg["ink"]
    size = 44 if max(len(l) for l in title_lines) <= 9 else (38 if max(len(l) for l in title_lines) <= 10 else 34)
    first_y = size + 406
    gap = size + 5
    if len(title_lines) == 1:
        last_y = first_y
        title_svg = f'<text x="52" y="{first_y}" font-family="Georgia, serif" font-size="{size}" fill="{ink}">{title_lines[0]}</text>'
    else:
        last_y = first_y + gap
        title_svg = (
            f'<text x="52" y="{first_y}" font-family="Georgia, serif" font-size="{size}" fill="{ink}">{title_lines[0]}</text>'
            f'<text x="52" y="{last_y}" font-family="Georgia, serif" font-size="{size}" fill="{ink}">{title_lines[1]}</text>'
        )
    line_y = last_y + 18
    subtitle_y = line_y + 20
    sub_size = 11 if len(subtitle) <= 40 else (10 if len(subtitle) <= 50 else 9)

    return f"""
<rect width="400" height="600" fill="url(#grad)"/>
<text x="200" y="40" text-anchor="middle" font-family="Georgia, serif" font-size="9" letter-spacing="5" fill="{accent}">{cfg["label"]}</text>
<line x1="52" y1="52" x2="348" y2="52" stroke="{line_color}" stroke-width="0.5"/>
<path d="{SPIRAL_PATH}" fill="none" stroke="{accent}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="52" y1="396" x2="348" y2="396" stroke="{line_color}" stroke-width="0.5"/>
{title_svg}
<line x1="52" y1="{line_y}" x2="240" y2="{line_y}" stroke="{accent}" stroke-width="1.0"/>
<g transform="translate(52,{subtitle_y}) skewX(-11)">
  <text x="0" y="0" font-family="Georgia, serif" font-size="{sub_size}" fill="{accent}">{subtitle}</text>
</g>
<line x1="52" y1="546" x2="348" y2="546" stroke="{line_color}" stroke-width="0.5"/>
<text x="200" y="565" text-anchor="middle" font-family="Georgia, serif" font-size="12" letter-spacing="2" fill="{ink}">Giovanni Martini</text>
"""


def sanitize_for_svg(text):
    """cairosvg non ha fallback affidabile per script non latini (es. ebraico)."""
    text = re.sub(r"\([^()]*[֐-׿][^()]*\)", "", text)
    text = re.sub(r"[֐-׿]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def wrap_lines(text, width_in, font_size_pt):
    chars_per_line = max(10, int(width_in * 72 / (font_size_pt * 0.52)))
    return textwrap.wrap(text, width=chars_per_line)


def back_fits(blurb, bio, width_in, top, limite, scale):
    """Righe e ingombro della quarta a una data scala del corpo.

    Restituisce (righe del blurb, righe della bio, corpo del blurb, passo del
    blurb, corpo della bio, passo della bio, fondo). Il fondo e' la quota a cui
    scende l'ultima riga, discendenti compresi: e' quella che deve stare sopra
    `limite`, non la baseline."""
    blurb_pt, blurb_step = 13 * scale, 21 * scale
    # la biografia e' testo di servizio e ha lunghezza quasi fissa: si rimpicciolisce
    # con il resto, ma non sotto gli 8.5pt, sotto i quali smette di leggersi
    bio_pt, bio_step = max(8.5, 9.5 * scale), max(13.5, 15 * scale)
    righe_blurb = wrap_lines(blurb, width_in, blurb_pt)
    righe_bio = wrap_lines(bio, width_in, bio_pt)
    fondo = (top + 14 + 50
             + blurb_step * len(righe_blurb) + 40 + 28 + 22
             + bio_step * (len(righe_bio) - 1)
             + bio_pt * 0.25 / 72 * 100)
    return righe_blurb, righe_bio, blurb_pt, blurb_step, bio_pt, bio_step, fondo


def back_panel_svg(cfg, blurb, x0, width_units, units_per_in, height_units, numero):
    """Quarta di copertina, dentro l'area sicura di KDP.

    Il testo sta a BACK_MARGIN dai due tagli e finisce sopra la fascia del
    codice a barre. Quando il blurb e' lungo il corpo si riduce quanto basta a
    farlo rientrare, invece di proseguire oltre il bordo: prima di questo
    controllo la biografia del vol. 21 usciva dal foglio e nessuno se ne era
    accorto, perche' un PDF di copertina si guarda al centro, non ai margini."""
    bleed_u = BLEED * units_per_in
    margin_u = BACK_MARGIN * units_per_in
    left = x0 + bleed_u + margin_u
    right = x0 + width_units - margin_u
    width_in = (right - left) / units_per_in
    top = BACK_TOP * units_per_in
    limite = height_units - bleed_u - BARCODE_RESERVE * units_per_in

    scale = 1.0
    while True:
        misure = back_fits(blurb, cfg["bio"], width_in, top, limite, scale)
        if misure[6] <= limite or scale <= BACK_MIN_SCALE:
            break
        scale = round(scale - 0.02, 2)
    righe_blurb, righe_bio, blurb_pt, blurb_step, bio_pt, bio_step, fondo = misure
    if fondo > limite:
        # ValueError e non SystemExit: il rebuild --tutti deve saltare il volume
        # difettoso e proseguire, come fa con ogni altro errore di generazione
        raise ValueError(
            f"vol. {numero}: la quarta non ci sta nemmeno a corpo {blurb_pt:.1f}pt "
            f"(sfora di {(fondo - limite) / units_per_in:.2f}in). Accorciare il blurb "
            f"di circa {int((fondo - limite) / blurb_step) * int(width_in * 72 / (blurb_pt * 0.52))} caratteri."
        )

    lines = []
    y = top
    lines.append(f'<text x="{left}" y="{y}" font-family="Georgia, serif" font-size="11" letter-spacing="4" fill="{cfg["back_label"]}">{cfg["label"]}</text>')
    y += 14
    lines.append(f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="{cfg["back_rule"]}" stroke-width="0.5"/>')
    y += 50
    for ln in righe_blurb:
        lines.append(f'<text x="{left}" y="{y:.1f}" font-family="Georgia, serif" font-size="{blurb_pt:.2f}" fill="{cfg["back_text"]}">{ln}</text>')
        y += blurb_step
    y += 40
    lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{cfg["back_rule"]}" stroke-width="0.5"/>')
    y += 28
    lines.append(f'<text x="{left}" y="{y:.1f}" font-family="Georgia, serif" font-size="9" letter-spacing="2" fill="{cfg["back_label"]}">GIOVANNI MARTINI</text>')
    y += 22
    for ln in righe_bio:
        lines.append(f'<text x="{left}" y="{y:.1f}" font-family="Georgia, serif" font-size="{bio_pt:.2f}" fill="{cfg["back_bio"]}">{ln}</text>')
        y += bio_step
    return "\n".join(lines), scale


def spine_svg(cfg, title, x0, width_units, height_units, color):
    if width_units < 22:  # dorso troppo stretto per il testo leggibile
        return ""
    cx, cy = x0 + width_units / 2, height_units / 2
    label = f"{title.upper()}  ·  GIOVANNI MARTINI"
    # dominant-baseline="central" centra i glifi sull'asse del dorso (non sulla baseline),
    # garantendo clearance simmetrica su entrambi i lati (requisito KDP: ≥ 0.0625" = 6.25 u).
    # Formula: size ≤ spine_width - 2×6.25 per margine di sicurezza esplicito.
    size = min(11, max(6, width_units - 12.5))
    return (
        f'<g transform="translate({cx},{cy}) rotate(-90)">'
        f'<text x="0" y="0" text-anchor="middle" dominant-baseline="central" '
        f'font-family="Georgia, serif" '
        f'font-size="{size}" letter-spacing="1.5" fill="{cfg["ink"]}">{label}</text></g>'
    )


def build_cover_svg(cfg, book, parsed, page_count, blurb, color):
    paper = PAPER
    spine_in = round(max(page_count, 24) * SPINE_FACTOR[paper], 3)
    units_per_in = 100
    total_w_in = TRIM_W * 2 + spine_in + BLEED * 2
    total_h_in = TRIM_H + BLEED * 2
    W, H = total_w_in * units_per_in, total_h_in * units_per_in

    bleed_u = BLEED * units_per_in
    trim_w_u = TRIM_W * units_per_in
    spine_u = spine_in * units_per_in

    back_x0 = 0
    spine_x0 = bleed_u + trim_w_u
    front_x0 = spine_x0 + spine_u

    title_lines = split_title(parsed["title"])
    front_inner = front_panel_svg(cfg, title_lines, parsed["subtitle"], color)
    back_inner, back_scale = back_panel_svg(cfg, sanitize_for_svg(blurb), back_x0,
                                            bleed_u + trim_w_u, units_per_in, H, book["n"])
    spine_inner = spine_svg(cfg, parsed["title"], spine_x0, spine_u, H, color)

    s0, s1, s2 = cfg["stops"]
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{total_w_in}in" height="{total_h_in}in" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="{s0}"/>
      <stop offset="65%"  stop-color="{s1}"/>
      <stop offset="100%" stop-color="{s2}"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#grad)"/>
  {back_inner}
  {spine_inner}
  <g transform="translate({front_x0},{bleed_u}) scale(1.5)">
    {front_inner}
  </g>
</svg>"""
    return svg, spine_in, back_scale


def build_cover_pdf(cfg, book, parsed, page_count, blurb, color):
    svg, spine_in, back_scale = build_cover_svg(cfg, book, parsed, page_count, blurb, color)
    slug = slugify(parsed["title"])
    os.makedirs(COPERTINE_DIR, exist_ok=True)
    svg_path = os.path.join(COPERTINE_DIR, f"copertina-stampa-{cfg['prefix']}{slug}.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    pdf_dir = os.path.join(parsed["folder"], "Bozze", "Copertina")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, "copertina-stampa.pdf")
    cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)
    return pdf_path, spine_in, back_scale


# ---------------------------------------------------------------------------
# Orchestrazione
# ---------------------------------------------------------------------------

def save_blurb(cfg, registry, book, blurb):
    for b in registry["books"]:
        if b["n"] == book["n"]:
            b["blurb"] = blurb
    with open(registry_path(cfg), "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
        f.write("\n")


def process(cfg, book, registry):
    print(f"Vol. {book['n']} — {book['title']}")
    parsed = parse_md(cfg, book)

    interior_path, page_count = build_interior_pdf(cfg, book, parsed)
    print(f"  ✓ interno: {page_count} pagine")

    blurb = book.get("blurb")
    if not blurb:
        blurb = extract_blurb(cfg, parsed["body_md"])
        save_blurb(cfg, registry, book, blurb)
        print(f"  ✓ quarta di copertina abbozzata dal Prologo (rivedere in {cfg['registry']})")

    color = book.get("color", "#7878C8")
    cover_path, spine_in, back_scale = build_cover_pdf(cfg, book, parsed, page_count, blurb, color)
    ridotto = "" if back_scale == 1.0 else f", quarta a corpo {13 * back_scale:.1f}pt (blurb lungo)"
    print(f"  ✓ copertina: dorso {spine_in:.3f}in{ridotto}")

    full_title = f"{parsed['title']} — {parsed['subtitle']}"
    set_pdf_metadata(interior_path, full_title, parsed["subtitle"], parsed["year"])
    set_pdf_metadata(cover_path, full_title, parsed["subtitle"], parsed["year"])
    print("  ✓ metadati PDF (titolo, autore, data edizione)")

    dest = cfg["dest"]
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(interior_path, os.path.join(dest, book["file"] + " - Interno.pdf"))
    shutil.copy2(cover_path, os.path.join(dest, book["file"] + " - Copertina.pdf"))
    print(f"  ✓ copiati in {os.path.relpath(dest, BASE)}/")
    return True


def main():
    lang = "it"
    if "--lang" in sys.argv:
        idx = sys.argv.index("--lang")
        lang = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if lang not in LANGS:
            print(f"Errore: --lang accetta {' o '.join(sorted(LANGS))}", file=sys.stderr)
            sys.exit(1)
    cfg = LANGS[lang]

    tutti = "--tutti" in sys.argv
    volume = None
    if "--volume" in sys.argv:
        idx = sys.argv.index("--volume")
        try:
            volume = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("Errore: --volume richiede un numero (es. --volume 4)", file=sys.stderr)
            sys.exit(1)

    registry = load_books(cfg)
    books = registry["books"]
    if not books:
        print(f"Errore: nessun volume in {cfg['registry']}", file=sys.stderr)
        sys.exit(1)

    if tutti:
        print(f"{cfg['series']} — stampa, rebuild completo ({len(books)} volumi)\n")
        targets = books
    elif volume is not None:
        targets = [b for b in books if b["n"] == volume]
        if not targets:
            print(f"Errore: volume {volume} non trovato in {cfg['registry']}", file=sys.stderr)
            sys.exit(1)
        print(f"{cfg['series']} — stampa, volume {volume}\n")
    else:
        targets = [books[-1]]
        print(f"{cfg['series']} — stampa, nuovo volume\n")

    errors = []
    for book in targets:
        try:
            process(cfg, book, registry)
        except Exception as e:
            print(f"  ✗ Errore: {e}", file=sys.stderr)
            errors.append(book["n"])
        print()

    if errors:
        print(f"Errori nei volumi: {errors}")
        sys.exit(1)
    print("Fatto.")


if __name__ == "__main__":
    main()
