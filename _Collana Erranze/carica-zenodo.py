#!/usr/bin/env python3
"""Deposita i volumi su Zenodo prendendo i metadati dai registri.

Prima volta:
    crea un token su https://sandbox.zenodo.org/account/settings/applications/tokens
    (permessi: deposit:write e deposit:actions) e salvalo in
        ~/.config/zenodo/token-sandbox
    Per il deposito vero, token creato su https://zenodo.org e salvato in
        ~/.config/zenodo/token
    In alternativa: variabili ZENODO_SANDBOX_TOKEN e ZENODO_TOKEN.

Uso:
    python3 carica-zenodo.py --prova --tutti                  # non tocca la rete: mostra i metadati
    python3 carica-zenodo.py --sandbox --volume 14            # bozza sulla sandbox
    python3 carica-zenodo.py --sandbox --tutti                # prova generale, DOI finti
    python3 carica-zenodo.py --sandbox --tutti --pubblica     # prova generale fino in fondo
    python3 carica-zenodo.py --volume 14                      # bozza vera, da pubblicare a mano
    python3 carica-zenodo.py --volume 14 --pubblica           # deposito definitivo
    python3 carica-zenodo.py --volume 14 --nuova-versione     # dopo una correzione

Perche' la bozza e' il default: su Zenodo un DOI non si cancella. Si puo'
chiedere che il file venga oscurato, ma il record resta e resta citabile. Quindi
lo script si ferma un passo prima: crea il record, carica i file, e lascia a te
il clic che lo rende definitivo. --pubblica salta quel passo di proposito.

Perche' la sandbox: sandbox.zenodo.org e' una copia di Zenodo che rilascia DOI
finti. Serve a vedere il record finito, con la sua pagina e i suoi file, prima di
impegnare quello vero. I record della sandbox non contano e vengono ripuliti.

Ordine: prima l'italiano, poi l'inglese. I volumi di Errancies dichiarano
«is derived from» verso il DOI del volume italiano di origine, e quel DOI deve
gia' esistere. Se manca, lo script si ferma e dice quale volume depositare prima.

Dopo una correzione il record pubblicato non si tocca: si aggiunge una versione
con --nuova-versione, che eredita il concept DOI e riceve un DOI proprio. Il DOI
vecchio finisce in "precedenti" e continua a puntare al testo vecchio, che resta
scaricabile: e' il modo in cui Zenodo tiene insieme la citabilita' e la
correzione. Lo script non sa dire da solo se una correzione c'e' stata davvero:
l'epub cambia byte a ogni ricompilazione, anche a testo identico, quindi la
decisione di versionare resta di chi lancia il comando.

I DOI tornano nel registro (serie.json, series-en.json) sotto la chiave "zenodo",
o "zenodo_sandbox" per le prove: senza, al deposito successivo si ricomincia a
cercarli a mano, e la relazione fra edizione inglese e italiana non si compila.

publication_date e' l'anno di copyright letto dalla testata del .md, che e' la
data dell'opera. La data del file epub non va bene: cambia a ogni ricompilazione.
"""
import html
import io
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)
LICENZA = "cc-by-nc-sa-4.0"

LANGS = {
    "it": {"registry": "serie.json", "root": "", "serie": "Collana Erranze", "iso": "ita"},
    "en": {"registry": "series-en.json", "root": "English", "serie": "Errancies", "iso": "eng"},
}


def token(sandbox):
    var = "ZENODO_SANDBOX_TOKEN" if sandbox else "ZENODO_TOKEN"
    if os.environ.get(var):
        return os.environ[var].strip()
    nome = "token-sandbox" if sandbox else "token"
    p = os.path.expanduser(f"~/.config/zenodo/{nome}")
    if os.path.exists(p):
        return io.open(p, encoding="utf-8").read().strip()
    sys.exit(f"Manca il token: valorizza {var} oppure scrivilo in {p}")


def cartella_di(cfg, book):
    return os.path.join(BASE, cfg["root"], book["folder"]) if cfg["root"] \
        else os.path.join(BASE, book["folder"])


