#!/usr/bin/env python3
"""Verifica la conformita' dei volumi allo standard della collana.

Non modifica niente: legge i .md registrati in serie.json (o series-en.json)
e stampa un rapporto di scostamenti dallo standard descritto in CLAUDE.md.

Uso:
    python3 verifica-standard.py                    # tutti i volumi italiani
    python3 verifica-standard.py --volume 7         # un volume solo
    python3 verifica-standard.py --lang en          # serie Errancies
    python3 verifica-standard.py --report rapporto.md
    python3 verifica-standard.py --dettaglio        # elenca tutte le occorrenze

Livelli:
    ERRORE  scostamento dallo standard, va corretto
    AVVISO  da guardare, puo' essere legittimo
"""

import json
import os
import re
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)          # Progetti culturali/

# Numero massimo di occorrenze mostrate per rilievo senza --dettaglio
MAX_ESEMPI = 4

LANGS = {
    "it": {
        "registry": "serie.json",
        "root": "",
        "series_re": r"^\*Collana Erranze · (\d+|\[N\]) — Giovanni Martini\*$",
        "toc": "Sommario",
        "prologo": "Prologo",
        "epilogo": "Epilogo",
        "biblio": "Testi di riferimento",
        "also": "Nella stessa collana",
        "author": "L'autore",
        "em_dash_vietato": True,
        "cc_deed": "deed.it",
    },
    "en": {
        "registry": "series-en.json",
        "root": "English",
        "series_re": r"^\*Errancies · (\d+|\[N\]) — Giovanni Martini\*$",
        "toc": "Contents",
        "prologo": "Prologue",
        "epilogo": "Epilogue",
        "biblio": "Further Reading",
        "also": "Also in This Series",
        "author": "About the Author",
        "em_dash_vietato": False,
        "cc_deed": "deed.en",
    },
}

# --- espressioni usate dai controlli ------------------------------------

RE_COPYRIGHT = re.compile(r"^\*© (\d{4}) Giovanni Martini — \[CC BY-NC-SA 4\.0\]\((\S+)\)\*$")
RE_HEADING = re.compile(r"^(#{1,6}) +(.*?)\s*$")
RE_EMPH = re.compile(r"[*_`]+")
RE_ANNO_FINALE = re.compile(r"\b\d{3,4}(\s*[-–/]\s*\d{2,4})?\.?$")
RE_CORSIVO_IN_PARENTESI = re.compile(r"\(\s*\*[^)]*\*\s*\)")
RE_NOTA_A_PIE = re.compile(r"^\s*(\*{0,2}(Fonti|Fonte|Bibliografia|Note|Riferimenti)\*{0,2}\s*:)", re.I)
RE_RIGA_ORIZZONTALE = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")
RE_DOPPIO_PRIMO = re.compile(r"\d'\d+\"")   # 4'33": secondi, non virgolette
SOGLIA_CITAZIONE = 9                        # parole oltre cui un passo e' una citazione


RE_FINE_NUMERO = re.compile(r"(\d|\b[IVXLCDM]+)$")
RE_INIZIO_NUMERO = re.compile(r"^(\d|[IVXLCDM]+\b)")


def intervallo(s, i):
    """True se il trattino in posizione i e' un intervallo, non un inciso.

    Copre `1915–1920`, `III–VI sec.` e gli intervalli aperti `1983–`.
    """
    prima = s[:i].rstrip()
    dopo = s[i + 1:].lstrip()
    if not RE_FINE_NUMERO.search(prima):
        return False
    return dopo == "" or bool(RE_INIZIO_NUMERO.match(dopo))


def norm(s):
    """Normalizza un titolo per confrontare Sommario e intestazioni reali."""
    s = RE_EMPH.sub("", s)
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    return s.strip().strip(".").lower()


def load_books(cfg):
    with open(os.path.join(SCRIPT_DIR, cfg["registry"]), encoding="utf-8") as f:
        return json.load(f)["books"]


class Rapporto:
    """Raccoglie i rilievi di un volume."""

    def __init__(self, book):
        self.book = book
        self.voci = []          # (livello, categoria, messaggio, [dettagli])

    def errore(self, categoria, messaggio, dettagli=None):
        self.voci.append(("ERRORE", categoria, messaggio, dettagli or []))

    def avviso(self, categoria, messaggio, dettagli=None):
        self.voci.append(("AVVISO", categoria, messaggio, dettagli or []))

    @property
    def n_errori(self):
        return sum(1 for v in self.voci if v[0] == "ERRORE")

    @property
    def n_avvisi(self):
        return sum(1 for v in self.voci if v[0] == "AVVISO")


