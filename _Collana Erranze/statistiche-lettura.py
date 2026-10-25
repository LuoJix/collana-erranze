#!/usr/bin/env python3
"""Legge i contatori pubblici di Internet Archive e Zenodo per tutti i volumi
delle due collane, salva la rilevazione con la data e scrive un rapporto con
una classificazione.

Uso:
    python3 statistiche-lettura.py            # rileva, salva, scrive il rapporto
    python3 statistiche-lettura.py --stampa   # rileva e stampa, senza salvare

Sola lettura: non serve nessun account e non si tocca nessun record.

Dove finisce:
    Diagnosi/Letture/storico.csv         una riga per volume per rilevazione
    Diagnosi/Letture/AAAA-MM-GG.md       il rapporto del giorno
Diagnosi resta nel repository privato: pubblica.py non la copia.

Perche' il ritmo e non il totale. I volumi sono usciti in momenti diversi, fra
agosto e ottobre 2026: un totale premia chi e' online da piu' tempo. La
classifica usa quindi gli accessi per settimana dal deposito. Il totale resta
in tabella, ma non decide l'ordine.

Che cosa conta come lettura. Su Internet Archive ogni accesso all'item conta,
e quasi sempre coincide con un download. Su Zenodo si contano a parte le visite
alla pagina e i download dei file: qui si sommano solo i download, perche' una
visita alla scheda non e' una lettura. Accessi = accessi IA + download Zenodo.

Due cautele che il rapporto ripete. I numeri sono piccoli e comprendono le
visite di controllo dell'autore e di Claude dopo ogni caricamento. E il
contatore di Internet Archive parte con alcuni giorni di ritardo: finche' non
e' attivo il volume compare a parte, fuori classifica, invece che ultimo.
"""

import csv
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "Diagnosi" / "Letture"
REGISTRI = (("it", "serie.json", "collana-erranze"), ("en", "series-en.json", "errancies"))
OGGI = dt.date.today()

# Soglie della classificazione per profilo, scelte sui dati di ottobre 2026.
# Sono convenzioni, non leggi: se i numeri crescono, vanno ritoccate.
SOGLIA_ACCELERA = 2.0   # ultima settimana almeno il doppio della media settimanale
MINIMO_ACCELERA = 3     # e almeno 3 accessi: con medie di 1-2 a settimana, 2 accessi sono rumore
SOGLIA_CITAZIONE = 0.25  # download Zenodo almeno un quarto degli accessi IA


def get(url):
    """curl e non urllib: il Python del Mac mini rifiuta alcuni certificati."""
    for _ in range(3):
        r = subprocess.run(["curl", "-s", "-m", "30", url], capture_output=True, text=True)
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(3)
    return {}


def data(s):
    return dt.date.fromisoformat(s[:10]) if s else None


def rileva():
    q = ("https://archive.org/advancedsearch.php?q=identifier%3Acollana-erranze-%2A"
         "+OR+identifier%3Aerrancies-%2A&fl%5B%5D=identifier&fl%5B%5D=addeddate"
         "&rows=200&output=json")
    docs = get(q).get("response", {}).get("docs", [])
    ia_ids = {d["identifier"]: data(d.get("addeddate")) for d in docs}
    viste = {}
    ids = sorted(ia_ids)
    for i in range(0, len(ids), 10):
        viste.update(get("https://be-api.us.archive.org/views/v1/short/" + ",".join(ids[i:i + 10])))

    righe = []
    for lang, registro, prefisso in REGISTRI:
        for b in json.load(open(BASE / registro))["books"]:
            n = b["n"]
            ia = next((i for i in ids if i.startswith(f"{prefisso}-{n:02d}-")), None)
            v = viste.get(ia, {}) if ia else {}
            z = b.get("zenodo", {}).get("deposit_id")
            zr = get(f"https://zenodo.org/api/records/{z}") if z else {}
            time.sleep(1.2)
            s = zr.get("stats", {})
            uscita = min(d for d in (ia_ids.get(ia), data(zr.get("created"))) if d) if (ia or zr) else None
            righe.append({
                "data": OGGI.isoformat(), "lingua": lang, "n": n,
                "titolo": b["title"].split(" — ")[0],
                "keywords": b.get("keywords", []),
                "ia": ia or "", "ia_attivo": bool(v.get("have_data")),
                "ia_totale": v.get("all_time") or 0, "ia_30": v.get("last_30day") or 0,
                "ia_7": v.get("last_7day") or 0,
                "z_visite": s.get("unique_views") or 0, "z_download": s.get("unique_downloads") or 0,
                "uscita": uscita.isoformat() if uscita else "",
            })
    return righe


