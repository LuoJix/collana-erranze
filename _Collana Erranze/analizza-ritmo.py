#!/usr/bin/env python3
"""Analizza il ritmo della prosa e i tic di scrittura automatica.

Non modifica niente: legge i .md registrati in serie.json (o series-en.json),
misura la prosa del corpo (esclusi testata, Sommario, Testi di riferimento e
sezioni automatiche) e produce un rapporto comparativo fra i volumi.

Uso:
    python3 analizza-ritmo.py                        # tutti i volumi
    python3 analizza-ritmo.py --volume 15
    python3 analizza-ritmo.py --riferimento 14       # confronto con un volume
    python3 analizza-ritmo.py --lang en
    python3 analizza-ritmo.py --report ritmo.md
    python3 analizza-ritmo.py --dettaglio            # righe di ogni occorrenza

Che cosa misura:
    - lunghezza media delle frasi, deviazione standard, code lunghe e corte
    - connettivi-stampella ripetuti
    - frasi che aprono con la negazione ("Non X, ma Y")
    - chiusure di sottosezione tutte con lo stesso schema retorico
    - n-grammi ricorrenti (tic specifici del singolo volume)
"""

import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)

FRASE_LUNGA = 45        # parole: soglia "frase molto lunga"
FRASE_BREVE = 8         # parole: soglia "frase molto breve"
MAX_ESEMPI = 5

LANGS = {
    "it": {
        "registry": "serie.json",
        "root": "",
        "escluse": ["Sommario", "Testi di riferimento", "Nella stessa collana", "L'autore"],
        "connettivi": [
            "in questa luce", "in questa prospettiva", "in questa chiave",
            "in questa lettura", "in questo senso", "sotto questa luce",
            "e' per questo che", "non e' un caso che", "vale la pena",
            "in altre parole", "per cosi' dire", "in un certo senso",
            "a ben vedere", "in ultima analisi", "in definitiva",
            "cio' che conta", "il punto e' che", "la posta in gioco",
            "il paradosso e' che", "resta il fatto che", "va detto che",
            "occorre notare", "al tempo stesso", "allo stesso tempo",
            "non tanto", "non solo", "non e' che",
            "la domanda non e'", "la questione non e'",
        ],
        "negazione_re": r"^(Non|Né|Nessun[ao]?)\b",
        "chiusura_re": r":\s+[^.!?]*\bnon\b[^.!?]*\bma\b",
        "vaghi": [
            r"\b(?:molti|alcuni|diversi|numerosi|parecchi|non pochi)\s+"
            r"(?:studiosi|critici|autori|commentatori|storici|ricercatori|interpreti|lettori)\b",
            r"\bla maggior parte (?:degli|dei) (?:studiosi|critici|storici|autori)\b",
            r"\bsecondo (?:molti|alcuni|i piu')\b",
            r"\be' (?:spesso|di solito|comunemente|generalmente) "
            r"(?:letto|letta|interpretato|interpretata|considerato|considerata|ritenuto|ritenuta|visto|vista)\b",
            r"\bsi (?:dice|ritiene|sostiene|legge) (?:spesso|di solito|comunemente)\b",
            r"\bchiunque abbia\b",
            r"\bcome e' noto\b",
            r"\be' noto che\b",
        ],
    },
    "en": {
        "registry": "series-en.json",
        "root": "English",
        "escluse": ["Contents", "Further Reading", "Also in This Series", "About the Author"],
        "connettivi": [
            "in this light", "in this sense", "in this perspective",
            "it is no accident", "it is worth noting", "in other words",
            "so to speak", "in a certain sense", "ultimately",
            "what matters is", "the point is that", "at stake",
            "the paradox is that", "it is precisely", "at the same time",
            "not merely", "not simply", "the question is not",
        ],
        "negazione_re": r"^(Not|Neither|No)\b",
        "chiusura_re": r":\s+[^.!?]*\bnot\b[^.!?]*\bbut\b",
        "vaghi": [
            r"\b(?:many|some|several|numerous)\s+"
            r"(?:scholars|critics|commentators|historians|researchers|readers)\b",
            r"\bmost (?:scholars|critics|historians|readers)\b",
            r"\bis (?:often|usually|commonly|generally) "
            r"(?:read|interpreted|seen|taken|considered|held)\b",
            r"\bit is (?:often|widely) (?:said|held|believed|assumed)\b",
            r"\banyone who has\b",
            r"\bas is well known\b",
        ],
        "translationese": True,   # vedi la checklist in English/Errancies.md
    },
}