def anno_copyright(cartella, book):
    """L'anno di copyright dalla testata del .md.

    Non la data del file epub: quella cambia a ogni ricompilazione, e un volume
    uscito a marzo si ritroverebbe depositato ad agosto solo perche' e' stato
    rigenerato. Zenodo accetta l'anno secco, ed e' l'anno dell'opera."""
    md = os.path.join(cartella, book["file"] + ".md")
    m = re.search(r"\*©\s*(\d{4})", io.open(md, encoding="utf-8").read(1500))
    if not m:
        sys.exit(f"Manca la riga di copyright nella testata di {book['file']}.md")
    return m.group(1)


def doi_origine(book, chiave):
    """Per un volume inglese, il DOI dell'italiano da cui deriva.

    Nel registro inglese "original" e' un oggetto {title, n}: si cerca per
    numero, che non cambia, e non per titolo, che nei due registri puo' essere
    scritto con maiuscole diverse."""
    with io.open(os.path.join(SCRIPT_DIR, "serie.json"), encoding="utf-8") as f:
        italiani = json.load(f)["books"]
    rif = book.get("original") or {}
    n_orig = rif.get("n") if isinstance(rif, dict) else None
    orig = next((b for b in italiani if b["n"] == n_orig), None)
    if orig is None:
        return None, f"nessun volume italiano corrisponde a «{rif}»"
    dep = orig.get(chiave) or {}
    if not dep.get("doi"):
        return None, f"il vol. {orig['n']} italiano non e' ancora depositato: depositalo prima"
    return dep["doi"], None


def prepara(cfg, book, chiave):
    cartella = cartella_di(cfg, book)
    files = [p for p in (os.path.join(cartella, book["file"] + ".epub"),
                         os.path.join(cartella, book["file"] + " - Interno.pdf"))
             if os.path.exists(p)]
    meta = {
        "upload_type": "publication",
        "publication_type": "book",
        "title": book["title"],
        "creators": [{"name": "Martini, Giovanni"}],
        "description": "<p>" + html.escape(book.get("blurb", "")).replace("\n\n", "</p><p>") + "</p>",
        "access_right": "open",
        "license": LICENZA,
        "publication_date": anno_copyright(cartella, book),
        "language": cfg["iso"],
        "keywords": book.get("keywords", []),
        "version": "1.0",
        "notes": f"{cfg['serie']}, volume {book['n']}",
    }
    errore = None
    if book.get("original"):
        doi, errore = doi_origine(book, chiave)
        if doi:
            meta["related_identifiers"] = [{"relation": "isDerivedFrom", "identifier": doi,
                                            "resource_type": "publication-book"}]
    return files, meta, errore


def salva(cfg, book, chiave, dati):
    """Riscrive il registro aggiornando un solo volume."""
    p = os.path.join(SCRIPT_DIR, cfg["registry"])
    with io.open(p, encoding="utf-8") as f:
        reg = json.load(f)
    for b in reg["books"]:
        if b["n"] == book["n"]:
            b[chiave] = dati
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def verifica_stato(sess, api, deposit_id, tentativi=5):
    """Che cosa risulta a Zenodo, al di la' di quello che ha risposto."""
    for i in range(tentativi):
        try:
            r = sess.get(f"{api}/deposit/depositions/{deposit_id}", timeout=90)
            if r.status_code == 200:
                d = r.json()
                return d.get("state"), d.get("doi"), d.get("conceptdoi")
        except Exception:                                       # noqa: BLE001
            pass
        time.sleep(10 * (i + 1))
    return None, None, None


