#!/usr/bin/env python3
"""Genera la copertina di un volume della Collana Erranze (it) o di Errancies (en).

Uso tipico (legge titolo e sottotitolo dal file .md della cartella):
    python3 genera-copertina.py --folder "<Nome cartella del volume>" --color "#9C4A3C"

Edizione inglese (cartelle sotto English/, copertina a fondo chiaro):
    python3 genera-copertina.py --lang en --folder "The Golem — Clay and Word" --color "#C4724A"

Override manuali, se il risultato automatico non convince:
    --line1 / --line2     forzano la divisione del titolo su due righe
    --font-size           forza la dimensione del titolo (44, 40 o 34)
    --subtitle-font-size  forza la dimensione del sottotitolo

Cosa fa:
    1. Legge titolo (riga "# ...") e sottotitolo (prima riga "*...*") dal .md.
    2. Genera l'SVG con l'emblema a spirale comune alle due serie, e lo
       salva in Copertine/cover-<Titolo>.svg (o cover-en-<Titolo>.svg).
    3. Converte l'SVG in cover.png (800x1200) dentro <cartella>/Bozze/Copertina/.

Le due serie condividono impaginazione e spirale, e si distinguono per il tema,
che è l'una il negativo dell'altra: 'it' bianco su fondo blu, 'en' blu su fondo
bianco, lo stesso blu in entrambi i casi. Tutte e due monocrome, quindi il
colore del volume non compare in copertina in nessuna delle due serie.

Nota tecnica: il sottotitolo in corsivo usa un'inclinazione manuale (skewX)
invece di font-style="italic". cairosvg ha un bug di spaziatura con il
corsivo sintetico della Georgia su certe coppie di lettere (es. "fi", "Ne"):
con skewX il problema non si presenta, qualunque parola venga usata.
"""

import argparse
import glob
import io
import os
import re
import sys

import cairosvg
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)  # Progetti culturali/
COPERTINE_DIR = os.path.join(SCRIPT_DIR, "Copertine")

# Temi delle due serie, l'uno il negativo dell'altro. Entrambi monocromi: il
# colore del volume ('color' nei registri) resta come dato, ma non entra in
# copertina. Nella serie italiana i pastelli sparivano sul fondo blu; nella
# inglese, accanto al titolo blu, i pastelli freddi si confondevano con esso.
THEMES = {
    "it": {
        "root": "",                    # relativo a BASE
        "label": "COLLANA ERRANZE",
        "prefix": "",
        "stops": ("#47698A", "#577694", "#456687"),
        "ink": "#FFFFFF",              # titolo e nome dell'autore
        "accent_factor": 1.0,
        "rule_factor": 0.55,           # filetti sottili
        # Copertina monocroma: spirale, occhiello e sottotitolo prendono l'ink
        # invece del colore del volume. Il colore in serie.json resta usato dalla
        # serie inglese, che ha fondo chiaro e non ha lo stesso problema.
        "mono": True,
    },
    "en": {
        "root": "English",
        "label": "ERRANCIES",
        "prefix": "en-",
        # Negativo esatto della copertina italiana: fondo bianco pieno e tutto
        # il resto nel blu che in italiano fa da fondo. Anche qui monocroma,
        # quindi il campo 'color' del registro non entra nella copertina.
        "stops": ("#FFFFFF", "#FFFFFF", "#FFFFFF"),
        "ink": "#47698A",
        "accent_factor": 1.0,
        "rule_factor": 0.62,
        "mono": True,
    },
}

