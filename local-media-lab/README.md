# Open Social Scheduler — Media Lab Locale

Modulo Windows per estrarre l’audio dai video e, quando richiesto, trascriverlo con Whisper direttamente sul computer.

## Privacy e funzionamento

- I file vengono elaborati esclusivamente in locale.
- Il servizio ascolta solo su `127.0.0.1:8765`.
- Nessun video, audio o testo viene inviato a servizi esterni.
- FFmpeg estrae e converte l’audio.
- Whisper genera la trascrizione italiana.
- I risultati vengono salvati nella cartella `elaborazioni`, salvo modifica nelle impostazioni.

## Prima installazione

1. Scaricare il repository come ZIP ed estrarlo.
2. Aprire la cartella `local-media-lab`.
3. Fare doppio clic su `INSTALLA_MEDIA_LAB.bat`.
4. Attendere l’installazione di Python, librerie, modello Whisper Base e FFmpeg.
5. Fare doppio clic su `AVVIA_MEDIA_LAB.bat`.
6. Il browser apre automaticamente `http://127.0.0.1:8765`.

## Utilizzo quotidiano

1. Avviare `AVVIA_MEDIA_LAB.bat`.
2. Aprire Open Social Scheduler.
3. Premere **Media Lab locale** nel menu.
4. Selezionare o trascinare il video.
5. Scegliere solo estrazione audio oppure estrazione e trascrizione.
6. Scegliere MP3, WAV o M4A.
7. Avviare l’elaborazione.
8. Scaricare i risultati o aprire la cartella locale.

## File generati

A seconda dell’operazione selezionata:

- audio `.mp3`, `.wav` oppure `.m4a`;
- trascrizione `.txt`;
- trascrizione `.docx`;
- sottotitoli `.srt`.

## Modelli Whisper

- `tiny`: più veloce, meno preciso;
- `base`: equilibrio consigliato;
- `small`: più preciso, richiede più risorse;
- `medium`: precisione elevata, più lento.

L’elaborazione resta locale. I modelli aggiuntivi vengono scaricati una sola volta e poi conservati sul computer.

## Arresto

Chiudere la finestra del server oppure eseguire `ARRESTA_MEDIA_LAB.bat`.