# --- controlli ----------------------------------------------------------

def controlla_testata(r, cfg, righe, book):
    """1. Testata: titolo, sottotitolo, riga collana, copyright, separatore."""
    utili = [(i, l) for i, l in enumerate(righe[:14], 1) if l.strip()]
    if not utili:
        r.errore("testata", "file vuoto")
        return

    n, titolo = utili[0]
    if not titolo.startswith("# ") or titolo.startswith("## "):
        r.errore("testata", f"riga {n}: la prima riga non e' un titolo `# ...`")
    else:
        testo = titolo[2:].strip()
        lettere = [c for c in testo if c.isalpha()]
        if lettere and all(c.isupper() for c in lettere):
            r.errore("testata", f"titolo tutto MAIUSCOLO: «{testo}»")
        if " — " in testo or " – " in testo:
            r.errore("testata", f"titolo e sottotitolo uniti dal trattino: «{testo}»")

    if len(utili) < 2:
        r.errore("testata", "manca la riga del sottotitolo")
        return
    n, sotto = utili[1]
    if not (sotto.startswith("*") and sotto.endswith("*") and not sotto.startswith("**")):
        r.errore("testata", f"riga {n}: sottotitolo non in corsivo su riga a se': «{sotto}»")

    # riga della collana
    idx_serie = next((i for i, (_, l) in enumerate(utili) if "Giovanni Martini*" in l and "©" not in l), None)
    if idx_serie is None:
        r.errore("testata", "manca la riga della collana")
    else:
        n, riga = utili[idx_serie]
        m = re.match(cfg["series_re"], riga)
        if not m:
            r.errore("testata", f"riga {n}: riga della collana non conforme: «{riga}»")
        elif m.group(1) == "[N]":
            r.errore("testata", "placeholder [N] non sostituito nella riga della collana")
        elif int(m.group(1)) != book["n"]:
            r.errore("testata", f"numero di volume {m.group(1)} diverso da serie.json ({book['n']})")

    idx_cc = next((i for i, (_, l) in enumerate(utili) if l.startswith("*©")), None)
    if idx_cc is None:
        r.errore("testata", "manca la riga di copyright")
    else:
        n, riga = utili[idx_cc]
        m = RE_COPYRIGHT.match(riga)
        if not m:
            r.errore("testata", f"riga {n}: copyright non conforme: «{riga}»")
        elif cfg["cc_deed"] not in m.group(2):
            r.avviso("testata", f"riga {n}: licenza con deed «{m.group(2)}», atteso {cfg['cc_deed']}")

    if idx_cc is not None:
        resto = []
        for n, l in utili[idx_cc + 1:]:
            if l.startswith("## "):
                break                     # inizia il Sommario: la testata finisce qui
            resto.append((n, l))
        # La dichiarazione sull'uso dell'AI fa parte della testata: la inserisce
        # aggiorna-collana.py dalle costanti AI_IT / AI_EN. Senza questa riga il
        # validatore la segnalava come «extra» su tutti e venti i volumi.
        def e_dichiarazione_ai(l):
            return (l.startswith("*Il testo è stato scritto dall'autore")
                    or l.startswith("*The Italian original was written by the author"))

        extra = [(n, l) for n, l in resto if l.strip() != "---"
                 and not l.startswith("*Originally published")
                 and not e_dichiarazione_ai(l)]
        if extra:
            r.avviso("testata", "righe extra fra copyright e Sommario",
                     [f"riga {n}: {l[:70]}" for n, l in extra[:3]])


def estrai_intestazioni(righe):
    out = []
    dentro_codice = False
    for i, l in enumerate(righe, 1):
        if l.startswith("```"):
            dentro_codice = not dentro_codice
            continue
        if dentro_codice:
            continue
        m = RE_HEADING.match(l)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
    return out


