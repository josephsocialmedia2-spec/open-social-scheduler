# F1 Social — pubblicazione automatica dal PC sempre acceso

## Architettura attiva

Il PC Windows sempre acceso esegue il fallback browser di F1 Social.

Regola:

```text
1 CLIENTE = 1 PROFILO CHROME DEDICATO
```

Percorso predefinito:

```text
C:\F1Social\BrowserProfiles\<CLIENT_UUID>\chrome-profile
```

GitHub continua a sincronizzare e orchestrare la coda. Se un social è realmente collegato via API/OAuth usa l'API. Se non è collegato, il job passa al PC Windows e apre il profilo Chrome del cliente corretto.

## Installazione sul PC

Apri PowerShell nella cartella del repository ed esegui:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_f1_social_windows_runner.ps1
```

Se manca il token temporaneo del runner, lo script si ferma e mostra il link GitHub esatto da aprire. Il token non va salvato nel repository.

Il runner viene configurato con la label:

```text
f1-social-local-pc
```

e viene avviato automaticamente al login Windows, nello stesso account Windows che possiede le sessioni Chrome. Questo è necessario perché i cookie Chrome sono protetti dal profilo Windows.

## Preparazione automatica dei clienti

Dopo aver installato il runner, esegui:

```powershell
cd C:\F1Social\open-social-scheduler
$env:SUPABASE_SERVICE_ROLE_KEY="<VALORE_PROTETTO>"
C:\F1Social\venv\Scripts\python.exe scripts\f1_windows_prepare_clients.py
```

Lo script:

1. legge tutti i clienti attivi;
2. ignora i social già collegati correttamente via API;
3. individua solo i social non configurati che hanno un URL account noto;
4. crea il profilo Chrome dedicato del cliente;
5. apre i social da verificare;
6. richiede login/2FA solo se il social lo richiede;
7. verifica che account atteso e account aperto coincidano;
8. registra `CONNECTED` soltanto dopo la verifica;
9. non salva password o cookie in GitHub o Supabase.

## Pubblicazione

Il workflow:

```text
.github/workflows/f1-social-cloud-publisher.yml
```

usa:

```text
runs-on: [self-hosted, Windows, X64, f1-social-local-pc]
```

e:

```text
F1_BROWSER_ROOT=C:\F1Social\BrowserProfiles
F1_BROWSER_CHANNEL=chrome
F1_BROWSER_HEADLESS=true
```

Quando arriva l'orario:

```text
contenuto approvato
→ cliente
→ piattaforma
→ API collegata?
   → SI: API
   → NO: profilo Chrome dedicato del cliente
→ scarica media
→ inserisce caption approvata
→ pubblica
→ verifica il post
→ salva URL/ID quando disponibile
→ PUBLISHED
```

## Protezioni

Il sistema blocca la pubblicazione se:

- il profilo Chrome non è quello del cliente;
- l'account social aperto non coincide;
- la sessione è scaduta;
- compare CAPTCHA;
- viene richiesta 2FA;
- compare un checkpoint;
- manca un URL account affidabile;
- non può verificare che il post sia realmente pubblicato.

In questi casi usa `AUTH_REQUIRED` oppure `ACCOUNT_WRONG`.

## Nota

Il PC deve rimanere acceso e connesso a Internet. Il runner GitHub viene avviato al login Windows. Non è necessario tenere manualmente aperto Chrome: F1 Social apre il profilo corretto quando serve.