def analizza(r):
    giorni = max(1, (OGGI - data(r["uscita"])).days) if r["uscita"] else 1
    settimane = giorni / 7
    accessi = r["ia_totale"] + r["z_download"]
    ritmo = accessi / settimane
    media_sett_ia = r["ia_totale"] / settimane if settimane else 0
    accelera = r["ia_7"] >= MINIMO_ACCELERA and media_sett_ia and r["ia_7"] / media_sett_ia >= SOGLIA_ACCELERA
    citazione = r["ia_totale"] and r["z_download"] / r["ia_totale"] >= SOGLIA_CITAZIONE
    profilo = ("in accelerazione" if accelera else
               "da citazione" if citazione else
               "di lettura")
    return {**r, "giorni": giorni, "accessi": accessi, "ritmo": round(ritmo, 2), "profilo": profilo}


def fasce(valori):
    """Quartili sul ritmo: alta, medio-alta, medio-bassa, bassa."""
    s = sorted(valori)
    q = lambda p: s[min(len(s) - 1, int(p * len(s)))]
    return q(0.25), q(0.5), q(0.75)


def fascia(x, soglie):
    q1, q2, q3 = soglie
    return "alta" if x >= q3 else "medio-alta" if x >= q2 else "medio-bassa" if x >= q1 else "bassa"


def precedente():
    f = OUT / "storico.csv"
    if not f.exists():
        return {}
    righe = list(csv.DictReader(open(f)))
    date = sorted({r["data"] for r in righe if r["data"] < OGGI.isoformat()})
    if not date:
        return {}
    return {(r["lingua"], int(r["n"])): r for r in righe if r["data"] == date[-1]} | {"_data": date[-1]}