def pubblicazione(sess, api, deposit_id, dati):
    """Il passo che non si annulla: da qui in poi il DOI esiste e resta.

    Un errore qui non prova che la pubblicazione non sia avvenuta: sotto carico
    Zenodo risponde 504 dopo aver gia' fatto il lavoro, e fidarsi della risposta
    significa segnare come bozza un volume che invece e' pubblico, con il DOI
    perso dal registro. Quindi, dopo un errore, si va a rileggere lo stato."""
    try:
        r = sess.post(f"{api}/deposit/depositions/{deposit_id}/actions/publish", timeout=120)
        codice, corpo = r.status_code, r.text[:200]
    except Exception as e:                                      # noqa: BLE001
        codice, corpo, r = None, f"{type(e).__name__}: {e}", None
    if codice not in (200, 202):
        stato, doi, concept = verifica_stato(sess, api, deposit_id)
        if stato == "done" and doi:
            dati.update({"doi": doi, "concept_doi": concept, "pubblicato": True,
                         "url": f"https://zenodo.org/records/{deposit_id}"})
            print(f"      ! risposta {codice} ({corpo[:60].strip()}), ma il record risulta"
                  f" pubblicato: {doi}")
            return True
        print(f"      ✗ pubblicazione fallita ({codice}): {corpo}")
        print(f"      la bozza resta aperta: {dati['url']}")
        return False
    j = r.json()
    dati.update({"doi": j.get("doi"), "concept_doi": j.get("conceptdoi"),
                 "url": j["links"].get("record_html", dati["url"]), "pubblicato": True})
    print(f"      ✓ pubblicato: {dati['doi']}")
    return True


def prossima_versione(attuale):
    try:
        maggiore, minore = attuale.split(".")[:2]
        return f"{maggiore}.{int(minore) + 1}"
    except (ValueError, AttributeError):
        return "1.1"


def nuova_versione(sess, api, cfg, book, chiave, meta, files, pubblica):
    """Aggiunge una versione a un volume gia' pubblicato.

    La bozza della nuova versione eredita i file della precedente: vanno tolti,
    altrimenti la versione nuova esce con dentro anche l'epub vecchio."""
    fatto = book[chiave]
    bozza = fatto.get("bozza")
    if not bozza:
        r = sess.post(f"{api}/deposit/depositions/{fatto['deposit_id']}/actions/newversion")
        if r.status_code not in (200, 201):
            print(f"      ✗ nuova versione non creata ({r.status_code}): {r.text[:200]}")
            return
        nuovo_id = int(r.json()["links"]["latest_draft"].rstrip("/").split("/")[-1])
        bozza = {"deposit_id": nuovo_id, "url": f"{api.rsplit('/api', 1)[0]}/deposit/{nuovo_id}"}
        fatto["bozza"] = bozza
        salva(cfg, book, chiave, fatto)
        print(f"      versione nuova aperta a partire da {fatto['doi']}")

    d = sess.get(f"{api}/deposit/depositions/{bozza['deposit_id']}").json()
    for f_ in d.get("files", []):
        sess.delete(f"{api}/deposit/depositions/{bozza['deposit_id']}/files/{f_['id']}")
    for percorso in files:
        with io.open(percorso, "rb") as fh:
            u = sess.put(f"{d['links']['bucket']}/{os.path.basename(percorso)}", data=fh)
        if u.status_code not in (200, 201):
            print(f"      ✗ upload di {os.path.basename(percorso)} fallito ({u.status_code})")
            return

    meta["version"] = prossima_versione(fatto.get("versione", "1.0"))
    m = sess.put(f"{api}/deposit/depositions/{bozza['deposit_id']}", json={"metadata": meta})
    if m.status_code != 200:
        print(f"      ✗ metadati non aggiornati ({m.status_code}): {m.text[:200]}")
        return

    if not pubblica:
        print(f"      ✓ versione {meta['version']} pronta da rivedere: {bozza['url']}")
        return
    dati = {"deposit_id": bozza["deposit_id"], "url": bozza["url"], "pubblicato": False}
    if pubblicazione(sess, api, bozza["deposit_id"], dati):
        dati["versione"] = meta["version"]
        dati["concept_doi"] = dati.get("concept_doi") or fatto.get("concept_doi")
        dati["precedenti"] = (fatto.get("precedenti") or []) + [fatto["doi"]]
        salva(cfg, book, chiave, dati)