# Sintomi del translationese italiano -> inglese. Sono misure di densita', non
# di correttezza: nessuna di queste parole e' sbagliata in se'. Servono a
# confrontare i volumi fra loro e a dare all'autore una lista da guardare,
# perche' il calco sopravvive proprio quando la frase sembra corretta.

# Connettivi resi alla lettera da 'infatti, del resto, ora, dunque, d'altra
# parte'. L'inglese saggistico ne usa molti meno, spesso nessuno.
TR_CONNETTIVI = [
    "in fact", "as a matter of fact", "moreover", "furthermore", "indeed",
    "on the other hand", "on the contrary", "besides", "therefore", "thus",
    "hence", "for the rest", "that said", "having said that", "in effect",
]

# Cognati latini: la parola normale dell'italiano e' il registro formale, o
# addirittura il falso amico, dell'inglese. Vanno guardati uno per uno.
TR_COGNATI = {
    "individuate": "identify", "evidence": "show (se e' verbo)",
    "utilise": "use", "utilize": "use", "effectuate": "carry out",
    "problematise": "question", "problematize": "question",
    "thematise": "treat", "thematize": "treat",
    "valorise": "bring out", "valorize": "bring out",
    "concretise": "make concrete", "concretize": "make concrete",
    "eventual": "possible? (it. eventuale)", "eventually": "in the end? (it. eventualmente)",
    "actual": "current? (it. attuale)", "actually": "currently? (it. attualmente)",
    "pretend": "claim/demand? (it. pretendere)", "attend": "wait for? (it. attendere)",
    "assist": "attend? (it. assistere)", "comprehensive": "inclusive? (it. comprensivo)",
    "sensible": "noticeable? (it. sensibile)", "casual": "random? (it. casuale)",
    "ulterior": "further? (it. ulteriore)", "argument": "topic? (it. argomento)",
    "confront": "compare? (it. confrontare)", "delusion": "disappointment? (it. delusione)",
    "education": "upbringing? (it. educazione)", "morbid": "morbose? (it. morboso)",
    "preventive": "precautionary? (it. preventivo)", "scope": "aim? (it. scopo)",
    "notice": "news? (it. notizia)", "conserve": "keep? (it. conservare)",
}

# Attenuativi: normali in italiano, in inglese diventano esitazione.
TR_ATTENUATIVI = [
    "perhaps", "in a sense", "in a certain sense", "so to speak", "somewhat",
    "arguably", "more or less", "to some extent", "in some way", "as it were",
]

RE_TR_NOM = re.compile(r"\b\w+(?:tions?|sions?|ities|ity)\b", re.I)
RE_TR_NOI = re.compile(r"\b(?:we|us|our|ourselves)\b", re.I)
RE_TR_MATTER = re.compile(r"\bit is (?:a matter|a question) of\b", re.I)
RE_TR_PASS = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ed|born|made|given|taken|seen|"
    r"known|written|done|held|kept|left|found|shown|built|drawn|brought)\b", re.I)
RE_TR_COPPIA = re.compile(
    r"\b(\w{4,}(?:ic|al|ive|ous|ful|ent|ant|ary|able|ible))\s+and\s+"
    r"(\w{4,}(?:ic|al|ive|ous|ful|ent|ant|ary|able|ible))\b", re.I)

RE_HEADING = re.compile(r"^(#{1,6}) +(.*?)\s*$")
RE_EMPH = re.compile(r"[*_`]")
RE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
RE_SPLIT = re.compile(r"(?<=[.!?…])[»\"']?\s+(?=[«\"'A-ZÀ-ÖØ-Þ0-9])")
RE_PAROLA = re.compile(r"[\wÀ-ÿ'’-]+")


def norm_accenti(s):
    """Toglie gli accenti finali piu' comuni, per confrontare i connettivi."""
    return (s.replace("è", "e'").replace("é", "e'").replace("à", "a'")
             .replace("ò", "o'").replace("ù", "u'").replace("ì", "i'")
             .replace("’", "'"))