def rapporto(righe, prima):
    attivi = [r for r in righe if r["ia_attivo"]]
    attesa = [r for r in righe if not r["ia_attivo"]]
    soglie = fasce([r["ritmo"] for r in attivi]) if attivi else (0, 0, 0)
    attivi.sort(key=lambda r: -r["ritmo"])
    L = []
    w = L.append
    w(f"# Letture al {OGGI.day} {['','gennaio','febbraio','marzo','aprile','maggio','giugno','luglio','agosto','settembre','ottobre','novembre','dicembre'][OGGI.month]} {OGGI.year}\n")
    w("Contatori pubblici di Internet Archive e Zenodo, letti da `statistiche-lettura.py`. "
      "**Accessi** = accessi a Internet Archive + download da Zenodo. **Ritmo** = accessi per settimana dal deposito. "
      "I numeri sono piccoli e comprendono le visite di controllo dell'autore e di Claude.\n")

    for lang, nome in (("it", "Collana Erranze"), ("en", "Errancies")):
        g = [r for r in righe if r["lingua"] == lang]
        w(f"- **{nome}**: {len(g)} volumi, {sum(r['ia_totale'] for r in g)} accessi a Internet Archive, "
          f"{sum(r['z_visite'] for r in g)} visite e {sum(r['z_download'] for r in g)} download su Zenodo.")
    w("")

    w("## Classifica per ritmo\n")
    w("| # | Vol. | Titolo | Ritmo | Fascia | Profilo | Accessi | IA ult. 7 gg | Zenodo vis./dl | Giorni online |")
    w("|---:|---|---|---:|---|---|---:|---:|---:|---:|")
    for i, r in enumerate(attivi, 1):
        sig = ("IT" if r["lingua"] == "it" else "EN") + f" {r['n']}"
        w(f"| {i} | {sig} | {r['titolo']} | {r['ritmo']:.1f} | {fascia(r['ritmo'], soglie)} | {r['profilo']} | "
          f"{r['accessi']} | {r['ia_7']} | {r['z_visite']}/{r['z_download']} | {r['giorni']} |")
    w("")
    if attesa:
        w("**Fuori classifica**, contatore di Internet Archive non ancora attivo: "
          + ", ".join(f"{'IT' if r['lingua']=='it' else 'EN'} {r['n']} *{r['titolo']}* (Zenodo {r['z_visite']}/{r['z_download']})" for r in attesa) + ".\n")

    w("## Profili\n")
    for p, spiega in (("in accelerazione", f"nell'ultima settimana almeno {MINIMO_ACCELERA} accessi e almeno il doppio della media settimanale: qualcosa l'ha fatto scoprire da poco"),
                      ("da citazione", f"i download da Zenodo sono almeno un quarto degli accessi a Internet Archive: chi lo prende cerca un DOI da citare"),
                      ("di lettura", "il pubblico arriva da Internet Archive, dove si legge e si scarica")):
        g = [r for r in attivi if r["profilo"] == p]
        w(f"- **{p.capitalize()}** ({len(g)}): {spiega}."
          + (" " + ", ".join(f"*{r['titolo']}*" for r in g) + "." if g else ""))
    w("")

    w("## Per collana e per periodo di uscita\n")
    w("Ritmo medio dei volumi in classifica. Le parole chiave del registro non servono a classificare i temi: "
      "mescolano argomenti e nomi di autori.\n")
    w("| Gruppo | Volumi | Ritmo medio |")
    w("|---|---:|---:|")
    gruppi = [("Collana Erranze", [r for r in attivi if r["lingua"] == "it"]),
              ("Errancies", [r for r in attivi if r["lingua"] == "en"]),
              ("Online da oltre 8 settimane", [r for r in attivi if r["giorni"] > 56]),
              ("Online da 8 settimane o meno", [r for r in attivi if r["giorni"] <= 56])]
    for nome, g in gruppi:
        if g:
            w(f"| {nome} | {len(g)} | {sum(r['ritmo'] for r in g) / len(g):.1f} |")
    w("")

    w("## Rispetto alla rilevazione precedente\n")
    if not prima:
        w("Prima rilevazione: il confronto comincia dalla prossima.")
    else:
        w(f"Rilevazione precedente: {prima['_data']}.\n")
        cresc = []
        for r in righe:
            p = prima.get((r["lingua"], r["n"]))
            if p:
                d = r["accessi"] - (int(p["ia_totale"]) + int(p["z_download"]))
                if d:
                    cresc.append((d, r))
        cresc.sort(key=lambda x: -x[0])
        if cresc:
            w("| Vol. | Titolo | Accessi in più |")
            w("|---|---|---:|")
            for d, r in cresc:
                w(f"| {'IT' if r['lingua']=='it' else 'EN'} {r['n']} | {r['titolo']} | {d:+d} |")
        else:
            w("Nessun accesso nuovo.")
    w("")
    w(f"Fasce: quartili del ritmo fra i volumi in classifica (soglie {soglie[0]:.1f} / {soglie[1]:.1f} / {soglie[2]:.1f}).")
    return "\n".join(L) + "\n"


def main():
    righe = [analizza(r) for r in rileva()]
    prima = precedente()
    testo = rapporto(righe, prima)
    if "--stampa" in sys.argv:
        print(testo)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    campi = ["data", "lingua", "n", "titolo", "ia", "ia_attivo", "ia_totale", "ia_30", "ia_7",
             "z_visite", "z_download", "uscita", "giorni", "accessi", "ritmo", "profilo"]
    f = OUT / "storico.csv"
    vecchie = [r for r in csv.DictReader(open(f))] if f.exists() else []
    vecchie = [r for r in vecchie if r["data"] != OGGI.isoformat()]  # una rilevazione al giorno
    with open(f, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=campi, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(vecchie)
        wr.writerows(righe)
    (OUT / f"{OGGI.isoformat()}.md").write_text(testo)
    print(f"  ✓ {len(righe)} volumi → {f.relative_to(BASE)} e Diagnosi/Letture/{OGGI.isoformat()}.md")


if __name__ == "__main__":
    main()
