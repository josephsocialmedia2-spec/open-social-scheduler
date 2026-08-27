# F1 / RMP AI Call Copilot

MVP di copilota vocale assistito per chiamate commerciali F1 Immobiliare e Real Media Pro.

## Cosa fa ora
- Selezione F1 / RMP.
- Aperture e risposte rapide alle obiezioni principali.
- Riconoscimento vocale browser in italiano quando supportato.
- Suggerimento automatico della risposta in base alle parole del cliente.
- Sintesi vocale browser della risposta selezionata.
- Stop immediato e pulsante PRENDO IO LA CHIAMATA.
- Esito chiamata e note.
- CRM locale esportabile JSON.
- Rotazione giornaliera di 5 zone.
- Nessuna modifica alla versione main dello scheduler.

## Limite importante della v1
Il browser non può intercettare automaticamente l'audio di una normale chiamata telefonica del cellulare. Per una conversazione realmente integrata servono telefonia VoIP/WebRTC e un backend che riceva l'audio della chiamata.

## Fase 2 proposta
Architettura: telefonia VoIP/WebRTC -> streaming audio -> speech-to-text -> motore AI -> text-to-speech/voice clone -> ritorno audio in chiamata -> CRM.

La chiave API del provider vocale non deve essere inserita nel JavaScript pubblico di GitHub Pages. Va custodita lato server.

## Modalità operativa prevista
1. Joseph avvia la chiamata.
2. Ascolto/transcrizione live.
3. L'AI suggerisce una risposta entro pochi istanti.
4. Joseph può premere AI PARLA oppure parlare direttamente.
5. PRENDO IO interrompe immediatamente la voce sintetica.
6. A fine chiamata viene salvato l'esito.

## Sviluppo
Branch: `ai-call-copilot`
Percorso: `/ai-call-copilot/`