def load_books(cfg):
    with open(os.path.join(SCRIPT_DIR, cfg["registry"]), encoding="utf-8") as f:
        return json.load(f)["books"]


def estrai_corpo(cfg, path):
    """Ritorna (paragrafi, sottosezioni).

    paragrafi: lista di (riga, testo) del corpo narrativo
    sottosezioni: dict titolo -> lista di paragrafi, per le h3 del corpo
    """
    with open(path, encoding="utf-8") as f:
        righe = f.read().split("\n")

    escluse = {t.lower() for t in cfg["escluse"]}
    paragrafi = []
    sottosezioni = defaultdict(list)

    sezione_esclusa = True          # la testata sta fuori
    sotto_corrente = None
    dentro_codice = False
    buffer_righe, buffer_inizio = [], 0

    def chiudi():
        nonlocal buffer_righe
        if buffer_righe:
            testo = " ".join(buffer_righe).strip()
            if testo:
                paragrafi.append((buffer_inizio, testo))
                if sotto_corrente:
                    sottosezioni[sotto_corrente].append((buffer_inizio, testo))
        buffer_righe = []

    for i, l in enumerate(righe, 1):
        if l.startswith("```"):
            dentro_codice = not dentro_codice
            chiudi()
            continue
        if dentro_codice:
            continue

        m = RE_HEADING.match(l)
        if m:
            chiudi()
            liv, titolo = len(m.group(1)), m.group(2)
            if liv <= 2:
                sezione_esclusa = titolo.strip().lower() in escluse or liv == 1
                sotto_corrente = None
            elif liv == 3 and not sezione_esclusa:
                sotto_corrente = titolo
            continue

        if sezione_esclusa:
            continue

        s = l.strip()
        if not s or s == "---":
            chiudi()
            continue
        if s.startswith(("- ", "* ", "> ", "|")) or re.match(r"^\d+\. ", s):
            chiudi()
            continue

        if not buffer_righe:
            buffer_inizio = i
        buffer_righe.append(s)

    chiudi()
    return paragrafi, sottosezioni


def pulisci(testo):
    testo = RE_LINK.sub(r"\1", testo)
    return RE_EMPH.sub("", testo)


def frasi_di(paragrafi):
    """Lista di (riga, frase, n_parole)."""
    out = []
    for riga, testo in paragrafi:
        for f in RE_SPLIT.split(pulisci(testo)):
            f = f.strip()
            if len(f) < 3:
                continue
            n = len(RE_PAROLA.findall(f))
            if n:
                out.append((riga, f, n))
    return out


def ngrammi(frasi, n=4, minimo=3):
    conta = Counter()
    for _, f, _ in frasi:
        parole = [p.lower() for p in RE_PAROLA.findall(norm_accenti(f))]
        for i in range(len(parole) - n + 1):
            conta[" ".join(parole[i:i + n])] += 1
    return [(g, c) for g, c in conta.most_common(40) if c >= minimo]


