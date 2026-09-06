# Collana Erranze

Sorgenti dei saggi di Giovanni Martini: il testo di ogni volume in
Markdown e gli script che ne generano l'ebook e l'edizione a stampa.

I libri sono gratuiti. Gli ebook stanno su Zenodo, il cartaceo su Amazon;
qui c'e' il testo da cui nascono, per chi voglia citarlo, correggerlo,
rimpaginarlo o tradurlo.

## I volumi

- **1. Il Golem — Argilla e Parola** — [ebook](https://zenodo.org/record/22010649)
- **2. Abitare la Soglia — Una cartografia della coscienza** — [ebook](https://zenodo.org/record/22010653)
- **3. Errare — Mito e Spazio del Labirinto** — [ebook](https://zenodo.org/record/22010655)
- **4. Il Luogo Comune — Viaggiare nell'Epoca della Sua Riproducibilità** — [ebook](https://zenodo.org/record/22010659)
- **5. Causalità e Sincronicità — Una problematizzazione senza tesi** — [ebook](https://zenodo.org/record/22010661)
- **6. Vendere il Cielo — La Pubblicità come Paesaggio Totale** — [ebook](https://zenodo.org/records/22010664)
- **7. La Natura non Esiste — Una storia culturale dell'ambiente** — [ebook](https://zenodo.org/records/22010666)
- **8. La Piazza Privata — Media dal basso, proprietà dall'alto** — [ebook](https://zenodo.org/records/22010670)
- **9. Il Sudore della Fronte — Una storia culturale del lavoro** — [ebook](https://zenodo.org/record/22010672)
- **10. I Parenti Poveri — Storia culturale e scientifica dei Neandertal** — [ebook](https://zenodo.org/records/22010674)
- **11. La Creatura Imperfetta — Umanesimo, Transumanesimo, Postumanesimo** — [ebook](https://zenodo.org/records/22010676)
- **12. Il Caso Abolito — La progettazione dell'autenticità** — [ebook](https://zenodo.org/record/22010678)
- **13. Utopia e Distopia — La Politica del Mondo (Im)Perfetto** — [ebook](https://zenodo.org/records/22010680)
- **14. La Soglia della Cura — Destino, colpa, luogo, classe: chi decide di che cosa ci ammaliamo** — [ebook](https://zenodo.org/record/22010683)
- **15. La Stanza di Pascal — Silenzio, Solitudine, Rumore, Compagnia** — [ebook](https://zenodo.org/record/22010685)
- **16. Il Trono Vuoto — Perché il Potere ha Bisogno di Sudditi** — [ebook](https://zenodo.org/record/22010687)
- **17. Il Futuro Non Vota — Nostalgia, demografia e la rinuncia italiana all'innovazione** — [ebook](https://zenodo.org/record/22010690)
- **18. Persone e Personaggi — Autenticità e Falsificazione dell'Io** — [ebook](https://zenodo.org/record/22010694)
- **19. Divi e Divismo — I Quindici Minuti di Celebrità** — [ebook](https://zenodo.org/record/22010696)
- **20. Le Forme del Tempo — Lineare, circolare, a loop** — [ebook](https://zenodo.org/record/22010698)
- **21. Chi Chiami Fratello — L'unità di base e chi la misura** — [ebook](https://zenodo.org/record/22283708)

## Errancies (edizione inglese)

Riscritture d'autore, non traduzioni di servizio.

- **1. The Golem — Clay and Word** — [ebook](https://zenodo.org/record/22011130)
- **2. Nature Does Not Exist — A Cultural History of the Environment** — [ebook](https://zenodo.org/record/22011138)
- **3. The Threshold of Care — Fate, Blame, Place, Class** — [ebook](https://zenodo.org/record/22011140)

## Com'e' fatto

- `Completati/` e `English/` — un volume per cartella, il testo definitivo in `.md`
- `_Collana Erranze/` — i registri (`serie.json`, `series-en.json`) e gli script
- `Metodo di lavoro sui volumi.md`, `_Collana Erranze/stampa.md` — lo standard editoriale

Epub, PDF e copertine non stanno qui: sono prodotti derivati e si
rigenerano dagli script.

```bash
cd "_Collana Erranze"
python3 aggiorna-collana.py --volume 1     # testo + epub
python3 genera-stampa.py --volume 1        # interno e copertina per la stampa
python3 genera-copertina.py --folder "..." # copertina dell'ebook
```

## Licenze

I testi sono sotto [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.it):
si possono copiare e adattare, citando l'autore, senza scopo di lucro e
condividendo allo stesso modo. Vedi `LICENSE`.

Gli script sono sotto licenza MIT. Vedi `LICENSE-CODE`.

*Aggiornato al 6 settembre 2026.*
