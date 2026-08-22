# L'edizione a stampa

Come è fatto il cartaceo delle due collane, e perché è fatto così. Vale per
*Collana Erranze* e per *Errancies*: la pagina è condivisa di proposito, e le
differenze fra le due serie riguardano lingua e contenuto, non l'impaginazione.

Lo produce `genera-stampa.py`, che genera due PDF per volume, l'interno in
formato 6×9" e la copertina *wrap* con dorso calcolato sul numero di pagine, e
li copia in `Progetti stampa/` (`Progetti stampa/English/` per gli inglesi).

```bash
cd "_Collana Erranze"
python3 genera-stampa.py --volume 14
python3 genera-stampa.py --lang en --volume 3
python3 genera-stampa.py --tutti
```

## Il front matter

Tre pagine, in quest'ordine: frontespizio, copyright, sommario. I salti fra le
tre **non hanno bisogno di regole esplicite**: le pagine con nome
(`page: front` per le prime due, `page: toc` per il sommario) li impongono da
sé. Un `page-break-after: always` aggiunto per «renderli deterministici» si è
rivelato un no-op, ed è stato tolto: prima di irrobustire una regola conviene
verificare che il problema esista.

**Le pagine bianche sono mute.** I capitoli aprono su pagina destra
(`h2.chapter-open { page-break-before: right }`), quindi prima di molti di essi
cade una bianca. È tipografia corretta. Non lo era che quelle bianche
portassero testatina e numero di pagina: le silenzia
`@page :blank { @top-center { content: none } @bottom-center { content: none } }`.
Il difetto è rimasto invisibile a lungo perché una pagina quasi vuota, in un PDF
che si scorre a schermo, non si guarda.

## La pagina del copyright

È il punto in cui questo file esiste, perché ogni sua scelta è una risposta a
un difetto visto in pagina.

**È ancorata in basso con `padding-top: 3.2in`.** Era `4in`. Su una pagina alta
9 pollici con margini da 1 restano 7 pollici utili, quindi 4 di padding ne
lasciavano 3 al blocco, che ne occupava quasi altrettanti: sul vol. 3 inglese
l'ultima riga, «First edition: 2026», è finita da sola sulla pagina successiva.
A 3,2 pollici il margine è di circa quattro righe. Non è una soluzione
definitiva, è un cuscinetto: **se un giorno il blocco cresce ancora, la pagina
va ripensata, non il padding riridotto.**

**È a bandiera a destra e senza sillabazione** (`text-align: left`,
`hyphens: none`). È la convenzione tipografica delle pagine di copyright, e qui
risolve due cose insieme: gli spazi dilatati che il testo giustificato apriva
attorno al titolo italiano in corsivo del colophon, che è lungo, e le
sillabazioni brutte a fine riga («consist-ency»).

**Non porta l'ISBN.** C'era una riga con il segnaposto «ISBN: [assegnato in
fase di pubblicazione su KDP]», cablata nello script e mai sostituita da
nessuno: finiva stampata così. KDP stampa comunque l'ISBN nel codice a barre in
quarta di copertina, quindi la riga interna era una convenzione dell'editoria
commerciale, non un obbligo. Toglierla elimina anche il rischio che il
segnaposto sfugga. Se un giorno servisse il numero vero, la strada è un campo
`isbn` nei registri, non un segnaposto nel codice.

**La riga sull'uso dell'AI dice cose diverse nelle due collane**, perché
diverso è il lavoro. Vedi la sezione 7 di `English/Errancies.md`. La stessa
dichiarazione sta anche in fondo alla testata del `.md`, e quindi nell'epub, ma
per un'altra strada: là la inserisce `aggiorna-collana.py` dalle costanti
`AI_IT` e `AI_EN`. **Se cambia una formula vanno cambiati tutti e due gli
script**, altrimenti cartaceo ed ebook dello stesso volume dichiarano cose
diverse.

## La carta, e perché il dorso resta calcolato sulla crema

Su KDP le due collane sono ordinate in **carta di pastalegno** (scelta del 16
agosto 2026). È ammessa per tutti i formati con interno in bianco e nero, quindi
anche per il 6×9", è disponibile su Amazon.it e sugli altri tredici marketplace
che servono, costa circa il 5% in meno a pagina, ed è più opaca: per volumi di
solo testo è la carta giusta. Il prezzo lo paga in durata, perché la pastalegno
ingiallisce prima di una carta senza lignina. Per una collana senza scopo di
lucro, in cui il cartaceo serve soprattutto a rendere possibili le copie
d'autore, è uno scambio che conviene.

**`PAPER = "cream"` in `genera-stampa.py` non va toccato.** È il fattore con cui
si calcola il dorso (0,0025 pollici per pagina), non una dichiarazione di quale
carta si ordina, e KDP chiede di rivedere il dorso solo **oltre le 350 pagine**
(crema) **o le 525** (bianca). Il volume più lungo della collana ne ha 119, il
più corto 35: siamo lontanissimi dalla soglia, e le 46 copertine già generate
sono valide così come sono. Rimpiazzare quel fattore con uno «da pastalegno»
cambierebbe il dorso di tutti e 23 i volumi, obbligherebbe a rigenerare e
ricaricare ogni copertina, e non correggerebbe niente.

## Dopo ogni rigenerazione: KDP

`Diagnosi/da-ricaricare.txt` tiene l'elenco dei volumi da ricaricare, con
numero di pagine e larghezza del dorso. **Va rifatto a ogni giro di
rigenerazione**, perché le date di modifica dei file vengono azzerate e non
dicono più che cosa è cambiato.

**Su KDP resta solo la scheda cartacea.** Le schede Kindle sono state eliminate
il 16 agosto 2026: l'epub è libero e gratuito, e distribuirlo dentro un negozio
non serviva alla collana. Un aggiornamento dell'epub quindi non comporta più
nessun caricamento su KDP, e i cataloghi dove l'epub circola vanno aggiornati
per conto loro.

Quando cambia la paginazione cambia il dorso: per il cartaceo **va ricaricata
anche la copertina**, non solo l'interno. È l'errore più facile da fare, perché
l'interno è il file che si è appena modificato e la copertina sembra
indipendente.