def main():
    argv = sys.argv[1:]

    def opt(nome, default=None):
        if nome in argv:
            i = argv.index(nome)
            return argv[i + 1] if i + 1 < len(argv) else default
        return default

    prova = "--prova" in argv
    sandbox = "--sandbox" in argv
    pubblica = "--pubblica" in argv
    versionare = "--nuova-versione" in argv
    lang = opt("--lang", "it")
    vol = opt("--volume")
    cfg = LANGS[lang]
    chiave = "zenodo_sandbox" if sandbox else "zenodo"
    api = "https://sandbox.zenodo.org/api" if sandbox else "https://zenodo.org/api"

    with io.open(os.path.join(SCRIPT_DIR, cfg["registry"]), encoding="utf-8") as f:
        books = json.load(f)["books"]
    if vol:
        books = [b for b in books if b["n"] == int(vol)]
    elif "--tutti" not in argv:
        sys.exit("Serve --volume N oppure --tutti (e --prova per vedere senza depositare).")

    if not prova:
        import requests
        sess = requests.Session()
        sess.params = {"access_token": token(sandbox)}
        dove = "SANDBOX (DOI finti)" if sandbox else "ZENODO VERO"
        print(f"Deposito su {dove} — {'pubblicazione immediata' if pubblica else 'bozze da rivedere'}")

    for book in books:
        files, meta, errore = prepara(cfg, book, chiave)
        print(f"\n[{book['n']:>2}] {book['title'][:60]}")
        if errore:
            print(f"      ✗ {errore}, salto")
            continue
        for f_ in files:
            print(f"      {os.path.basename(f_)}  ({round(os.path.getsize(f_)/1024)} KB)")
        if prova:
            print("      metadati:", json.dumps(meta, ensure_ascii=False)[:400], "…")
            continue
        fatto = book.get(chiave) or {}
        if fatto.get("pubblicato"):
            if versionare:
                nuova_versione(sess, api, cfg, book, chiave, meta, files, pubblica)
            else:
                print(f"      gia' depositato: {fatto.get('doi')}"
                      " (per una correzione serve --nuova-versione)")
            continue
        if versionare:
            print("      non ancora depositato: prima il deposito normale, poi le versioni")
            continue
        if fatto.get("deposit_id"):
            # bozza gia' aperta da un giro precedente: non se ne apre una seconda,
            # si pubblica quella se e' il momento, altrimenti la si lascia dov'e'.
            if pubblica:
                print(f"      bozza gia' aperta, la pubblico: {fatto['url']}")
                if pubblicazione(sess, api, fatto["deposit_id"], fatto):
                    salva(cfg, book, chiave, fatto)
            else:
                print(f"      bozza gia' aperta, la lascio: {fatto['url']}")
            continue

        r = sess.post(f"{api}/deposit/depositions", json={"metadata": meta})
        if r.status_code not in (200, 201):
            print(f"      ✗ creazione fallita ({r.status_code}): {r.text[:400]}")
            continue
        dep = r.json()
        bucket = dep["links"]["bucket"]
        caricati = True
        for f_ in files:
            with io.open(f_, "rb") as fh:
                u = sess.put(f"{bucket}/{os.path.basename(f_)}", data=fh)
            if u.status_code not in (200, 201):
                print(f"      ✗ upload di {os.path.basename(f_)} fallito ({u.status_code})")
                caricati = False
        if not caricati:
            print(f"      bozza incompleta, resta aperta: {dep['links']['html']}")
            continue

        dati = {"deposit_id": dep["id"], "url": dep["links"]["html"], "pubblicato": False}
        riservato = dep.get("metadata", {}).get("prereserve_doi", {})
        if riservato.get("doi"):
            dati["doi_riservato"] = riservato["doi"]

        if pubblica:
            pubblicazione(sess, api, dep["id"], dati)
        else:
            print(f"      ✓ bozza pronta da rivedere: {dati['url']}")
        salva(cfg, book, chiave, dati)
        time.sleep(2)


if __name__ == "__main__":
    main()
