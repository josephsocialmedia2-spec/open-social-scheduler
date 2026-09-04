# F1 · Buffer Free + Cloudinary Free

Obiettivo: collegamento iniziale una sola volta, poi pubblicazione automatica F1 su Facebook, Instagram e LinkedIn senza approvazione quotidiana.

## Architettura

GitHub Actions → genera contenuto/media → Cloudinary Free ospita il file → Buffer Free programma/pubblica → Facebook + Instagram + LinkedIn.

## Account social da collegare in Buffer

Il piano Free consente fino a 3 canali. Collegare esattamente:

1. una Pagina Facebook;
2. un account Instagram Business o Creator;
3. un profilo LinkedIn oppure una Pagina LinkedIn.

Il publisher scopre automaticamente gli ID dei tre canali. Non vanno copiati nel repository.

## Uniche due credenziali GitHub richieste

### BUFFER_API_KEY

Buffer → Settings → API → Create API Key.

Salvare il valore come GitHub Actions Secret con nome esatto:

`BUFFER_API_KEY`

### CLOUDINARY_URL

Creare/usare il piano Cloudinary Free. Dal dashboard copiare l'environment URL nel formato:

`cloudinary://API_KEY:API_SECRET@CLOUD_NAME`

Salvarlo come GitHub Actions Secret con nome esatto:

`CLOUDINARY_URL`

Cloudinary serve esclusivamente a fornire a Buffer URL HTTPS pubblici, diretti e stabili per immagini e video. Nessuna trasformazione a pagamento è richiesta dal workflow.

## Orari automatici

Europe/Rome:

- 10:30 → carousel/post su Facebook, Instagram e LinkedIn;
- 18:30 → Reel su Facebook e Instagram, video post su LinkedIn.

Il workflow GitHub parte prima dell'orario obiettivo, genera il contenuto, carica i media e usa `customScheduled` di Buffer. Se GitHub Actions parte in ritardo, il publisher usa `shareNow` come recupero nello stesso slot.

## Nessuna approvazione

Il workflow usa `schedulingType: automatic` e non crea bozze né richieste di approvazione.

## Idempotenza

Ogni slot ha un ID deterministico. Dopo ogni canale creato in Buffer, il relativo ID viene registrato in `publisher/queue.json`. Un retry crea soltanto i canali mancanti e non ripubblica quelli già schedulati.

## File operativi

- `publisher/buffer_twice_daily.py`
- `.github/workflows/buffer-twice-daily.yml`
- `publisher/queue.json`

Il vecchio workflow automatico Meta diretto è stato rimosso per evitare doppie pubblicazioni.

## Verifica finale

Dopo aver salvato i due Secrets, eseguire una volta il workflow `F1 Buffer Auto Publisher - 2 Daily x 3 Social` con `dry_run=true`. Se i tre canali vengono rilevati correttamente, eseguire `dry_run=false` oppure lasciare operare il prossimo slot automatico.