SPIRAL_PATH = "M 210.0,248.8 L 209.7,249.2 L 209.3,249.0 L 209.0,249.2 L 208.5,249.4 L 208.1,250.0 L 207.9,250.2 L 207.2,250.0 L 206.8,250.5 L 206.3,250.6 L 205.9,250.2 L 205.3,250.4 L 205.0,250.4 L 204.6,250.5 L 204.2,250.2 L 203.7,249.7 L 202.4,249.6 L 201.6,249.8 L 201.3,249.4 L 200.9,249.0 L 200.3,248.9 L 199.8,249.0 L 199.4,248.9 L 199.0,248.8 L 198.2,248.3 L 197.5,248.2 L 196.9,248.5 L 196.2,247.7 L 195.9,247.7 L 195.6,247.4 L 195.5,246.8 L 194.5,246.1 L 194.3,245.1 L 193.9,244.6 L 193.3,244.3 L 193.1,244.3 L 192.8,243.4 L 192.3,242.4 L 192.2,241.5 L 191.8,241.0 L 191.3,240.2 L 190.5,239.1 L 190.2,238.4 L 190.4,237.7 L 190.4,236.9 L 190.6,236.3 L 190.5,235.2 L 190.7,234.5 L 191.0,233.6 L 191.5,232.6 L 191.8,231.8 L 191.6,230.6 L 191.6,230.1 L 191.9,229.4 L 191.3,228.7 L 191.7,227.6 L 191.7,226.7 L 192.5,225.5 L 192.7,225.0 L 193.0,224.0 L 193.4,222.8 L 194.0,221.7 L 194.7,220.9 L 195.9,220.2 L 196.8,219.1 L 197.2,218.5 L 198.3,217.4 L 199.1,216.9 L 200.1,216.5 L 200.7,215.7 L 201.0,215.2 L 201.7,215.2 L 202.4,214.6 L 202.8,213.9 L 203.8,213.6 L 205.2,213.1 L 205.9,212.7 L 207.1,212.4 L 207.9,212.3 L 209.0,212.1 L 210.5,211.9 L 211.7,212.2 L 212.9,211.7 L 214.0,211.9 L 215.2,211.7 L 216.7,211.4 L 217.4,211.3 L 218.6,211.1 L 220.1,211.3 L 221.0,211.5 L 222.2,211.2 L 223.6,211.4 L 224.6,211.8 L 226.0,212.0 L 227.3,212.7 L 228.3,213.2 L 229.5,214.3 L 230.2,215.0 L 231.3,215.4 L 233.1,216.0 L 234.9,216.5 L 236.0,217.1 L 236.8,217.9 L 237.7,218.8 L 238.1,220.3 L 239.1,221.6 L 239.9,222.6 L 241.7,223.3 L 242.2,224.2 L 243.2,225.5 L 244.3,226.5 L 244.6,227.6 L 245.7,229.0 L 245.8,230.2 L 246.8,232.2 L 247.5,233.5 L 247.6,234.6 L 248.1,236.1 L 248.7,237.4 L 248.7,238.6 L 248.7,240.3 L 248.3,241.7 L 248.8,243.7 L 249.0,245.5 L 249.0,246.8 L 248.9,248.8 L 249.2,250.4 L 250.0,251.9 L 249.9,253.5 L 249.5,255.7 L 249.5,256.7 L 248.8,258.4 L 248.5,259.5 L 247.2,260.5 L 246.5,262.1 L 245.9,263.4 L 244.8,264.5 L 244.1,266.2 L 243.5,268.0 L 242.5,269.9 L 241.4,271.1 L 240.2,272.3 L 238.4,273.8 L 237.4,275.0 L 236.0,276.4 L 235.2,277.7 L 233.7,278.7 L 232.3,279.5 L 230.8,280.7 L 229.9,282.0 L 228.5,282.8 L 227.0,283.5 L 225.4,284.5 L 223.4,285.9 L 221.7,286.1 L 220.1,286.6 L 218.2,287.4 L 216.4,287.4 L 214.1,288.1 L 212.5,289.1 L 211.1,288.8 L 209.2,288.5 L 207.6,288.9 L 205.1,289.6 L 203.2,289.0 L 201.2,288.8 L 199.1,288.6 L 197.4,288.0 L 195.3,288.3 L 193.0,288.0 L 191.0,287.4 L 189.1,286.9 L 186.8,286.8 L 185.0,285.9 L 182.8,284.9 L 181.3,284.0 L 179.4,282.9 L 177.7,281.9 L 176.0,280.7 L 174.4,279.7 L 172.5,278.2 L 170.5,276.6 L 168.6,275.5 L 167.0,274.4 L 166.1,272.8 L 164.1,271.0 L 162.6,268.9 L 161.2,267.2 L 159.8,265.2 L 158.4,263.9 L 157.3,261.7 L 156.2,260.0 L 155.0,258.0 L 154.4,256.1 L 154.0,253.8 L 153.6,251.4 L 152.7,249.5 L 152.4,247.2 L 151.5,245.1 L 150.9,242.4 L 150.4,240.2 L 149.7,237.9 L 149.7,235.4 L 150.0,233.2 L 150.0,230.6 L 150.4,227.8 L 150.6,225.2 L 151.0,223.0 L 151.5,221.0 L 152.1,218.5 L 152.5,216.4 L 153.4,214.5 L 154.1,212.1 L 155.0,209.7 L 156.1,206.9 L 157.5,204.9 L 159.0,203.4 L 160.2,201.1 L 161.6,199.5 L 162.6,197.5 L 163.8,194.6 L 164.9,192.3 L 167.1,190.2 L 169.0,188.1 L 171.1,186.1 L 173.5,184.3 L 175.4,182.8 L 177.5,181.8 L 179.7,180.1 L 181.8,178.6 L 184.4,177.5 L 186.7,176.7 L 189.0,175.5 L 191.6,175.0 L 194.1,173.9 L 196.3,173.3 L 198.8,172.7 L 201.0,172.3 L 203.4,171.5 L 206.6,170.7 L 209.4,170.4 L 211.9,170.6 L 215.2,169.9 L 217.6,170.2 L 220.1,170.2 L 223.0,170.7 L 225.8,171.0 L 228.5,171.8 L 231.2,172.4 L 233.9,173.1 L 236.7,173.8 L 239.3,174.9 L 242.5,175.9 L 245.4,177.2 L 248.3,178.4 L 250.9,179.9 L 253.4,181.0 L 255.9,181.9 L 258.3,183.7 L 260.9,185.5 L 263.4,187.3 L 265.3,188.9 L 267.1,190.6 L 269.4,192.7 L 271.5,195.0 L 273.7,197.7 L 275.3,200.0 L 276.8,202.0 L 278.6,205.0 L 280.1,207.5 L 281.9,209.5 L 283.2,212.4 L 284.2,215.7 L 285.6,218.5 L 286.5,221.3 L 287.2,224.0 L 288.4,227.3 L 289.2,230.1 L 290.2,233.8 L 290.6,236.6 L 290.5,239.9 L 290.3,243.0 L 290.7,245.8 L 291.1,249.4 L 290.4,252.2 L 290.0,255.1 L 289.4,257.7 L 288.7,261.5 L 287.7,264.6 L 286.5,268.0 L 285.5,271.7 L 284.6,274.6 L 283.6,277.5 L 281.9,280.6 L 280.5,283.5 L 279.1,286.3 L 277.6,289.6 L 275.5,292.8 L 273.6,295.2 L 272.4,297.8 L 270.6,300.6 L 267.8,303.0 L 265.3,305.0 L 262.4,307.3 L 260.1,309.6 L 257.5,311.5 L 254.5,313.4 L 251.5,315.3 L 248.7,316.9 L 245.8,318.4 L 242.8,320.2 L 239.9,321.9 L 236.3,323.2 L 233.3,324.6 L 229.6,325.8 L 226.7,326.8 L 223.4,327.7 L 220.1,328.7 L 216.7,329.3 L 213.1,329.6 L 210.0,329.9 L 206.4,329.9 L 203.1,329.7 L 199.8,329.4 L 195.9,329.3 L 192.4,329.0 L 189.1,328.4 L 185.7,327.6 L 182.4,327.0 L 179.0,326.1 L 175.2,325.0 L 171.9,323.8 L 168.5,322.1 L 165.1,320.5 L 161.5,318.9 L 157.7,317.4 L 154.8,315.5 L 151.5,313.3 L 148.5,310.5 L 145.6,308.6 L 142.7,306.2 L 140.0,303.8 L 137.7,301.3 L 134.9,298.5 L 132.5,296.2 L 130.1,293.0 L 127.6,289.4 L 125.6,286.0 L 123.3,282.3 L 121.1,279.4 L 119.1,275.6 L 117.6,272.3 L 116.4,269.1 L 115.1,265.3 L 113.9,261.9 L 112.7,257.9 L 112.2,254.2 L 111.3,250.5 L 111.0,246.9 L 110.4,243.3 L 110.7,239.9 L 110.7,235.6 L 111.6,231.4 L 111.5,227.3 L 112.0,223.6 L 111.9,219.8 L 112.5,215.8 L 112.8,211.8 L 113.6,208.0 L 114.4,204.4 L 115.4,200.1 L 116.6,196.8 L 118.0,193.7 L 119.8,189.6 L 121.5,186.1 L 123.2,183.2 L 125.1,179.8 L 127.9,176.2 L 130.1,172.7 L 132.8,169.7 L 135.5,166.1 L 138.4,162.8 L 140.7,159.7 L 143.5,157.0 L 147.3,154.8 L 150.5,152.0 L 154.1,149.8 L 157.5,147.4 L 161.8,145.1 L 165.3,143.0 L 169.2,140.8 L 172.9,138.7 L 176.8,137.6 L 181.0,136.1 L 184.7,134.6 L 189.1,133.3 L 193.7,131.9 L 197.7,131.6 L 201.4,131.3 L 205.1,130.7 L 209.5,130.5"