def controlla_gerarchia(r, cfg, intestazioni):
    """4. Gerarchia: un solo h1, niente h5+, due punti come separatore."""
    h1 = [(n, t) for n, liv, t in intestazioni if liv == 1]
    if len(h1) > 1:
        r.errore("gerarchia", f"{len(h1)} intestazioni di livello 1 (deve essercene una sola)",
                 [f"riga {n}: {t}" for n, t in h1[1:]])

    profonde = [(n, liv, t) for n, liv, t in intestazioni if liv >= 5]
    if profonde:
        r.errore("gerarchia", f"{len(profonde)} intestazioni di livello 5 o piu' (max h4)",
                 [f"riga {n}: {'#' * liv} {t}" for n, liv, t in profonde])

    h4 = [(n, t) for n, liv, t in intestazioni if liv == 4]
    if len(h4) > 6:
        r.avviso("gerarchia", f"{len(h4)} intestazioni h4 (usare con parsimonia)",
                 [f"riga {n}: {t}" for n, t in h4[:MAX_ESEMPI]])

    orfane = [(n, t) for n, liv, t in intestazioni if liv == 3]
    # una h3 senza h2 che la precede
    liv_corrente = 0
    for n, liv, t in intestazioni:
        if liv == 3 and liv_corrente < 2:
            r.errore("gerarchia", f"riga {n}: h3 «{t}» senza una h2 che la apra")
        if liv <= 3:
            liv_corrente = liv

    trattino = [(n, liv, t) for n, liv, t in intestazioni if liv in (2, 3) and (" — " in t or " – " in t)]
    if trattino:
        r.errore("gerarchia", f"{len(trattino)} intestazioni con trattino lungo invece dei due punti",
                 [f"riga {n}: {'#' * liv} {t}" for n, liv, t in trattino])


def controlla_cornice(r, cfg, intestazioni):
    """3. Cornice: Prologo in apertura, Epilogo in chiusura."""
    h2 = [(n, t) for n, liv, t in intestazioni if liv == 2]
    titoli = [t for _, t in h2]

    def indice(prefisso):
        for i, t in enumerate(titoli):
            if t == prefisso or t.startswith(prefisso + ":"):
                return i
        return None

    i_toc = indice(cfg["toc"])
    i_pro = indice(cfg["prologo"])
    i_epi = indice(cfg["epilogo"])
    i_bib = indice(cfg["biblio"])

    for nome, i in ((cfg["toc"], i_toc), (cfg["prologo"], i_pro),
                    (cfg["epilogo"], i_epi), (cfg["biblio"], i_bib)):
        if i is None:
            r.errore("cornice", f"manca la sezione `## {nome}`")

    for alt in ("Introduzione", "Premessa", "Conclusione", "Postfazione",
                "Introduction", "Foreword", "Conclusion", "Afterword"):
        j = indice(alt)
        if j is not None:
            r.errore("cornice", f"sezione `## {alt}`: usare {cfg['prologo']}/{cfg['epilogo']}")

    if i_toc is not None and i_pro is not None and i_pro != i_toc + 1:
        r.avviso("cornice", f"fra {cfg['toc']} e {cfg['prologo']} ci sono altre sezioni")
    if i_epi is not None and i_bib is not None and i_bib != i_epi + 1:
        r.avviso("cornice", f"{cfg['biblio']} non segue immediatamente {cfg['epilogo']}")
    if i_pro is not None and i_pro > 1:
        r.errore("cornice", f"{cfg['prologo']} non e' la prima sezione dopo la testata")


def blocco_sezione(righe, intestazioni, titolo, livello=2):
    """Righe (1-based) di una sezione, esclusa la sua intestazione."""
    for k, (n, liv, t) in enumerate(intestazioni):
        if liv == livello and (t == titolo or t.startswith(titolo + ":")):
            fine = len(righe)
            for n2, liv2, _ in intestazioni[k + 1:]:
                if liv2 <= livello:
                    fine = n2 - 1
                    break
            return n, fine
    return None, None


def controlla_sommario(r, cfg, righe, intestazioni):
    """2. Sommario completo e allineato alla struttura reale."""
    inizio, fine = blocco_sezione(righe, intestazioni, cfg["toc"])
    if inizio is None:
        return

    dichiarate_h2, dichiarate_h3 = [], []
    for l in righe[inizio:fine]:
        s = l.strip()
        if not s or s == "---":
            continue
        if s.startswith("- "):
            dichiarate_h3.append(norm(s[2:]))
        elif s.startswith("**"):
            dichiarate_h2.append(norm(s))
        else:
            r.avviso("sommario", f"riga non riconosciuta nel {cfg['toc']}: «{s[:70]}»")

    auto = {norm(cfg["also"]), norm(cfg["author"]), norm(cfg["toc"])}
    reali_h2 = [(n, t) for n, liv, t in intestazioni if liv == 2 and norm(t) not in auto]
    i_bib_riga, _ = blocco_sezione(righe, intestazioni, cfg["biblio"])
    reali_h3 = [(n, t) for n, liv, t in intestazioni
                if liv == 3 and (i_bib_riga is None or n < i_bib_riga)]

    confronta(r, cfg, "sezioni `##`", reali_h2, dichiarate_h2)
    confronta(r, cfg, "sottosezioni `###`", reali_h3, dichiarate_h3)

    # ordine
    set_h2, set_reali_h2 = set(dichiarate_h2), {norm(t) for _, t in reali_h2}
    ordine_reale = [norm(t) for _, t in reali_h2 if norm(t) in set_h2]
    ordine_dich = [d for d in dichiarate_h2 if d in set_reali_h2]
    if ordine_reale != ordine_dich:
        r.errore("sommario", f"l'ordine delle sezioni nel {cfg['toc']} non segue quello del testo")


