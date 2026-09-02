# Immobiliare La Sacra — Carousel Engine

Modulo di Open Social Scheduler per trasformare il link di un immobile pubblicato su `lasacraimmobiliare.it` in una campagna social multi-angolo.

## Flusso

1. Avvia `AVVIA_LA_SACRA.bat`.
2. Si apre `http://127.0.0.1:5055`.
3. Incolla il link dell'immobile.
4. Il motore legge la pagina lato server, quindi non dipende dal CORS del browser.
5. Recupera esclusivamente le immagini reali presenti nella scheda Shopify.
6. Legge dal sito La Sacra riferimenti cromatici e font disponibili nel tema.
7. Produce 12 angoli comunicativi, ciascuno come carosello.
8. `SCARICA TUTTI I PNG` esporta il pacchetto completo in ZIP.

## Regole editoriali

- niente immagini stock;
- niente immagini generate al posto delle foto dell'immobile;
- le fotografie arrivano sempre dall'URL dell'annuncio;
- foto protagonista e copy breve;
- stile Immobiliare La Sacra, non Real Media Pro/F1 Immobiliare;
- dati tecnici e confronti di mercato devono essere verificabili;
- gli aspetti potenzialmente penalizzanti vengono comunicati con trasparenza.

## Primo test configurato

`https://lasacraimmobiliare.it/products/alloggio-a-moncalieri-di-4-locali?variant=54853547065671`

Angoli: prezzo/spazio, confronto mercato, famiglia, prima casa, libero subito, riscaldamento autonomo, tripla esposizione, dotazioni, zona, trasparenza, qualificazione, visita.

## Requisiti

- Windows
- Python 3.11+
- connessione internet

L'installatore crea automaticamente le dipendenze Python al primo avvio.