def slugify(title):
    s = re.sub(r"[^\w\s-]", "", title)
    return re.sub(r"\s+", "-", s.strip())


def darken(hex_color, factor=0.5):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


def volume_dir(theme, folder):
    return os.path.join(BASE, theme["root"], folder)


def find_md(theme, folder):
    candidates = glob.glob(os.path.join(volume_dir(theme, folder), "*.md"))
    if len(candidates) != 1:
        sys.exit(f"Errore: trovati {len(candidates)} file .md in '{folder}', attesi 1.")
    return candidates[0]


def read_title_subtitle(md_path):
    with open(md_path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    title = subtitle = None
    for l in lines:
        if title is None and l.startswith("# "):
            title = l[2:].strip()
            continue
        if title is not None and subtitle is None and l.startswith("*") and l.endswith("*") and not l.startswith("**"):
            subtitle = l.strip("*")
            break
    if not title or not subtitle:
        sys.exit("Errore: titolo o sottotitolo non trovati nel .md (servono '# Titolo' e una riga '*Sottotitolo*').")
    return title, subtitle


def split_title(title):
    words = title.upper().split()
    if len(words) == 1 or len(" ".join(words)) <= 9:
        return [" ".join(words)]
    best = None
    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        diff = abs(len(line1) - len(line2))
        if best is None or diff < best[0]:
            best = (diff, line1, line2)
    return [best[1], best[2]]


def title_font_size(lines):
    maxlen = max(len(l) for l in lines)
    if maxlen <= 9:
        return 44
    if maxlen <= 10:
        return 38
    return 34


def subtitle_font_size(subtitle):
    n = len(subtitle)
    if n <= 40:
        return 11
    if n <= 50:
        return 10
    return 9


def build_svg(title_lines, subtitle, color, theme):
    if theme.get("mono"):
        color = theme["ink"]
    accent = darken(color, theme["accent_factor"])
    line_color = darken(color, theme["rule_factor"])
    ink = theme["ink"]
    size = title_font_size(title_lines)
    first_y = size + 406
    gap = size + 5
    if len(title_lines) == 1:
        last_y = first_y
        title_svg = (
            f'<text x="52" y="{first_y}" text-anchor="start" '
            f'font-family="Georgia, serif" font-size="{size}" fill="{ink}">{title_lines[0]}</text>'
        )
    else:
        last_y = first_y + gap
        title_svg = (
            f'<text x="52" y="{first_y}" text-anchor="start" font-family="Georgia, serif" '
            f'font-size="{size}" fill="{ink}">{title_lines[0]}</text>\n'
            f'  <text x="52" y="{last_y}" text-anchor="start" font-family="Georgia, serif" '
            f'font-size="{size}" fill="{ink}">{title_lines[1]}</text>'
        )
    line_y = last_y + 18
    subtitle_y = line_y + 20
    sub_size = subtitle_font_size(subtitle)

    s0, s1, s2 = theme["stops"]

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="800" height="1200">
  <defs>
    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="{s0}"/>
      <stop offset="65%"  stop-color="{s1}"/>
      <stop offset="100%" stop-color="{s2}"/>
    </linearGradient>
  </defs>
  <rect width="400" height="600" fill="url(#grad)"/>
  <text x="200" y="40" text-anchor="middle"
        font-family="Georgia, serif" font-size="9" letter-spacing="5"
        fill="{accent}">{theme["label"]}</text>
  <line x1="52" y1="52" x2="348" y2="52" stroke="{line_color}" stroke-width="0.5"/>
  <path d="{SPIRAL_PATH}" fill="none" stroke="{accent}" stroke-width="2.2"
        stroke-linecap="round" stroke-linejoin="round"/>
  <line x1="52" y1="396" x2="348" y2="396" stroke="{line_color}" stroke-width="0.5"/>
  {title_svg}
  <line x1="52" y1="{line_y}" x2="240" y2="{line_y}" stroke="{accent}" stroke-width="1.0"/>
  <g transform="translate(52,{subtitle_y}) skewX(-11)">
  <text x="0" y="0" text-anchor="start"
        font-family="Georgia, serif" font-size="{sub_size}"
        fill="{accent}">{subtitle}</text>
  </g>
  <line x1="52" y1="546" x2="348" y2="546" stroke="{line_color}" stroke-width="0.5"/>
  <text x="200" y="565" text-anchor="middle"
        font-family="Georgia, serif" font-size="12" letter-spacing="2"
        fill="{ink}">Giovanni Martini</text>
</svg>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--folder", required=True, help="Nome della cartella del volume in Progetti culturali/")
    p.add_argument("--color", required=True, help="Colore accento, es. #9C4A3C")
    p.add_argument("--lang", default="it", choices=sorted(THEMES), help="Serie: it (Erranze) o en (Errancies)")
    p.add_argument("--title", help="Titolo (default: letto dal .md)")
    p.add_argument("--subtitle", help="Sottotitolo (default: letto dal .md)")
    p.add_argument("--line1", help="Forza la prima riga del titolo")
    p.add_argument("--line2", help="Forza la seconda riga del titolo")
    p.add_argument("--font-size", type=int, help="Forza la dimensione del titolo")
    p.add_argument("--subtitle-font-size", type=int, help="Forza la dimensione del sottotitolo")
    args = p.parse_args()

    theme = THEMES[args.lang]

    if args.title and args.subtitle:
        title, subtitle = args.title, args.subtitle
    else:
        md_path = find_md(theme, args.folder)
        title, subtitle = read_title_subtitle(md_path)

    if args.line1 and args.line2:
        title_lines = [args.line1.upper(), args.line2.upper()]
    elif args.line1:
        title_lines = [args.line1.upper()]
    else:
        title_lines = split_title(title)

    global title_font_size
    if args.font_size:
        _orig = title_font_size
        title_font_size = lambda lines: args.font_size  # noqa: E731

    global subtitle_font_size
    if args.subtitle_font_size:
        subtitle_font_size = lambda s: args.subtitle_font_size  # noqa: E731

    svg = build_svg(title_lines, subtitle, args.color, theme)

    slug = slugify(title)
    svg_path = os.path.join(COPERTINE_DIR, f"cover-{theme['prefix']}{slug}.svg")
    os.makedirs(COPERTINE_DIR, exist_ok=True)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    png_dir = os.path.join(volume_dir(theme, args.folder), "Bozze", "Copertina")
    os.makedirs(png_dir, exist_ok=True)

    # cover.png: per l'embedding nell'epub via calibre (--cover), nessun vincolo di formato
    png_path = os.path.join(png_dir, "cover.png")
    cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=800, output_height=1200)

    # cover.jpg: per il caricamento diretto su KDP (Kindle eBook Cover),
    # che richiede JPEG/TIFF, non PNG, e una risoluzione più alta di quella ebook-reader
    jpg_path = os.path.join(png_dir, "cover.jpg")
    png_bytes = cairosvg.svg2png(url=svg_path, output_width=1600, output_height=2400)
    Image.open(io.BytesIO(png_bytes)).convert("RGB").save(
        jpg_path, "JPEG", quality=95, dpi=(300, 300)
    )

    print(f"  ✓ SVG: {svg_path}")
    print(f"  ✓ PNG (epub): {png_path}")
    print(f"  ✓ JPG (KDP, 1600×2400): {jpg_path}")


if __name__ == "__main__":
    main()