def analizza_translationese(a, paragrafi, frasi):
    """Sintomi del calco italiano -> inglese. Riempie le chiavi 'tr_*' di a.stat
    (tassi per mille parole) e aggiunge i rilievi con le righe da guardare."""
    testo = " ".join(pulisci(t) for _, t in paragrafi)
    piano = testo.lower()
    parole = len(RE_PAROLA.findall(testo)) or 1
    per_mille = lambda n: 1000.0 * n / parole   # noqa: E731

    def righe_con(regex_o_str, limite=MAX_ESEMPI):
        """Righe del .md in cui compare il pattern, per il rapporto."""
        rx = (regex_o_str if hasattr(regex_o_str, "search")
              else re.compile(r"\b" + re.escape(regex_o_str) + r"\b", re.I))
        out = []
        for r, t in paragrafi:
            for m in rx.finditer(pulisci(t)):
                out.append((r, m.group(0)))
                if len(out) >= limite:
                    return out
        return out

    # 1. nominalizzazioni: l'italiano saggistico ama i nomi astratti, l'inglese
    #    vuole i verbi. Densita' alta = paragrafi da riscrivere.
    nom = RE_TR_NOM.findall(testo)
    a.stat["tr_nom"] = per_mille(len(nom))

    # 2. il "noi" saggistico: neutro in italiano, predicatorio in inglese
    #    se usato con la stessa frequenza.
    a.stat["tr_noi"] = per_mille(len(RE_TR_NOI.findall(testo)))

    # 3. connettivi resi alla lettera
    conn = [(c, piano.count(c)) for c in TR_CONNETTIVI]
    conn = sorted([(c, n) for c, n in conn if n], key=lambda x: -x[1])
    a.stat["tr_conn"] = per_mille(sum(n for _, n in conn))
    if conn:
        a.nota("EN connettivi", f"{sum(n for _, n in conn)} connettivi da traduzione",
               [f"«{c}» × {n}" for c, n in conn])

    # 4. cognati latini e falsi amici: da guardare uno per uno
    cog = []
    for parola, meglio in TR_COGNATI.items():
        n = len(re.findall(r"\b" + parola + r"\b", piano))
        if n:
            righe = ", ".join(f"riga {r}" for r, _ in righe_con(parola, 3))
            cog.append((n, f"«{parola}» × {n} → {meglio}  ({righe})"))
    a.stat["tr_cognati"] = sum(n for n, _ in cog)
    if cog:
        a.nota("EN cognati", f"{len(cog)} cognati o falsi amici da verificare",
               [d for _, d in sorted(cog, key=lambda x: -x[0])])

    # 5. "si tratta di": la firma piu' riconoscibile in assoluto
    matter = righe_con(RE_TR_MATTER, 20)
    a.stat["tr_matter"] = len(matter)
    if matter:
        a.nota("EN si-tratta-di", f"{len(matter)} occorrenze di «it is a matter/question of»",
               [f"riga {r}: {m}" for r, m in matter])

    # 6. passivi a catena, dalle impersonali con "si"
    a.stat["tr_pass"] = per_mille(len(RE_TR_PASS.findall(testo)))

    # 7. raddoppio aggettivale: in inglese se ne tiene uno
    coppie = righe_con(RE_TR_COPPIA, 20)
    a.stat["tr_coppie"] = len(coppie)
    if coppie:
        a.nota("EN raddoppi", f"{len(coppie)} coppie aggettivali «X and Y»",
               [f"riga {r}: {m}" for r, m in coppie])

    # 8. domanda retorica in chiusura di paragrafo: l'italiano la concede,
    #    l'inglese molto meno. Sopravvive solo dove e' davvero il perno.
    dom = []
    for r, t in paragrafi:
        fr = frasi_di([(r, t)])
        if fr and fr[-1][1].rstrip().endswith("?"):
            dom.append((r, fr[-1][1]))
    a.stat["tr_domande"] = len(dom)
    a.stat["tr_pct_domande"] = 100.0 * len(dom) / len(paragrafi) if paragrafi else 0
    if dom:
        a.nota("EN domande",
               f"{len(dom)} paragrafi su {len(paragrafi)} chiudono con una domanda "
               f"({a.stat['tr_pct_domande']:.1f}%)",
               [f"riga {r}: {f[:90]}" for r, f in dom[:MAX_ESEMPI * 2]])

    # 9. attenuativi: normali in italiano, esitazione in inglese
    att = sorted([(c, piano.count(c)) for c in TR_ATTENUATIVI if piano.count(c)],
                 key=lambda x: -x[1])
    a.stat["tr_att"] = per_mille(sum(n for _, n in att))
    if att:
        a.nota("EN attenuativi", f"{sum(n for _, n in att)} attenuativi",
               [f"«{c}» × {n}" for c, n in att])


class Analisi:
    def __init__(self, book):
        self.book = book
        self.rilievi = []       # (categoria, messaggio, dettagli)

    def nota(self, categoria, messaggio, dettagli=None):
        self.rilievi.append((categoria, messaggio, dettagli or []))


