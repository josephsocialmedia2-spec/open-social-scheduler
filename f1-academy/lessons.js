window.F1_LESSONS = [
{
 id:'start-shift',code:'F1-OG-000',stage:'INIZIO TURNO',title:'Avvia la giornata',role:'F1 Territory Scout',trigger:'Quando inizi il turno.',doneWhen:'Sei pronto a uscire con missione, zona e strumenti assegnati.',next:'prepare-zone',
 commands:['Apri TODAY’S MISSION.','Leggi: COMUNE, MICROZONA, VIA, CIVICI, OBIETTIVO.','Controlla i follow-up assegnati per oggi.','Apri lo storico della microzona.','Prendi scheda A5, penna, telefono e materiale F1 previsto.','Premi AVVIA MISSIONE.'],
 branches:[['Missione incompleta','NON USCIRE. Chiedi al responsabile di completarla.'],['Follow-up urgente assegnato','Eseguilo prima dell’uscita se la dashboard lo mette in priorità.']],
 record:['Ora inizio turno','Missione aperta','Operatore'],stop:['Non scegliere una zona diversa da quella assegnata.'],
 script:'Apri Today’s Mission. Leggi comune, microzona, via, civici e obiettivo. Controlla i follow-up assegnati. Apri lo storico della microzona. Prendi scheda A5, penna, telefono e materiale F1. Quando tutto è pronto, avvia la missione.'
},
{
 id:'prepare-zone',code:'F1-OG-010',stage:'PREPARAZIONE',title:'Prepara la zona',role:'F1 Territory Scout',trigger:'Hai aperto la missione del giorno.',doneWhen:'Sai esattamente da quale civico partire e quali informazioni sono già note.',next:'work-civic',
 commands:['Apri la mappa della microzona.','Individua il primo civico assegnato.','Leggi SOLO le informazioni già registrate su via/civico/palazzo.','Segna eventuali follow-up o immobili già noti presenti lungo il percorso.','Vai fisicamente al primo civico.'],
 branches:[['Civico già completato oggi','Passa al civico successivo.'],['Indirizzo errato o inesistente','Segna ANOMALIA INDIRIZZO e passa al successivo.']],
 record:['Via','Civici da lavorare','Ora ingresso zona'],stop:['Non dedurre proprietari, vendite o intenzioni da dati incompleti.'],
 script:'Apri la mappa. Individua il primo civico assegnato. Leggi solo ciò che F1 conosce già. Segna eventuali follow-up presenti sulla via. Vai al primo civico.'
},
{
 id:'work-civic',code:'F1-OG-020',stage:'TERRITORIO',title:'Lavora un civico',role:'F1 Territory Scout',trigger:'Sei davanti a un civico assegnato.',doneWhen:'Il civico è lavorato e ogni informazione utile è stata classificata.',next:'work-civic',
 commands:['Conferma VIA e CIVICO.','Osserva SOLO elementi immobiliari visibili e pertinenti.','Se vedi un cartello VENDESI/AFFITTASI → apri F1-OG-100.','Se devi fare contatto al citofono → apri F1-OG-021.','Se avviene un contatto alla porta → apri F1-OG-022.','Se ricevi un’informazione → apri F1-OG-030.','Quando il civico è chiuso, passa al civico successivo.'],
 branches:[['Nessuno risponde','Segna NESSUN CONTATTO e continua.'],['Persona chiede di non essere disturbata','Chiudi immediatamente la conversazione.'],['Emergenza / situazione anomala','Interrompi la procedura e avvisa il responsabile.']],
 record:['Via','Civico','Tipo attività','Esito'],stop:['Non fotografare persone.','Non trasformare un’osservazione in una vendita presunta.'],
 script:'Conferma via e civico. Osserva gli elementi immobiliari pertinenti. Se trovi un cartello usa la procedura cartello. Se fai citofono usa la procedura citofono. Se ricevi un’informazione usa la procedura notizia. Chiudi il civico e passa al successivo.'
},
{
 id:'intercom',code:'F1-OG-021',stage:'TERRITORIO',title:'Citofono',role:'F1 Territory Scout',trigger:'La missione prevede contatto citofonico.',doneWhen:'Hai ottenuto una risposta oppure hai registrato nessun contatto.',next:'work-civic',
 commands:['Suona UNA volta al nominativo/campanello previsto dalla missione.','Quando rispondono dì: “Buongiorno, sono [NOME] di F1 Immobiliare.”','Dichiara SOLO il motivo reale indicato nella missione.','Chiedi: “Posso farle una domanda velocissima?”','Se dice SÌ, fai UNA domanda territoriale prevista.','Ascolta. Non interrompere.','Ringrazia e chiudi.','Registra l’esito.'],
 branches:[['Dice NO','Rispondi “Grazie, buona giornata.” STOP.'],['Dice “io sto pensando di vendere”','Classifica CONTATTO DIRETTO e apri F1-OG-030.'],['Indica un’altra persona','NON chiedere numeri privati. Chiedi solo di lasciare il riferimento F1 alla persona interessata.']],
 record:['Civico','Ora','Risposta sì/no','Informazione ricevuta','Fonte'],stop:['Non insistere dopo un NO.','Non dire di avere un acquirente se non è vero.','Non chiedere dati personali di terzi.'],
 script:'Suona una volta. Presentati con nome e F1 Immobiliare. Dichiara il motivo reale. Chiedi il permesso per una domanda velocissima. Fai una sola domanda. Ascolta. Ringrazia. Chiudi. Registra.'
},
{
 id:'door',code:'F1-OG-022',stage:'TERRITORIO',title:'Porta a porta',role:'F1 Territory Scout',trigger:'La missione prevede porta a porta oppure una persona apre la porta durante il lavoro di zona.',doneWhen:'La conversazione è chiusa e l’esito registrato.',next:'work-civic',
 commands:['Mantieni distanza dalla porta.','Presentati: “[NOME], F1 Immobiliare.”','Dichiara il motivo reale della presenza in zona.','Fai UNA domanda prevista dalla missione.','Ascolta la risposta.','Se emerge interesse diretto, chiedi il permesso di far ricontattare la persona dal consulente F1.','Ringrazia e chiudi.','Registra subito dopo.'],
 branches:[['Non interessato','Ringrazia e chiudi.'],['Non ora','Chiedi SOLO se desidera essere ricontattato in futuro.'],['Interessato a valore/vendita','Apri F1-OG-030 e poi F1-OG-050.'],['Invito ad entrare','Non entrare salvo attività formalmente autorizzata e prevista.']],
 record:['Fonte diretta/indiretta','Nome se fornito volontariamente','Contatto se fornito volontariamente','Esito','Prossima azione'],stop:['Non fingere di essere un cliente.','Non raccogliere dati non necessari.','Non forzare una conversazione.'],
 script:'Mantieni distanza. Presentati. Dichiara il motivo reale. Fai una domanda. Ascolta. Se emerge interesse chiedi il permesso per il contatto del consulente. Ringrazia. Chiudi. Registra.'
},
{
 id:'news',code:'F1-OG-030',stage:'DATA CAPTURE',title:'Registra una notizia',role:'F1 Territory Scout',trigger:'Hai ricevuto o osservato un’informazione immobiliare utile.',doneWhen:'La notizia ha fonte, livello, attendibilità e prossima azione.',next:'work-civic',
 commands:['Scrivi COSA è stato detto/osservato senza interpretazioni.','Seleziona FONTE: osservazione / indiretta / diretta / documentata.','Assegna livello: N0 informazione; N1 segnale; N2 prospect; N3 prospect qualificato; N4 valutazione; N5 opportunità; N6 incarico.','Scrivi VIA e CIVICO se pertinenti.','Scrivi DATA e OPERATORE.','Definisci PROSSIMA AZIONE oppure NESSUNA AZIONE.','Salva.'],
 branches:[['Voce non verificata','Classifica N1.'],['Proprietario parla direttamente di possibile esigenza','Classifica almeno N2 e valuta F1-OG-050.'],['Chiede esplicitamente una valutazione','Classifica N4 e apri F1-OG-050.']],
 record:['Testo esatto informazione','Fonte','N0-N6','Attendibilità','Next action','Data'],stop:['Non scrivere “vende” se nessuno lo ha confermato.','Non trasformare un rumor in fatto.'],
 script:'Scrivi esattamente cosa sai. Seleziona la fonte. Assegna N0-N6. Inserisci via, civico, data e operatore. Definisci la prossima azione. Salva.'
},
{
 id:'call',code:'F1-OG-040',stage:'TELEFONO',title:'Esegui una chiamata',role:'F1 Territory Scout / Consulente secondo abilitazioni',trigger:'Il contatto compare nella coda chiamate con stato ABILITATO.',doneWhen:'La chiamata ha un esito e una prossima azione.',next:'followup',
 commands:['Apri il contatto dalla coda.','Verifica che STATO CONTATTO sia ABILITATO.','Leggi ultima interazione e motivo della chiamata.','Chiama dal numero operativo previsto.','Presentati con nome e F1 Immobiliare.','Dichiara il motivo reale della chiamata.','Fai la domanda prevista dalla scheda.','Chiudi concordando la prossima azione oppure nessuna azione.','Registra immediatamente.'],
 branches:[['Non risponde','Segna NON RISPONDE. Non inventare esito.'],['Chiede richiamo','Apri F1-OG-041.'],['Non vuole più contatti','Apri F1-OG-060.'],['Chiede valutazione/appuntamento','Apri F1-OG-050.']],
 record:['Data/ora','Esito','Note essenziali','Next action'],stop:['Non chiamare contatti NON ABILITATI.','Non richiamare chi ha espresso un divieto di contatto.'],
 script:'Apri il contatto dalla coda. Verifica che sia abilitato. Leggi ultima interazione e motivo. Chiama. Presentati. Dichiara il motivo reale. Fai la domanda prevista. Concorda la prossima azione. Registra.'
},
{
 id:'followup',code:'F1-OG-041',stage:'FOLLOW-UP',title:'Imposta un follow-up',role:'F1 Territory Scout / Consulente',trigger:'La persona ha autorizzato o concordato un contatto futuro.',doneWhen:'Esistono data, motivo, responsabile e azione.',next:'end-shift',
 commands:['Seleziona stato RICONTATTO AUTORIZZATO.','Inserisci DATA precisa o periodo concordato.','Scrivi il MOTIVO del richiamo.','Assegna RESPONSABILE.','Scrivi COSA fare al prossimo contatto.','Salva.'],
 branches:[['Dice “non ora” senza autorizzare richiamo','NON creare follow-up commerciale automatico.'],['Fornisce una data','Usa la data indicata.'],['Chiede di non essere contattato','Apri F1-OG-060.']],
 record:['Data follow-up','Motivo','Responsabile','Azione'],stop:['Mai scrivere solo “RICHIAMARE”.'],
 script:'Seleziona ricontatto autorizzato. Inserisci data. Scrivi il motivo. Assegna il responsabile. Scrivi l’azione del prossimo contatto. Salva.'
},
{
 id:'handoff',code:'F1-OG-050',stage:'HANDOFF',title:'Passa il prospect al consulente',role:'F1 Territory Scout',trigger:'Emergono interesse diretto, valutazione, appuntamento o opportunità concreta.',doneWhen:'Il consulente riceve una scheda completa e può agire senza richiedere chiarimenti di base.',next:'work-civic',
 commands:['Apri PASSAGGIO CONSULENTE.','Inserisci NOME/CONTATTO disponibili legittimamente.','Inserisci IMMOBILE o zona collegata.','Inserisci FONTE.','Inserisci COSA HA DETTO il prospect.','Inserisci ORIZZONTE TEMPORALE se dichiarato.','Inserisci richiesta: valore / vendita / appuntamento / altra esigenza.','Inserisci prossima azione concordata.','Invia al consulente assegnato.'],
 branches:[['Informazione solo indiretta','NON passare come prospect qualificato.'],['Richiesta valutazione','Priorità ALTA.'],['Appuntamento già concordato','Inserisci data e ora esatte.']],
 record:['Prospect ID','Fonte','Esigenza','Tempo','Next action','Consulente'],stop:['Non aggiungere motivazioni non dichiarate.'],
 script:'Apri passaggio consulente. Inserisci contatto, immobile, fonte, parole del prospect, orizzonte, richiesta e prossima azione. Invia al consulente.'
},
{
 id:'do-not-contact',code:'F1-OG-060',stage:'COMPLIANCE',title:'Non contattare',role:'Tutti',trigger:'La persona chiede chiaramente di non ricevere ulteriori contatti.',doneWhen:'Il contatto resta nello storico ma non compare più nelle code operative.',next:'end-shift',
 commands:['Interrompi la conversazione commerciale.','Seleziona NON CONTATTARE / NON CHIAMARE.','Inserisci data e canale della richiesta.','Salva.','Verifica che il contatto non compaia più nella coda.'],
 branches:[['Contatto noto/conoscente ma non pertinente','Usa NON CHIAMARE OPERATIVO senza cancellare lo storico.']],
 record:['Data richiesta','Canale','Operatore'],stop:['Non cancellare lo storico salvo procedura autorizzata.','Non reinserire manualmente il contatto in coda.'],
 script:'Interrompi la conversazione. Seleziona non contattare o non chiamare. Inserisci data e canale. Salva. Verifica che il contatto sia fuori dalla coda.'
},
{
 id:'sign',code:'F1-OG-100',stage:'MARKET INTELLIGENCE',title:'Cartello o annuncio osservato',role:'F1 Territory Scout',trigger:'Osservi un cartello pubblico o un immobile pubblicamente commercializzato.',doneWhen:'L’elemento è registrato come market intelligence senza conclusioni non verificate.',next:'work-civic',
 commands:['Registra VIA e CIVICO.','Registra tipo: PRIVATO / AGENZIA / NON DETERMINATO.','Registra DATA prima osservazione.','Se disponibile pubblicamente, registra prezzo e link annuncio.','Se agenzia, registra nome agenzia visibile.','Salva come MARKET INTELLIGENCE.'],
 branches:[['Annuncio scompare in futuro','Segna ANNUNCIO NON PIÙ OSSERVATO.'],['Prezzo cambia','Registra data e nuovo prezzo.']],
 record:['Indirizzo','Tipo','Prezzo pubblico','Fonte/link','Data'],stop:['Non scrivere “incarico scaduto” senza prova.','Non concludere che il proprietario sia acquisibile.'],
 script:'Registra indirizzo, tipo di cartello, data, prezzo e link se pubblici, agenzia se visibile. Salva come market intelligence. Non fare conclusioni sull’incarico.'
},
{
 id:'end-shift',code:'F1-OG-090',stage:'FINE TURNO',title:'Chiudi la giornata',role:'F1 Territory Scout',trigger:'Termina il turno o la missione assegnata.',doneWhen:'Ogni attività del giorno è registrata e non esistono follow-up senza data/motivo.',next:'start-shift',
 commands:['Apri F1 CLOSE.','Controlla civici lavorati.','Controlla conversazioni registrate.','Controlla notizie N0-N6.','Controlla prospect e handoff.','Controlla follow-up: devono avere data e motivo.','Controlla NON CHIAMARE / NON CONTATTARE.','Scrivi eventuali anomalie per il responsabile.','Chiudi la missione.'],
 branches:[['Manca una registrazione','NON chiudere. Completa il dato.'],['Dato dubbio','Segna DA VERIFICARE, non inventare.']],
 record:['Ora fine','Civici lavorati','Conversazioni','Notizie','Prospect','Follow-up','Anomalie'],stop:['Non chiudere la giornata con attività non registrate.'],
 script:'Apri F1 Close. Controlla civici, conversazioni, notizie, prospect, handoff e follow-up. Se manca un dato completalo. Se è dubbio segna da verificare. Chiudi la missione.'
}
];
