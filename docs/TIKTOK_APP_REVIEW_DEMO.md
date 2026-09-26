# TikTok App Review Demo — F1 Social Publisher

## Scopo

Questa procedura serve a registrare il video richiesto da TikTok per la prima revisione dell'app **F1 Social Publisher**. La dimostrazione deve usare un **Sandbox TikTok reale** configurato nel Developer Portal. Non usare account Production per creare pubblicazioni pubbliche di prova.

Dominio mostrato nel video:

`https://josephsocialmedia2-spec.github.io/open-social-scheduler/`

F1 Content Hub:

`https://josephsocialmedia2-spec.github.io/open-social-scheduler/f1-content-hub/`

## Prerequisiti

- Sandbox creato nel TikTok Developer Portal.
- Target user TikTok aggiunto al Sandbox.
- Login Kit e Content Posting API presenti nel Sandbox.
- Direct Post abilitato.
- Redirect URI del Sandbox:
  `https://nqnmlsmeiynxbdojeyjt.supabase.co/functions/v1/f1-social-oauth/callback/tiktok`
- Scope dimostrati: `user.info.basic`, `video.publish`; se `video.upload` resta selezionato nel portale, dimostrare anche **Invia come bozza a TikTok**.
- URL properties verificati con il signature file esatto fornito da TikTok.
- Nessun client secret, access token o refresh token visibile nel video.

## Storyboard 2–4 minuti

### SCHERMATA 1 — Sito pubblico
Mostrare la home di F1 Social Publisher sul dominio ufficiale. Far vedere brevemente:
- nome del servizio;
- descrizione;
- link **Terms of Service**;
- link **Privacy Policy**.

### SCHERMATA 2 — Accesso F1 Content Hub
Aprire **F1 Content Hub** e accedere con l'utente autorizzato. Non mostrare password o strumenti sviluppatore.

### SCHERMATA 3 — Cliente e stato TikTok
Aprire **Automazione → Social collegati**. Mostrare il cliente utilizzato per la demo e lo stato TikTok.

Se TikTok non è collegato, premere **COLLEGA**.

### SCHERMATA 4 — Login Kit
Mostrare la pagina ufficiale TikTok di autorizzazione:
- nome F1 Social Publisher;
- account TikTok;
- consenso richiesto.

Confermare l'autorizzazione e mostrare il ritorno automatico al Content Hub.

### SCHERMATA 5 — Account collegato
Tornare in **Social collegati** e mostrare nickname/account TikTok collegato.

### SCHERMATA 6 — Contenuto video
Aprire **Archivio** e scegliere un contenuto video già approvato. Premere **TIKTOK**.

### SCHERMATA 7 — Query Creator Info
Mostrare la finestra **PUBBLICA SU TIKTOK** con:
- avatar;
- nickname;
- username;
- anteprima video;
- durata del video;
- limite massimo restituito dall'account quando disponibile.

Questi dati devono provenire dalla chiamata reale `creator_info/query`.

### SCHERMATA 8 — Caption
Mostrare la caption già presente, modificarla manualmente e far vedere il contatore. La caption deve restare editabile fino alla conferma.

### SCHERMATA 9 — Privacy
Aprire il menu **Privacy**. Deve iniziare senza una scelta predefinita. Selezionare manualmente una delle opzioni realmente restituite da TikTok.

Per un client non ancora auditato, usare l'opzione consentita dal Sandbox/creator; non tentare di forzare visibilità pubblica.

### SCHERMATA 10 — Commenti, Duet, Stitch
Mostrare:
- **Consenti commenti**
- **Consenti Duet**
- **Consenti Stitch**

Devono essere OFF all'apertura. Se TikTok segnala una funzione non disponibile, il controllo deve risultare disabilitato.

### SCHERMATA 11 — Contenuto commerciale
Attivare per pochi secondi **Questo contenuto promuove un brand, prodotto o servizio** e mostrare:
- **Il tuo brand**
- **Contenuto brandizzato / partnership**

Mostrare che la pubblicazione resta bloccata finché non viene selezionata almeno una classificazione. Disattivare di nuovo il controllo se il video di prova non è commerciale.

### SCHERMATA 12 — Consenso
Mostrare la dichiarazione:
`By posting, you agree to TikTok's Music Usage Confirmation`

Per branded content mostrare invece la dichiarazione che include anche la Branded Content Policy.

Spuntare il consenso.

### SCHERMATA 13 — Programmazione
Scegliere data e ora. Mostrare che **CONFERMA E PROGRAMMA SU TIKTOK** diventa disponibile solo dopo la validazione di tutti i campi.

Premere il pulsante.

### SCHERMATA 14 — Coda e stato
Aprire **Calendario editoriale** e mostrare la riga TikTok programmata. Quando il publisher parte nel Sandbox, mostrare il passaggio:
- PROGRAMMATO
- IN PUBBLICAZIONE
- PUBBLICATO

oppure un errore comprensibile se TikTok blocca la richiesta.

### SCHERMATA 15 — publish_id
Mostrare nell'Hub lo stato di pubblicazione / evento con il `publish_id` restituito da TikTok, senza mostrare token.

### SCHERMATA 16 — video.upload, solo se lo scope resta selezionato
Riaprire **TIKTOK**, scegliere **Invia come bozza a TikTok**, confermare il consenso e inviare un video di prova. Mostrare il completamento fino a `SEND_TO_USER_INBOX`.

Se il portale consente di rimuovere `video.upload` e la funzione bozza non viene richiesta dall'app, rimuovere lo scope prima della revisione invece di registrare questa schermata.

## Testo proposto per “Explain how each product and scope works”

> F1 Social Publisher is a web-based social media management platform for authorized client accounts. Login Kit lets an authorized user connect a TikTok account through TikTok OAuth. The user.info.basic scope is used to identify the connected account and display its basic profile information. The Content Posting API is used only after the user previews the video, edits the caption, chooses TikTok privacy and interaction settings, completes any commercial-content disclosure, and explicitly consents. The video.publish scope is used for Direct Post. If video.upload remains enabled in the TikTok app configuration, users can also choose to send a video to TikTok as a draft for further editing and posting in TikTok. Tokens are stored server-side and are never exposed in the browser.

## Prima di premere Submit for review

Non procedere finché:
- i tre URL risultano verificati;
- il Sandbox è realmente configurato;
- il target user Sandbox è collegato;
- il video demo mostra ogni prodotto e scope selezionato;
- Direct Post usa privacy scelta manualmente;
- nessuna pubblicazione pubblica di prova è stata eseguita.
