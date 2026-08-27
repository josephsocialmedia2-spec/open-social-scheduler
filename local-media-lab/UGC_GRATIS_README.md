# AI UGC Reel Lab — motore locale gratuito

Questo modulo genera Reel UGC per **F1 Immobiliare** e **Real Media Pro** senza API a pagamento.

## Motori

- **Ollama**: scrittura locale degli script. Se non è disponibile vengono usati template locali F1/RMP.
- **Chatterbox Multilingual**: voce italiana locale. Per ottenere una voce femminile coerente, caricare 8–20 secondi di voce italiana pulita di una persona consenziente.
- **MuseTalk 1.5**: lip-sync sul video reale del modello.
- **FFmpeg**: montaggio 9:16, alternanza presenter/B-roll e audio finale.

## Perché il presenter parte da un video reale

Per un UGC credibile è preferibile registrare una volta il modello mentre guarda in camera e compie piccoli gesti naturali. In questo modo corpo, mani, capelli, respirazione, luce e micro-movimenti restano reali. L'IA interviene soprattutto su voce e bocca.

Registrare più basi diverse per ogni modello: fermo in camera, leggero walk-and-talk, seduto, alla scrivania, con smartphone, gesto verso camera. Durata consigliata: 10–30 secondi per clip.

## Installazione Windows

Dalla radice del repository fare doppio clic su:

`INSTALLA_AI_UGC_REEL_LAB.bat`

Oppure dalla cartella `local-media-lab`:

`INSTALLA_UGC_GRATIS.bat`

L'installer crea l'icona Desktop **AI UGC Reel Lab**.

## Hardware

Script, server e voce possono funzionare localmente anche senza GPU NVIDIA, con tempi più lunghi per la voce. MuseTalk è invece pensato per GPU NVIDIA/CUDA; l'installer non attiva servizi cloud o a pagamento se la GPU non è disponibile.

## Uso

1. Avviare **AI UGC Reel Lab** dal Desktop.
2. Scegliere F1 Immobiliare o Real Media Pro.
3. Scegliere obiettivo e format.
4. Caricare un breve video del modello.
5. Caricare una voce femminile italiana di riferimento.
6. Caricare B-roll reali e differenti.
7. Generare/modificare lo script.
8. Premere **CREA REEL**.
9. **STOP** interrompe il processo locale attivo, compresi TTS, MuseTalk o FFmpeg.
10. Il Reel finale e i file intermedi vengono salvati in `ugc_elaborazioni`.

## Regola contenuti

Il generatore non deve inventare vendite, numeri, testimonianze o risultati. Gli script descrivono metodo, problemi reali, servizi, processi, offerte e CTA verificabili. Nessuna pubblicazione social è automatica.