def confronta(r, cfg, etichetta, reali, dichiarate):
    """Distingue voci divergenti (stesso posto, testo diverso) da vere assenze."""
    resta_reali = [(n, t) for n, t in reali if norm(t) not in set(dichiarate)]
    resta_dich = [d for d in dichiarate if d not in {norm(t) for _, t in reali}]

    # accoppia per prefisso: `### Borges` contro `- Borges: *El Golem*`
    divergenti, usate = [], set()
    for n, t in resta_reali:
        chiave = norm(t)
        for d in resta_dich:
            if d in usate:
                continue
            if d.startswith(chiave + ":") or chiave.startswith(d + ":") or d.startswith(chiave + " ("):
                divergenti.append((n, t, d))
                usate.add(d)
                break

    accoppiate = {n for n, _, _ in divergenti}
    mancanti = [(n, t) for n, t in resta_reali if n not in accoppiate]
    fantasma = [d for d in resta_dich if d not in usate]

    if divergenti:
        r.errore("sommario", f"{len(divergenti)} {etichetta} con testo diverso fra {cfg['toc']} e corpo",
                 [f"riga {n}: corpo «{t}» / {cfg['toc']} «{d}»" for n, t, d in divergenti])
    if mancanti:
        r.errore("sommario", f"{len(mancanti)} {etichetta} assenti dal {cfg['toc']}",
                 [f"riga {n}: {t}" for n, t in mancanti])
    if fantasma:
        r.errore("sommario", f"{len(fantasma)} voci del {cfg['toc']} senza riscontro nel corpo ({etichetta})",
                 fantasma)


def controlla_trattini(r, cfg, righe, intestazioni):
    """5. Niente trattino lungo nel corpo (solo italiano)."""
    if not cfg["em_dash_vietato"]:
        return

    i_also, f_also = blocco_sezione(righe, intestazioni, cfg["also"])
    esenti = set()
    if i_also:
        esenti.update(range(i_also, (f_also or len(righe)) + 1))

    occorrenze = []
    dentro_codice = False
    for i, l in enumerate(righe, 1):
        if l.startswith("```"):
            dentro_codice = not dentro_codice
            continue
        if dentro_codice or i in esenti:
            continue
        s = l.strip()
        if s.startswith("*©") or "Giovanni Martini*" in s or s.startswith("*Originally published"):
            continue
        for m in re.finditer(r"[—–]", s):
            # `1915–1920`, `III–VI sec.`, `1983–`: intervalli, non incisi
            if intervallo(s, m.start()):
                continue
            # trattino di dialogo a inizio riga: tipografia corretta nelle
            # citazioni di dialogo letterario (p.es. Calvino nel vol. 4)
            if m.start() == 0:
                continue
            occorrenze.append((i, s[max(0, m.start() - 35):m.start() + 35]))

    if occorrenze:
        r.errore("trattini", f"{len(occorrenze)} trattini lunghi nel corpo",
                 [f"riga {n}: …{s}…" for n, s in occorrenze])