def analizza(cfg, book):
    a = Analisi(book)
    path = os.path.join(ROOT, cfg["root"], book["folder"], book["file"] + ".md")
    if not os.path.exists(path):
        a.stat = None
        return a

    paragrafi, sottosezioni = estrai_corpo(cfg, path)
    frasi = frasi_di(paragrafi)
    lunghezze = [n for _, _, n in frasi]

    if not lunghezze:
        a.stat = None
        return a

    lunghe = [(r, f, n) for r, f, n in frasi if n >= FRASE_LUNGA]
    brevi = [(r, f, n) for r, f, n in frasi if n <= FRASE_BREVE]

    a.stat = {
        "parole": sum(lunghezze),
        "frasi": len(frasi),
        "media": statistics.mean(lunghezze),
        "mediana": statistics.median(lunghezze),
        "dev": statistics.pstdev(lunghezze),
        "pct_lunghe": 100 * len(lunghe) / len(frasi),
        "pct_brevi": 100 * len(brevi) / len(frasi),
        "paragrafi": len(paragrafi),
        "par_medio": statistics.mean([len(frasi_di([p])) for p in paragrafi]) if paragrafi else 0,
        "parole_par": sum(lunghezze) / len(paragrafi) if paragrafi else 0,
    }

    # 1. connettivi-stampella
    testo_piano = norm_accenti(" ".join(pulisci(t) for _, t in paragrafi).lower())
    trovati = []
    for c in cfg["connettivi"]:
        n = testo_piano.count(c)
        if n >= 3:
            trovati.append((c, n))
    trovati.sort(key=lambda x: -x[1])
    if trovati:
        a.nota("connettivi", f"{len(trovati)} connettivi ripetuti 3+ volte",
               [f"«{c}» × {n}" for c, n in trovati])
    a.stat["connettivi"] = sum(n for _, n in trovati)

    # 2. frasi che aprono con la negazione
    re_neg = re.compile(cfg["negazione_re"])
    neg = [(r, f) for r, f, _ in frasi if re_neg.match(f)]
    a.stat["negazioni"] = len(neg)
    a.stat["pct_neg"] = 100 * len(neg) / len(frasi)
    if len(neg) >= 5:
        a.nota("negazioni", f"{len(neg)} frasi aprono con la negazione ({a.stat['pct_neg']:.1f}%)",
               [f"riga {r}: {f[:90]}" for r, f in neg])

    # 3. chiusure di sottosezione con lo stesso schema
    re_chi = re.compile(cfg["chiusura_re"])
    chiusure, meccaniche = [], []
    for titolo, pars in sottosezioni.items():
        fr = frasi_di(pars[-1:]) if pars else []
        if not fr:
            continue
        r, f, _ = fr[-1]
        chiusure.append((titolo, r, f))
        if re_chi.search(f):
            meccaniche.append((titolo, r, f))
    a.stat["chiusure"] = len(chiusure)
    a.stat["pct_chiusure"] = 100 * len(meccaniche) / len(chiusure) if chiusure else 0
    if meccaniche:
        a.nota("chiusure",
               f"{len(meccaniche)} sottosezioni su {len(chiusure)} chiudono con lo schema "
               f"«due punti + non X ma Y» ({a.stat['pct_chiusure']:.0f}%)",
               [f"riga {r} ({t}): {f[:90]}" for t, r, f in meccaniche])

    # 4. n-grammi ricorrenti
    ng = ngrammi(frasi)
    if ng:
        a.nota("ricorrenze", f"{len(ng)} sequenze di 4 parole ripetute 3+ volte",
               [f"«{g}» × {c}" for g, c in ng])

    # 5. frasi lunghissime, da spezzare
    lunghissime = sorted(lunghe, key=lambda x: -x[2])[:20]
    if lunghissime and lunghissime[0][2] >= 60:
        a.nota("frasi lunghe", f"frase piu' lunga: {lunghissime[0][2]} parole",
               [f"riga {r} ({n} parole): {f[:110]}…" for r, f, n in lunghissime if n >= 55])

    # 6. riferimenti vaghi: «molti studiosi», «e' spesso letto», «chiunque abbia».
    # Vengono dalla prova di verifica della costruzione (Diagnosi/verifica-
    # costruzione.md): danno a un'affermazione l'aria di una fonte senza nominarne
    # nessuna. Qui si contano, perche' il rilievo e' meccanico; le due domande che
    # richiedono giudizio (contraddizioni interne, fonti senza contraddittorio)
    # restano alla lettura della fase 5.
    vaghi = []
    for riga, testo in paragrafi:
        piano = norm_accenti(pulisci(testo).lower())
        for espressione in cfg.get("vaghi", []):
            for m in re.finditer(espressione, piano):
                inizio = max(0, m.start() - 30)
                vaghi.append((riga, piano[inizio:m.end() + 40]))
    a.stat["vaghi"] = len(vaghi)
    if vaghi:
        a.nota("riferimenti vaghi",
               f"{len(vaghi)} riferimenti a un'autorita' che non viene nominata",
               [f"riga {r}: …{t}…" for r, t in vaghi])

    # 7. checklist del translationese, solo sull'edizione inglese
    if cfg.get("translationese"):
        analizza_translationese(a, paragrafi, frasi)

    return a


