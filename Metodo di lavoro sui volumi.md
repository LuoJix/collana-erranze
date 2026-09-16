# Metodo di lavoro sui volumi della Collana Erranze

Flusso in 8 fasi per costruire un volume, con il modello Claude più adatto a ciascuna. La distinzione chiave non è "ricerca contro scrittura", ma "raccolta di materiale grezzo contro tutto ciò che richiede un giudizio strutturale o letterario": l'Indice, per esempio, è già architettura del libro, non ricerca, e va trattato come tale.

## 1. Tema e titolo — Opus

Scelta del tema, verifica su Amazon/web che il titolo non duplichi libri già esistenti, creazione delle cartelle di lavoro (Bozze/Copertina, Bozze/Note, Bozze/Versioni).

## 2. Indice — Opus

Scaletta di Parti e sottosezioni, arco tematico che le lega, collocazione degli autori e delle opere. Richiede lo stesso giudizio letterario della scrittura vera e propria: un errore nell'impalcatura iniziale costa più caro da correggere dopo di quanto costerebbe evitarlo all'inizio.

## 3. Ricerca bibliografica — Sonnet

Prima Temp/, dove l'autore deposita i testi già convertiti; la Calibre Library solo su sua approvazione, caso per caso, e in quel caso conversione degli ebook con `ebook-convert`; il web per ultimo, solo se la fonte non è disponibile altrove. Lettura diretta del testo, citazioni verificate ed estratte sul testo primario. Un file di note per Parte in Bozze/Note/. Compito meccanico e ripetitivo.

## 4. Stesura — Opus

Prologo, poi Parte per Parte, poi Epilogo. Sempre scritta a mano nel filo conversazionale principale, mai delegata a un sub-agente: ogni paragrafo deve conoscere tutto ciò che è già stato scritto nel libro. Segue lo standard della collana (niente trattino lungo nel corpo, citazioni fra guillemets, gerarchia dei titoli a due livelli, bibliografia solo in "Testi di riferimento").

## 5. Verifica del tono — Opus

A stesura completa, controllo dei tic da scrittura automatica per conteggio di frequenza (frasi fatte ripetute, costrutti a effetto, chiusure troppo simili fra loro), confrontato contro un volume già pubblicato come riferimento di ritmo naturale.

## 6. Espansioni successive — Sonnet + Opus in ciclo

Ogni volta che si aggiunge un nuovo autore o un nuovo collegamento: ricerca con Sonnet, verifica con l'autore se il collegamento è sostanziale prima di scrivere, stesura del nuovo passaggio con Opus, aggiornamento di bibliografia e note di ricerca in coda.

## 7. Revisione puntuale — Sonnet per verificare, Opus per riformulare

Osservazioni puntuali (un termine da spiegare, una frase poco chiara, un dubbio filologico): la verifica del fatto è meccanica, la riformulazione della frase è di nuovo giudizio letterario.

## 8. Calibrazione della densità — Opus

Dare respiro alla prosa esistente senza aggiungere contenuto nuovo: più ragionamento di collegamento fra le citazioni, transizioni esplicite, pause riflessive. Puro giudizio di ritmo.

## 9. Pubblicazione definitiva — Sonnet

Numero di volume nella testata (il placeholder `[N]` non si sostituisce da solo), registrazione in `_Collana Erranze/serie.json`, `python3 aggiorna-collana.py --volume [N]` per generare "Nella stessa collana", "L'autore" e l'epub, verifica che sia stata generata anche `cover.jpg` oltre a `cover.png`, eventuale `genera-stampa.py` per il PDF di stampa. Tutto script-driven, nessun giudizio editoriale richiesto.