def controlla_bibliografia(r, cfg, righe, intestazioni):
    """6. Testi di riferimento: sottosezioni, voci compatte, formato."""
    inizio, fine = blocco_sezione(righe, intestazioni, cfg["biblio"])
    if inizio is None:
        return

    sotto = [(n, t) for n, liv, t in intestazioni if liv == 3 and inizio < n <= (fine or len(righe))]
    if not sotto:
        r.errore("bibliografia", f"`## {cfg['biblio']}` senza sottosezioni `###` tematiche")

    voci, buchi, blocco = [], [], []
    for i in range(inizio, (fine or len(righe))):
        l = righe[i].strip()
        n = i + 1
        if RE_HEADING.match(righe[i]):
            blocco = []
            continue
        if not l or RE_RIGA_ORIZZONTALE.match(l):
            if blocco:
                blocco = []          # chiude un blocco; una riga vuota successiva e' innocua
            continue
        if blocco == [] and voci and voci[-1][0] == n - 2:
            buchi.append(n)          # riga vuota fra due voci consecutive
        voci.append((n, l))
        blocco.append(n)

    if buchi:
        r.errore("bibliografia", f"{len(buchi)} righe vuote fra voci della stessa sottosezione",
                 [f"riga {n}" for n in buchi])

    senza_anno = [(n, l) for n, l in voci if not RE_ANNO_FINALE.search(l)]
    if senza_anno:
        r.avviso("bibliografia", f"{len(senza_anno)} voci che non terminano con l'anno",
                 [f"riga {n}: {l[:70]}" for n, l in senza_anno])

    senza_corsivo = [(n, l) for n, l in voci if "*" not in l]
    if senza_corsivo:
        r.avviso("bibliografia", f"{len(senza_corsivo)} voci senza titolo in corsivo",
                 [f"riga {n}: {l[:70]}" for n, l in senza_corsivo])

    corsivo_orig = [(n, l) for n, l in voci if RE_CORSIVO_IN_PARENTESI.search(l)]
    if corsivo_orig:
        r.errore("bibliografia", f"{len(corsivo_orig)} titoli originali in corsivo (vanno in tondo)",
                 [f"riga {n}: {l[:70]}" for n, l in corsivo_orig])

    # riferimenti fuori posto
    fuori = []
    dentro_codice = False
    for i, l in enumerate(righe, 1):
        if l.startswith("```"):
            dentro_codice = not dentro_codice
            continue
        if dentro_codice or i > inizio:
            continue
        if RE_NOTA_A_PIE.match(l):
            fuori.append((i, l.strip()))
    if fuori:
        r.errore("bibliografia", f"{len(fuori)} blocchi di riferimenti fuori da `## {cfg['biblio']}`",
                 [f"riga {n}: {l[:70]}" for n, l in fuori])


def controlla_automatiche(r, cfg, book, righe, intestazioni, books):
    """7. Nella stessa collana + L'autore, generate da aggiorna-collana.py."""
    titoli = [t for _, liv, t in intestazioni if liv == 2]
    attesi = [b for b in books if b["n"] < book["n"]]

    if cfg["also"] in titoli:
        inizio, fine = blocco_sezione(righe, intestazioni, cfg["also"])
        elencati = [l.strip() for l in righe[inizio:fine] if l.strip()]
        if len(elencati) != len(attesi):
            r.errore("automatiche",
                     f"`{cfg['also']}` elenca {len(elencati)} volumi, attesi {len(attesi)}: "
                     f"rigenerare con aggiorna-collana.py")
        else:
            atteso_txt = [f"{b['n']}. *{b['title']}*" for b in attesi]
            diverse = [(a, e) for a, e in zip(atteso_txt, elencati) if a != e]
            if diverse:
                r.errore("automatiche",
                         f"`{cfg['also']}` non corrisponde al registro ({len(diverse)} voci)",
                         [f"atteso: {a} / trovato: {e}" for a, e in diverse[:MAX_ESEMPI]])
    elif attesi:
        r.errore("automatiche", f"manca `## {cfg['also']}` (attesi {len(attesi)} volumi)")

    if cfg["author"] not in titoli:
        r.errore("automatiche", f"manca `## {cfg['author']}`")

    if titoli and titoli[-1] != cfg["author"]:
        r.avviso("automatiche", f"`{cfg['author']}` non e' l'ultima sezione del file")


def controlla_file_collegati(r, cfg, book):
    """Copertina ed epub attesi dal flusso di pubblicazione."""
    folder = os.path.join(ROOT, cfg["root"], book["folder"])
    cop = os.path.join(folder, "Bozze", "Copertina")
    for nome in ("cover.png", "cover.jpg"):
        if not os.path.exists(os.path.join(cop, nome)):
            r.avviso("file", f"manca Bozze/Copertina/{nome}")
    if not os.path.exists(os.path.join(folder, book["file"] + ".epub")):
        r.avviso("file", "manca l'epub nella cartella del volume")


