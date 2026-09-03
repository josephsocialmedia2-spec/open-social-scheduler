window.F1_LESSONS = [
{
 id:'start-shift',code:'F1-OG-000',stage:'INIZIO GIORNATA',title:'Inizia il lavoro',
 role:'Tu, stagista o funzionario F1 che oggi lavora sul territorio.',
 trigger:'Quando arrivi in agenzia e inizi la giornata.',
 doneWhen:'Hai letto dove devi andare, cosa devi fare e cosa devi portare.',next:'prepare-zone',
 commands:[
  {text:'Apri MISSIONE DI OGGI.',action:'mission'},
  {text:'Leggi il PAESE assegnato.'},
  {text:'Leggi la ZONA PRECISA assegnata. È la piccola parte di paese che devi lavorare oggi.'},
  {text:'Leggi la VIA e i NUMERI DEI PALAZZI da controllare.'},
  {text:'Leggi l’OBIETTIVO. Ti dice che cosa devi fare in quella zona.'},
  {text:'Guarda se ci sono PERSONE DA RICHIAMARE OGGI. Sono persone con cui F1 ha già parlato e che hanno accettato un nuovo contatto.'},
  {text:'Prendi scheda A5, penna, telefono e il materiale F1 indicato nella missione.'},
  {text:'Quando hai tutto, premi AVVIA MISSIONE.',action:'start-mission'}
 ],
 branches:[
  ['Manca il paese, la via, i numeri dei palazzi o l’obiettivo','NON USCIRE. Chiama il responsabile e chiedi di completare la missione.'],
  ['C’è una persona da richiamare prima dell’uscita','Apri la sua scheda e segui la procedura PROGRAMMA O ESEGUI UN RICHIAMO.']
 ],
 record:['Ora in cui inizi','Tuo nome','Missione aperta: SÌ'],
 stop:['Non scegliere da solo un’altra zona.','Non inventare un obiettivo diverso da quello scritto.'],
 script:'Apri la missione di oggi. Leggi paese, zona, via, numeri dei palazzi e obiettivo. Controlla se devi richiamare qualcuno. Prendi il materiale indicato. Quando hai tutto, avvia la missione.'
},
{
 id:'prepare-zone',code:'F1-OG-010',stage:'PRIMA DI USCIRE',title:'Prepara la zona',
 role:'Tu, prima di andare sul posto.',
 trigger:'Hai aperto la missione di oggi.',
 doneWhen:'Sai da quale palazzo iniziare e che cosa F1 sa già di quella via.',next:'work-civic',
 commands:[
  {text:'Apri la MAPPA della zona assegnata.'},
  {text:'Trova la VIA scritta nella missione.'},
  {text:'Trova il PRIMO NUMERO DEL PALAZZO da cui devi iniziare.'},
  {text:'Apri lo STORICO DELLA ZONA. È l’elenco di ciò che F1 ha già registrato su quella via e sui palazzi.'},
  {text:'Leggi solo ciò che è già scritto. Non aggiungere supposizioni.'},
  {text:'Vai fisicamente al primo numero del palazzo indicato.'}
 ],
 branches:[
  ['Quel numero del palazzo è già stato lavorato oggi','Vai al numero successivo scritto nella missione.'],
  ['Il numero non esiste','Scrivi INDIRIZZO NON TROVATO e passa al numero successivo.']
 ],
 record:['Via','Numeri dei palazzi da lavorare','Ora in cui arrivi in zona'],
 stop:['Non decidere che una casa è vuota, in vendita o abitata solo perché ti sembra così.'],
 script:'Apri la mappa. Trova la via e il primo numero. Leggi quello che F1 sa già. Poi vai al primo palazzo.'
},
{
 id:'work-civic',code:'F1-OG-020',stage:'SUL TERRITORIO',title:'Lavora un palazzo',
 role:'Tu, mentre sei davanti a un numero della via assegnata.',
 trigger:'Sei arrivato davanti a un palazzo scritto nella missione.',
 doneWhen:'Hai fatto quello che era previsto e hai scritto l’esito.',next:'work-civic',
 commands:[
  {text:'Controlla che VIA e NUMERO DEL PALAZZO siano quelli scritti nella missione.'},
  {text:'Guarda solo elementi immobiliari visibili: cartelli, numero del palazzo, ingresso, informazioni pubbliche.'},
  {text:'Se vedi un cartello VENDESI o AFFITTASI, apri la procedura CARTELLO O ANNUNCIO.',target:'sign'},
  {text:'Se la missione ti dice di usare il citofono, apri la procedura CITOFONO.',target:'intercom'},
  {text:'Se parli con una persona alla porta, apri la procedura PORTA A PORTA.',target:'door'},
  {text:'Se qualcuno ti dice qualcosa di utile su una casa o su una possibile vendita, apri la procedura SCRIVI UNA INFORMAZIONE.',target:'news'},
  {text:'Quando hai finito, passa al numero del palazzo successivo.'}
 ],
 branches:[
  ['Nessuno risponde','Scrivi NESSUN CONTATTO e continua.'],
  ['Una persona dice che non vuole essere disturbata','Ringrazia. Chiudi subito. Non insistere.'],
  ['Succede qualcosa che non è previsto','Fermati e chiama il responsabile.']
 ],
 record:['Via','Numero del palazzo','Cosa hai fatto','Risultato'],
 stop:['Non fotografare persone.','Non scrivere che qualcuno vende se nessuno lo ha detto.'],
 script:'Controlla via e numero. Guarda solo ciò che è visibile. Se trovi un cartello, usa la procedura cartello. Se usi il citofono, usa la procedura citofono. Se ricevi un’informazione, registrala. Poi passa al numero successivo.'
},
{
 id:'intercom',code:'F1-OG-021',stage:'SUL TERRITORIO',title:'Usa il citofono',
 role:'Tu, quando la missione ti dice di suonare.',
 trigger:'Sei davanti al palazzo e la missione prevede il citofono.',
 doneWhen:'Hai parlato con qualcuno oppure hai scritto che nessuno ha risposto.',next:'work-civic',
 commands:[
  {text:'Suona UNA SOLA VOLTA al campanello indicato nella missione.'},
  {text:'Se rispondono, dì: “Buongiorno, sono [TUO NOME] di F1 Immobiliare.”'},
  {text:'Dì il motivo vero per cui stai lavorando in quella zona. Usa il motivo scritto nella missione.'},
  {text:'Chiedi: “Posso farle una domanda velocissima?”'},
  {text:'Se dice SÌ, fai UNA SOLA domanda scritta nella missione.'},
  {text:'Ascolta la risposta senza interrompere.'},
  {text:'Dì: “Grazie, buona giornata.”'},
  {text:'Scrivi subito che cosa è successo.'}
 ],
 branches:[
  ['Dice NO','Dì “Grazie, buona giornata.” e chiudi.'],
  ['Dice direttamente che sta pensando di vendere','Apri SCRIVI UNA INFORMAZIONE.',target:'news'},
  ['Ti parla di un’altra persona','Non chiedere il suo numero. Lascia solo il contatto F1 da riferire alla persona interessata.']
 ],
 record:['Via e numero','Ora','Ha risposto: SÌ/NO','Che cosa ha detto','Chi te lo ha detto'],
 stop:['Non insistere dopo un NO.','Non dire che hai un acquirente se non è vero.','Non chiedere numeri privati di altre persone.'],
 script:'Suona una volta. Presentati. Dì il motivo vero. Chiedi se puoi fare una domanda. Fai una sola domanda. Ascolta. Ringrazia. Scrivi l’esito.'
},
{
 id:'door',code:'F1-OG-022',stage:'SUL TERRITORIO',title:'Parla alla porta',
 role:'Tu, quando una persona apre la porta mentre lavori nella zona.',
 trigger:'La missione prevede porta a porta oppure una persona apre mentre sei sul posto.',
 doneWhen:'La conversazione è finita e hai scritto l’esito.',next:'work-civic',
 commands:[
  {text:'Resta a una distanza normale dalla porta.'},
  {text:'Dì: “Buongiorno, sono [TUO NOME] di F1 Immobiliare.”'},
  {text:'Spiega in una frase il motivo vero per cui sei in quella zona.'},
  {text:'Fai UNA SOLA domanda prevista dalla missione.'},
  {text:'Ascolta la risposta.'},
  {text:'Se la persona dice che potrebbe vendere o vuole sapere quanto vale casa, chiedi: “Posso farla ricontattare dal consulente F1 che si occupa di valutazioni e appuntamenti?”'},
  {text:'Ringrazia e chiudi la conversazione.'},
  {text:'Scrivi subito che cosa è successo.'}
 ],
 branches:[
  ['Dice che non è interessata','Ringrazia e vai via.'],
  ['Dice “non adesso”','Chiedi solo se vuole essere richiamata in futuro.'],
  ['Dice che vuole vendere o conoscere il valore della casa','Prima scrivi l’informazione, poi passa la persona al consulente.',target:'news'},
  ['Ti invita a entrare','Non entrare se la missione non prevede un appuntamento autorizzato.']
 ],
 record:['Chi ti ha parlato','Nome solo se lo dice volontariamente','Telefono solo se lo dà volontariamente','Che cosa ha detto','Cosa bisogna fare dopo'],
 stop:['Non fingere di essere un cliente.','Non chiedere dati che non servono.','Non continuare se la persona vuole chiudere.'],
 script:'Presentati. Spiega perché sei lì. Fai una domanda. Ascolta. Se la persona mostra interesse, chiedi il permesso per farla ricontattare. Ringrazia e scrivi tutto.'
},
{
 id:'news',code:'F1-OG-030',stage:'SCRIVI QUELLO CHE HAI SAPUTO',title:'Scrivi una informazione',
 role:'Tu, subito dopo aver visto o sentito qualcosa di utile.',
 trigger:'Hai ricevuto una informazione su una casa, un proprietario o una possibile vendita.',
 doneWhen:'Hai scritto cosa sai, chi te lo ha detto, dove e cosa bisogna fare dopo.',next:'work-civic',
 commands:[
  {text:'Scrivi con parole semplici ESATTAMENTE che cosa hai visto o che cosa ti è stato detto.'},
  {text:'Scegli CHI TE LO HA DETTO: l’hai visto tu / te lo ha detto un’altra persona / te lo ha detto direttamente il proprietario / lo hai letto in un documento o annuncio pubblico.'},
  {text:'Scegli il livello: N0 = semplice informazione; N1 = voce non confermata; N2 = hai individuato una persona che potrebbe avere bisogno; N3 = la persona ha parlato direttamente con F1; N4 = chiede quanto vale la casa; N5 = sta valutando concretamente di vendere; N6 = F1 ha già ricevuto l’incarico di vendita.'},
  {text:'Scrivi VIA e NUMERO DEL PALAZZO, se li conosci.'},
  {text:'Scrivi la DATA e il TUO NOME.'},
  {text:'Scrivi COSA BISOGNA FARE DOPO. Se non bisogna fare niente, scrivi NESSUNA AZIONE.'},
  {text:'Premi SALVA.'}
 ],
 branches:[
  ['È solo una voce detta da qualcuno e non è confermata','Scegli N1 = VOCE NON CONFERMATA.'],
  ['Il proprietario ti dice direttamente che potrebbe vendere','Scegli almeno N3 e poi passa la persona al consulente.',target:'handoff'},
  ['Il proprietario chiede quanto vale la casa','Scegli N4 e passa la persona al consulente.',target:'handoff'}
 ],
 record:['Che cosa sai','Chi te lo ha detto','Livello N0-N6','Via e numero','Cosa fare dopo','Data','Tuo nome'],
 stop:['Non scrivere “vende” se nessuno lo ha confermato.','Non trasformare una voce in un fatto.'],
 script:'Scrivi esattamente cosa sai. Scrivi da dove arriva l’informazione. Scegli il livello. Inserisci indirizzo, data e nome. Scrivi cosa bisogna fare dopo. Salva.'
},
{
 id:'call',code:'F1-OG-040',stage:'TELEFONO',title:'Fai una telefonata',
 role:'Tu, solo quando il sistema ti mostra una persona che puoi chiamare.',
 trigger:'Il nome compare nella lista CHIAMATE DI OGGI e la scheda dice CHIAMABILE.',
 doneWhen:'Hai scritto come è andata la telefonata e cosa bisogna fare dopo.',next:'followup',
 commands:[
  {text:'Apri la persona dalla lista CHIAMATE DI OGGI.'},
  {text:'Controlla che nella scheda ci sia scritto CHIAMABILE. Se non c’è scritto, NON chiamare.'},
  {text:'Leggi l’ultima cosa successa con quella persona.'},
  {text:'Leggi perché devi chiamarla oggi.'},
  {text:'Premi CHIAMA.'},
  {text:'Quando risponde, dì il tuo nome e “F1 Immobiliare”.'},
  {text:'Spiega in una frase perché la stai chiamando.'},
  {text:'Fai la domanda scritta nella scheda.'},
  {text:'Prima di chiudere, chiarisci se bisogna richiamare, fissare un appuntamento oppure non fare altro.'},
  {text:'Scrivi subito l’esito.'}
 ],
 branches:[
  ['Non risponde','Scrivi NON RISPONDE.'],
  ['Chiede di essere richiamata','Apri PROGRAMMA UN RICHIAMO.',target:'followup'},
  ['Dice di non voler più essere contattata','Apri NON CHIAMARE PIÙ.',target:'do-not-contact'},
  ['Chiede quanto vale casa o vuole un appuntamento','Apri PASSA LA PERSONA AL CONSULENTE.',target:'handoff'}
 ],
 record:['Data e ora','Come è andata','Cosa ha detto di importante','Cosa bisogna fare dopo'],
 stop:['Non chiamare se la scheda non dice CHIAMABILE.','Non richiamare una persona che ha chiesto di non essere contattata.'],
 script:'Apri il nome dalla lista. Controlla che sia chiamabile. Leggi perché devi chiamare. Telefona. Presentati. Fai la domanda prevista. Scrivi come è andata e cosa fare dopo.'
},
{
 id:'followup',code:'F1-OG-041',stage:'RICHIAMO',title:'Programma un richiamo',
 role:'Tu, quando una persona accetta di essere ricontattata.',
 trigger:'La persona dice chiaramente che puoi chiamarla di nuovo.',
 doneWhen:'Hai scritto quando richiamarla, perché e chi deve farlo.',next:'end-shift',
 commands:[
  {text:'Apri la scheda della persona.'},
  {text:'Seleziona RICHIAMO AUTORIZZATO. Significa che la persona ha accettato un nuovo contatto.'},
  {text:'Scrivi la DATA precisa del richiamo. Se ha detto “la prossima settimana”, scrivi il periodo indicato.'},
  {text:'Scrivi PERCHÉ devi richiamarla.'},
  {text:'Scrivi CHI deve fare la chiamata.'},
  {text:'Scrivi la PRIMA COSA da chiedere quando la richiamerai.'},
  {text:'Premi SALVA.'}
 ],
 branches:[
  ['Dice solo “non ora” ma non ti autorizza a richiamare','Non programmare una nuova chiamata.'],
  ['Ti dà una data precisa','Usa quella data.'],
  ['Dice che non vuole più chiamate','Apri NON CHIAMARE PIÙ.',target:'do-not-contact'}
 ],
 record:['Data del richiamo','Motivo','Nome di chi deve chiamare','Prima domanda da fare'],
 stop:['Non scrivere solo “RICHIAMARE”. Devi sempre scrivere quando e perché.'],
 script:'Apri la scheda. Segna che il richiamo è autorizzato. Scrivi quando, perché, chi deve chiamare e cosa deve chiedere. Salva.'
},
{
 id:'handoff',code:'F1-OG-050',stage:'PASSA IL CONTATTO',title:'Passa la persona al consulente',
 role:'Tu, quando una persona mostra un interesse reale.',
 trigger:'La persona dice direttamente che potrebbe vendere, vuole sapere il valore della casa o vuole un appuntamento.',
 doneWhen:'Il consulente F1 riceve tutte le informazioni necessarie per continuare.',next:'work-civic',
 commands:[
  {text:'Apri PASSA AL CONSULENTE.'},
  {text:'Scrivi NOME e TELEFONO solo se la persona li ha forniti.'},
  {text:'Scrivi quale CASA o quale ZONA riguarda.'},
  {text:'Scrivi CHI ti ha dato l’informazione.'},
  {text:'Scrivi con parole semplici CHE COSA HA DETTO la persona.'},
  {text:'Se ha detto quando pensa di muoversi, scrivi il periodo.'},
  {text:'Scegli cosa chiede: SAPERE IL VALORE / VENDERE / APPUNTAMENTO / ALTRO.'},
  {text:'Scrivi che cosa avete concordato come prossimo passo.'},
  {text:'Premi INVIA AL CONSULENTE.'}
 ],
 branches:[
  ['Hai sentito solo una voce da un’altra persona','Non presentarla come persona interessata. Prima registra la voce come informazione.'],
  ['Chiede quanto vale la casa','Segna PRIORITÀ ALTA.'],
  ['Avete già fissato un appuntamento','Scrivi giorno e ora esatti.']
 ],
 record:['Nome','Telefono se fornito','Casa o zona','Che cosa ha detto','Quando','Che cosa chiede','Prossimo passo'],
 stop:['Non aggiungere motivi o intenzioni che la persona non ha detto.'],
 script:'Apri passa al consulente. Scrivi contatto, casa, fonte, parole dette, periodo, richiesta e prossimo passo. Invia.'
},
{
 id:'do-not-contact',code:'F1-OG-060',stage:'NON CHIAMARE',title:'Non chiamare più questa persona',
 role:'Chiunque stia parlando con la persona.',
 trigger:'La persona dice chiaramente che non vuole più essere chiamata o contattata.',
 doneWhen:'La persona resta nello storico ma non appare più nelle liste di chiamata.',next:'end-shift',
 commands:[
  {text:'Chiudi subito la conversazione commerciale.'},
  {text:'Apri la scheda della persona.'},
  {text:'Premi NON CONTATTARE / NON CHIAMARE.'},
  {text:'Scrivi la DATA.'},
  {text:'Scrivi dove lo ha chiesto: telefono / WhatsApp / email / di persona.'},
  {text:'Premi SALVA.'},
  {text:'Controlla che il nome non compaia più nella lista CHIAMATE DI OGGI.'}
 ],
 branches:[
  ['È un conoscente o una persona che non deve essere chiamata per motivi operativi','Usa NON CHIAMARE OPERATIVO senza cancellare lo storico.']
 ],
 record:['Data','Come ha chiesto di non essere contattata','Tuo nome'],
 stop:['Non cancellare lo storico solo per togliere il nome dalla lista.','Non rimettere manualmente la persona nella lista chiamate.'],
 script:'Chiudi la conversazione. Apri la scheda. Premi non contattare. Scrivi data e come lo ha chiesto. Salva. Controlla che sia fuori dalla lista chiamate.'
},
{
 id:'sign',code:'F1-OG-100',stage:'CARTELLO O ANNUNCIO',title:'Registra un cartello o un annuncio',
 role:'Tu, quando vedi pubblicamente che una casa è proposta in vendita o affitto.',
 trigger:'Vedi un cartello oppure trovi un annuncio pubblico collegato alla zona.',
 doneWhen:'Hai scritto i dati visibili senza inventare informazioni mancanti.',next:'work-civic',
 commands:[
  {text:'Scrivi VIA e NUMERO DEL PALAZZO.'},
  {text:'Scegli chi sembra pubblicizzare l’immobile: PRIVATO / AGENZIA / NON SI CAPISCE.'},
  {text:'Scrivi la DATA in cui lo hai visto per la prima volta.'},
  {text:'Se il prezzo è pubblico, scrivilo.'},
  {text:'Se hai trovato l’annuncio online, incolla il LINK.'},
  {text:'Se sul cartello compare il nome di un’agenzia, scrivi quel nome.'},
  {text:'Premi SALVA.'}
 ],
 branches:[
  ['In futuro l’annuncio non si trova più','Scrivi ANNUNCIO NON PIÙ VISTO. Non scrivere che l’incarico è scaduto.'],
  ['Il prezzo cambia','Scrivi la nuova cifra e la data del cambiamento.']
 ],
 record:['Via e numero','Privato/Agenzia/Non si capisce','Prezzo se pubblico','Link se esiste','Data'],
 stop:['Non scrivere “incarico scaduto” senza una prova.','Non concludere che il proprietario voglia cambiare agenzia.'],
 script:'Scrivi indirizzo, chi pubblicizza, data, prezzo se pubblico, link se disponibile e nome agenzia se visibile. Salva. Non inventare altro.'
},
{
 id:'end-shift',code:'F1-OG-090',stage:'FINE GIORNATA',title:'Chiudi il lavoro di oggi',
 role:'Tu, prima di finire la giornata.',
 trigger:'Hai terminato il tempo di lavoro o hai completato la missione assegnata.',
 doneWhen:'Tutto quello che hai fatto oggi è scritto e ogni richiamo ha una data e un motivo.',next:'start-shift',
 commands:[
  {text:'Apri il RIEPILOGO DI OGGI.'},
  {text:'Controlla che ogni palazzo lavorato abbia un risultato scritto.'},
  {text:'Controlla che ogni informazione ricevuta sia stata salvata.'},
  {text:'Controlla le PERSONE DA RICHIAMARE. Ognuna deve avere una data e un motivo.'},
  {text:'Controlla che le persone che hanno chiesto di non essere chiamate siano fuori dalla lista chiamate.'},
  {text:'Scrivi eventuali problemi che il responsabile deve vedere domani.'},
  {text:'Premi CHIUDI GIORNATA.'}
 ],
 branches:[
  ['Trovi un richiamo senza data o senza motivo','Apri la persona e completa i dati prima di chiudere.'],
  ['Trovi una attività fatta ma non registrata','Scrivila prima di chiudere la giornata.']
 ],
 record:['Ora fine lavoro','Numero di palazzi lavorati','Numero di conversazioni','Informazioni raccolte','Richiami programmati','Problemi da segnalare'],
 stop:['Non chiudere la giornata lasciando attività senza esito scritto.'],
 script:'Apri il riepilogo. Controlla palazzi, informazioni, richiami e persone da non chiamare. Scrivi i problemi. Poi chiudi la giornata.'
}
];