def scarto(v, rif):
    if rif is None:
        return ""
    d = v - rif
    return f" ({d:+.1f})" if abs(d) >= 0.05 else " (=)"


def stampa(analisi, cfg, riferimento, dettaglio, out):
    def p(s=""):
        out.append(s)

    validi = [a for a in analisi if a.stat]
    p("# Ritmo della prosa e tic ricorrenti")
    p()
    if not validi:
        p("Nessun volume analizzabile.")
        return

    rif = next((a for a in validi if a.book["n"] == riferimento), None) if riferimento else None

    p("Corpo narrativo soltanto: testata, Sommario, Testi di riferimento e sezioni")
    p("automatiche sono esclusi dal conteggio.")
    p()
    p("| Vol. | Titolo | Parole | Frasi | Parole/frase | Dev.st | ≥45 par. | ≤8 par. | Parole/parag. | Neg. iniz. | Connett. | Chius. mecc. | Rif. vaghi |")
    p("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a in validi:
        s = a.stat
        p(f"| {a.book['n']} | {a.book['title'].split(' — ')[0]} | {s['parole']} | {s['frasi']} | "
          f"{s['media']:.1f} | {s['dev']:.1f} | {s['pct_lunghe']:.0f}% | {s['pct_brevi']:.1f}% | "
          f"{s['parole_par']:.0f} | "
          f"{s['negazioni']} | {s['connettivi']} | {s['pct_chiusure']:.0f}% | {s.get('vaghi', 0)} |")
    p()

    def mediana(chiave):
        return statistics.median([a.stat[chiave] for a in validi])

    med = {k: mediana(k) for k in ("media", "dev", "pct_lunghe", "pct_brevi", "pct_neg", "pct_chiusure")}
    p(f"**Mediana della collana**: frase {med['media']:.1f} parole, dev.st {med['dev']:.1f}, "
      f"{med['pct_lunghe']:.0f}% di frasi ≥45 parole, {med['pct_brevi']:.1f}% ≤8 parole, "
      f"{med['pct_chiusure']:.0f}% di chiusure meccaniche.")
    if rif:
        s = rif.stat
        p(f"**Riferimento (vol. {rif.book['n']})**: frase {s['media']:.1f} parole, dev.st {s['dev']:.1f}, "
          f"{s['pct_lunghe']:.0f}% ≥45, {s['pct_brevi']:.1f}% ≤8.")
    p()

    # translationese: tabella a se', solo per la serie inglese
    tr = [a for a in validi if "tr_nom" in a.stat]
    if tr:
        p("## Translationese: sintomi del calco italiano → inglese")
        p()
        p("Tassi per mille parole, salvo dove indicato fra parentesi. Nessuno di questi")
        p("numeri e' un errore in se': servono a confrontare i volumi fra loro e a")
        p("produrre la lista dei punti da guardare. Checklist in English/Errancies.md.")
        p()
        p("| Vol. | Titolo | Nominalizz. | «we» | Connett. | Passivi | Attenuat. | "
          "Cognati | Raddoppi | Dom. finali | «matter of» |")
        p("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for a in tr:
            s = a.stat
            p(f"| {a.book['n']} | {a.book['title'].split(' — ')[0]} | "
              f"{s['tr_nom']:.1f} | {s['tr_noi']:.1f} | {s['tr_conn']:.1f} | "
              f"{s['tr_pass']:.1f} | {s['tr_att']:.1f} | "
              f"{s['tr_cognati']} | {s['tr_coppie']} | "
              f"{s['tr_domande']} ({s['tr_pct_domande']:.1f}%) | {s['tr_matter']} |")
        p()
        if len(tr) > 1:
            scarti = []
            for chiave, etichetta in (("tr_nom", "nominalizzazioni"), ("tr_noi", "«we» saggistico"),
                                      ("tr_conn", "connettivi da traduzione"),
                                      ("tr_pass", "passivi"), ("tr_att", "attenuativi")):
                ordinati = sorted(tr, key=lambda x: -x.stat[chiave])
                alto, basso = ordinati[0], ordinati[-1]
                if alto.stat[chiave] > 1 and alto.stat[chiave] >= basso.stat[chiave] * 1.35:
                    scarti.append(f"- **{etichetta}**: vol. {alto.book['n']} a "
                                  f"{alto.stat[chiave]:.1f} contro {basso.stat[chiave]:.1f} "
                                  f"del vol. {basso.book['n']}")
            if scarti:
                p("Scarti sensibili fra i volumi (il piu' alto almeno di un terzo sopra il piu' basso):")
                p()
                for s in scarti:
                    p(s)
                p()

    # volumi fuori scala
    fuori = []
    for a in validi:
        s, motivi = a.stat, []
        if s["media"] >= med["media"] + 3:
            motivi.append(f"frase media {s['media']:.1f} contro {med['media']:.1f}")
        if s["pct_lunghe"] >= med["pct_lunghe"] + 7:
            motivi.append(f"{s['pct_lunghe']:.0f}% di frasi lunghe contro {med['pct_lunghe']:.0f}%")
        if s["pct_brevi"] <= med["pct_brevi"] - 1.5:
            motivi.append(f"solo {s['pct_brevi']:.1f}% di frasi brevi contro {med['pct_brevi']:.1f}%")
        if s["pct_chiusure"] >= max(25, med["pct_chiusure"] + 10):
            motivi.append(f"{s['pct_chiusure']:.0f}% di chiusure meccaniche")
        if motivi:
            fuori.append((a, motivi))
    if fuori:
        p("## Volumi fuori scala")
        p()
        for a, motivi in sorted(fuori, key=lambda x: -len(x[1])):
            p(f"- **Vol. {a.book['n']} — {a.book['title']}**: " + "; ".join(motivi))
        p()

    # tic condivisi da piu' volumi
    comuni = Counter()
    for a in validi:
        for cat, _, det in a.rilievi:
            if cat == "connettivi":
                for d in det:
                    comuni[d.split("»")[0].strip("«")] += 1
    ricorrenti = [(c, n) for c, n in comuni.most_common() if n >= len(validi) // 2]
    if ricorrenti:
        p("## Connettivi-stampella comuni a meta' collana o piu'")
        p()
        for c, n in ricorrenti:
            p(f"- «{c}» in {n} volumi su {len(validi)}")
        p()

    p("## Dettaglio per volume")
    for a in analisi:
        p()
        p(f"### Vol. {a.book['n']} — {a.book['title']}")
        p()
        if not a.stat:
            p("File non trovato o senza corpo analizzabile.")
            continue
        s = a.stat
        rifv = rif.stat if rif and rif is not a else None
        p(f"Frase media **{s['media']:.1f}** parole{scarto(s['media'], rifv['media'] if rifv else None)}, "
          f"deviazione standard {s['dev']:.1f}, mediana {s['mediana']:.0f}. "
          f"Frasi ≥45 parole **{s['pct_lunghe']:.0f}%**, ≤8 parole **{s['pct_brevi']:.1f}%**. "
          f"Paragrafo medio {s['par_medio']:.1f} frasi / {s['parole_par']:.0f} parole "
          f"({s['paragrafi']} paragrafi).")
        if not a.rilievi:
            p()
            p("Nessun tic rilevato sopra soglia.")
            continue
        for cat, msg, det in a.rilievi:
            p()
            p(f"**{cat}** — {msg}")
            mostra = det if dettaglio else det[:MAX_ESEMPI]
            for d in mostra:
                p(f"- {d}")
            if not dettaglio and len(det) > MAX_ESEMPI:
                p(f"- … e altre {len(det) - MAX_ESEMPI} (usa --dettaglio)")


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
    target = [b for b in books if b["n"] == int(vol)] if vol else books
    if not target:
        print(f"Errore: volume {vol} non trovato", file=sys.stderr)
        sys.exit(1)

    rif = opt("--riferimento")
    analisi = [analizza(cfg, b) for b in (books if rif else target)]
    if rif and vol:
        analisi = [a for a in analisi if a.book["n"] in (int(vol), int(rif))]

    out = []
    stampa(analisi, cfg, int(rif) if rif else None, "--dettaglio" in argv, out)
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