def controlla_tipografia(r, cfg, righe, intestazioni):
    """Virgolette.

    La collana usa le guillemets per le *citazioni* e le virgolette dritte per
    i termini usati in senso particolare, le glosse, i titoli brevi. Segnalare
    ogni virgoletta dritta produrrebbe centinaia di falsi positivi: si segnala
    quindi solo un passo lungo fra virgolette dritte, che quasi sempre e' una
    citazione sfuggita alle guillemets. Le virgolette curve non appartengono
    invece a nessuna delle due funzioni.
    """
    i_bib, _ = blocco_sezione(righe, intestazioni, cfg["biblio"])
    limite = i_bib or len(righe)
    testo = "\n".join(righe[:limite])
    testo = RE_DOPPIO_PRIMO.sub(lambda m: m.group().replace('"', "\x00"), testo)

    lunghe = []
    for m in re.finditer(r'"([^"]*)"', testo):
        if len(m.group(1).split()) >= SOGLIA_CITAZIONE:
            riga = testo.count("\n", 0, m.start()) + 1
            lunghe.append(f"riga {riga}: {m.group(1)[:70]}…")
    if lunghe:
        r.avviso("tipografia",
                 f"{len(lunghe)} passi lunghi fra virgolette dritte (probabili citazioni: la collana usa «»)",
                 lunghe)

    ricce = [i for i, l in enumerate(righe[:limite], 1) if "“" in l or "”" in l]
    if ricce:
        r.avviso("tipografia", f"{len(ricce)} righe con virgolette curve “ ” (la collana usa «» o \")",
                 [f"riga {n}" for n in ricce])


# --- orchestrazione -----------------------------------------------------

def verifica(cfg, book, books):
    r = Rapporto(book)
    path = os.path.join(ROOT, cfg["root"], book["folder"], book["file"] + ".md")
    if not os.path.exists(path):
        r.errore("file", f"file non trovato: {path}")
        return r

    with open(path, encoding="utf-8") as f:
        righe = f.read().split("\n")

    intestazioni = estrai_intestazioni(righe)
    controlla_testata(r, cfg, righe, book)
    controlla_gerarchia(r, cfg, intestazioni)
    controlla_cornice(r, cfg, intestazioni)
    controlla_sommario(r, cfg, righe, intestazioni)
    controlla_trattini(r, cfg, righe, intestazioni)
    controlla_bibliografia(r, cfg, righe, intestazioni)
    controlla_automatiche(r, cfg, book, righe, intestazioni, books)
    controlla_tipografia(r, cfg, righe, intestazioni)
    controlla_file_collegati(r, cfg, book)
    return r


def stampa(rapporti, dettaglio, out):
    def p(s=""):
        out.append(s)

    p("# Verifica dello standard")
    p()
    p("| Vol. | Titolo | Errori | Avvisi |")
    p("|---:|---|---:|---:|")
    for r in rapporti:
        p(f"| {r.book['n']} | {r.book['title']} | {r.n_errori or ''} | {r.n_avvisi or ''} |")
    p()
    tot_e = sum(r.n_errori for r in rapporti)
    tot_a = sum(r.n_avvisi for r in rapporti)
    puliti = [r.book["n"] for r in rapporti if not r.voci]
    p(f"**Totale**: {tot_e} errori, {tot_a} avvisi su {len(rapporti)} volumi.")
    if puliti:
        p(f"**Conformi senza rilievi**: {', '.join(str(n) for n in puliti)}.")
    p()

    categorie = Counter(c for r in rapporti for liv, c, _, _ in r.voci if liv == "ERRORE")
    if categorie:
        p("## Errori per categoria")
        p()
        for c, n in categorie.most_common():
            p(f"- **{c}**: {n}")
        p()

    p("## Dettaglio per volume")
    for r in rapporti:
        if not r.voci:
            continue
        p()
        p(f"### Vol. {r.book['n']} — {r.book['title']}")
        p()
        for liv, cat, msg, det in r.voci:
            p(f"- **{liv}** ({cat}) {msg}")
            mostra = det if dettaglio else det[:MAX_ESEMPI]
            for d in mostra:
                p(f"  - {d}")
            if not dettaglio and len(det) > MAX_ESEMPI:
                p(f"  - … e altre {len(det) - MAX_ESEMPI} (usa --dettaglio)")


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
        books_target = [b for b in books if b["n"] == int(vol)]
        if not books_target:
            print(f"Errore: volume {vol} non trovato", file=sys.stderr)
            sys.exit(1)
    else:
        books_target = books

    rapporti = [verifica(cfg, b, books) for b in books_target]

    out = []
    stampa(rapporti, "--dettaglio" in argv, out)
    testo = "\n".join(out)

    dest = opt("--report")
    if dest:
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(testo + "\n")
        print(f"Rapporto scritto in {dest}")
    print(testo)


if __name__ == "__main__":
    main()
