window.F1_LESSONS = [
{
 id:'start-shift',code:'F1-OG-000',stage:'INIZIO GIORNATA',title:'Inizia il lavoro',
 role:'Tu, stagista o funzionario F1.',
 trigger:'Quando inizi la giornata di lavoro.',
 doneWhen:'Sai dove andare, cosa fare e cosa portare.',next:'prepare-zone',
 commands:[
  {text:'Apri MISSIONE DI OGGI.',action:'mission'},
  {text:'Leggi il PAESE assegnato.'},
  {text:'Leggi la ZONA PRECISA assegnata.'},
  {text:'Leggi la VIA e i NUMERI DEI PALAZZI da controllare.'},
  {text:'Leggi COSA DEVI FARE oggi.'},
  {text:'Guarda se ci sono PERSONE DA RICHIAMARE OGGI. Sono persone che hanno accettato di essere ricontattate.'},
  {text:'Prendi scheda A5, penna, telefono e il materiale F1 indicato.'},
  {text:'Premi AVVIA MISSIONE.',action:'start-mission'}
 ],
 branches:[
  ['Manca paese, via, numeri o attività da fare','NON USCIRE. Chiama il responsabile.'],
  ['C’è una persona da richiamare prima dell’uscita','Apri la sua scheda e usa PROGRAMMA UN RICHIAMO.']
 ],
 record:['Ora di inizio','Tuo nome','Missione aperta: SÌ'],
 stop:['Non scegliere da solo un’altra zona.','Non inventare attività diverse da quelle scritte.'],
 script:'Apri la missione di oggi. Leggi dove andare e cosa fare. Controlla se devi richiamare qualcuno. Prendi il materiale. Poi avvia la missione.'
},
{
 id:'prepare-zone',code:'F1-OG-010',stage:'PRIMA DI USCIRE',title:'Prepara la zona',
 role:'Tu, prima di andare sul posto.',
 trigger:'Hai aperto la missione di oggi.',
 doneWhen:'Sai da quale palazzo iniziare.',next:'work-civic',
 commands:[
  {text:'Apri la MAPPA della zona assegnata.'},
  {text:'Trova la VIA scritta nella missione.'},
  {text:'Trova il PRIMO NUMERO DEL PALAZZO da cui devi iniziare.'},
  {text:'Apri STORICO DELLA ZONA. È l’elenco di ciò che F1 ha già scritto su quella via.'},
  {text:'Leggi solo ciò che è già scritto.'},
  {text:'Vai al primo palazzo indicato.'}
 ],
 branches:[
  ['Quel palazzo è già stato lavorato oggi','Vai al numero successivo.'],
  ['Il numero non esiste','Scrivi INDIRIZZO NON TROVATO e passa al successivo.']
 ],
 record:['Via','Numeri da lavorare','Ora di arrivo'],
 stop:['Non decidere che una casa è vuota o in vendita solo perché ti sembra così.'],
 script:'Apri la mappa. Trova la via e il primo numero. Leggi ciò che F1 sa già. Poi vai al primo palazzo.'
},
{
 id:'work-civic',code:'F1-OG-020',stage:'SUL TERRITORIO',title:'Lavora un palazzo',
 role:'Tu, davanti a un palazzo assegnato.',
 trigger:'Sei arrivato davanti al numero scritto nella missione.',
 doneWhen:'Hai fatto l’attività prevista e scritto il risultato.',next:'work-civic',
 commands:[
  {text:'Controlla VIA e NUMERO DEL PALAZZO.'},
  {text:'Guarda solo ciò che è visibile e riguarda immobili: cartelli, ingresso, numero del palazzo.'},
  {text:'Se vedi VENDESI o AFFITTASI, apri CARTELLO O ANNUNCIO.',target:'sign'},
  {text:'Se devi suonare, apri USA IL CITOFONO.',target:'intercom'},
  {text:'Se una persona apre la porta, apri PARLA ALLA PORTA.',target:'door'},
  {text:'Se qualcuno ti dice qualcosa di utile su una casa, apri SCRIVI UNA INFORMAZIONE.',target:'news'},
  {text:'Quando hai finito, vai al palazzo successivo.'}
 ],
 branches:[
  ['Nessuno risponde','Scrivi NESSUN CONTATTO e continua.'],
  ['Una persona non vuole essere disturbata','Ringrazia e chiudi subito.'],
  ['Succede qualcosa che non è previsto','Fermati e chiama il responsabile.']
 ],
 record:['Via','Numero','Cosa hai fatto','Risultato'],
 stop:['Non fotografare persone.','Non scrivere che qualcuno vende se nessuno lo ha detto.'],
 script:'Controlla via e numero. Fai solo l’attività prevista. Scrivi il risultato. Poi passa al numero successivo.'
},
{
 id:'intercom',code:'F1-OG-021',stage:'SUL TERRITORIO',title:'Usa il citofono',
 role:'Tu, quando la missione ti dice di suonare.',
 trigger:'Sei davanti al palazzo e devi usare il citofono.',
 doneWhen:'Hai parlato con qualcuno oppure hai scritto NESSUNA RISPOSTA.',next:'work-civic',
 commands:[
  {text:'Suona UNA SOLA VOLTA al campanello indicato.'},
  {text:'Se rispondono, dì: “Buongiorno, sono [TUO NOME] di F1 Immobiliare.”'},
  {text:'Dì il motivo vero scritto nella missione.'},
  {text:'Chiedi: “Posso farle una domanda velocissima?”'},
  {text:'Se dice SÌ, fai UNA SOLA domanda prevista.'},
  {text:'Ascolta senza interrompere.'},
  {text:'Dì: “Grazie, buona giornata.”'},
  {text:'Scrivi subito che cosa è successo.'}
 ],
 branches:[
  ['Dice NO','Dì “Grazie, buona giornata.” e chiudi.'],
  ['Dice che sta pensando di vendere','Apri SCRIVI UNA INFORMAZIONE.'],
  ['Parla di un’altra persona','Non chiedere il numero di quella persona. Lascia il contatto F1.']
 ],
 record:['Via e numero','Ora','Ha risposto: SÌ/NO','Che cosa ha detto'],
 stop:['Non insistere dopo un NO.','Non dire di avere un acquirente se non è vero.','Non chiedere numeri privati di terzi.'],
 script:'Suona una volta. Presentati. Dì il motivo vero. Fai una sola domanda. Ascolta. Ringrazia. Scrivi il risultato.'
},
{
 id:'door',code:'F1-OG-022',stage:'SUL TERRITORIO',title:'Parla alla porta',
 role:'Tu, quando una persona apre la porta.',
 trigger:'La missione prevede porta a porta oppure una persona apre mentre sei sul posto.',
 doneWhen:'La conversazione è finita e hai scritto il risultato.',next:'work-civic',
 commands:[
  {text:'Resta a una distanza normale dalla porta.'},
  {text:'Dì: “Buongiorno, sono [TUO NOME] di F1 Immobiliare.”'},
  {text:'Spiega in una frase perché sei lì.'},
  {text:'Fai UNA SOLA domanda prevista dalla missione.'},
  {text:'Ascolta la risposta.'},
  {text:'Se dice che potrebbe vendere o vuole sapere quanto vale casa, chiedi se può essere ricontattata dal consulente F1.'},
  {text:'Ringrazia e chiudi.'},
  {text:'Scrivi subito che cosa è successo.'}
 ],
 branches:[
  ['Non è interessata','Ringrazia e vai via.'],
  ['Dice “non adesso”','Chiedi solo se vuole essere richiamata in futuro.'],
  ['Vuole vendere o sapere il valore','Apri SCRIVI UNA INFORMAZIONE.'],
  ['Ti invita a entrare','Non entrare se non hai un appuntamento autorizzato.']
 ],
 record:['Nome se lo dice','Telefono se lo dà','Che cosa ha detto','Cosa fare dopo'],
 stop:['Non fingere di essere un cliente.','Non chiedere dati inutili.','Non continuare se la persona vuole chiudere.'],
 script:'Presentati. Spiega perché sei lì. Fai una domanda. Ascolta. Se mostra interesse, chiedi il permesso per farla ricontattare. Poi scrivi tutto.'
},
{
 id:'news',code:'F1-OG-030',stage:'SCRIVI QUELLO CHE HAI SAPUTO',title:'Scrivi una informazione',
 role:'Tu, subito dopo aver visto o sentito qualcosa di utile.',
 trigger:'Hai ricevuto una informazione su una casa o una possibile vendita.',
 doneWhen:'Hai scritto cosa sai, da chi arriva e cosa fare dopo.',next:'work-civic',
 commands:[
  {text:'Scrivi ESATTAMENTE che cosa hai visto o che cosa ti è stato detto.'},
  {text:'Scegli da dove arriva: L’HO VISTO IO / ME LO HA DETTO UN’ALTRA PERSONA / ME LO HA DETTO IL PROPRIETARIO / L’HO LETTO IN UN ANNUNCIO O DOCUMENTO PUBBLICO.'},
  {text:'Scegli il livello: N0 = semplice informazione; N1 = voce non confermata; N2 = persona possibile; N3 = la persona ha parlato direttamente con F1; N4 = chiede quanto vale casa; N5 = sta pensando concretamente di vendere; N6 = F1 ha già l’incarico di vendita.'},
  {text:'Scrivi VIA e NUMERO, se li conosci.'},
  {text:'Scrivi DATA e TUO NOME.'},
  {text:'Scrivi COSA FARE DOPO. Se non c’è niente da fare, scrivi NESSUNA AZIONE.'},
  {text:'Premi SALVA.'}
 ],
 branches:[
  ['È solo una voce non confermata','Scegli N1 = VOCE NON CONFERMATA.'],
  ['Il proprietario dice che potrebbe vendere','Scegli N3 e poi apri PASSA LA PERSONA AL CONSULENTE.'],
  ['Il proprietario chiede quanto vale casa','Scegli N4 e poi apri PASSA LA PERSONA AL CONSULENTE.']
 ],
 record:['Che cosa sai','Da chi arriva','Livello N0-N6','Via e numero','Cosa fare dopo','Data','Tuo nome'],
 stop:['Non scrivere “vende” se nessuno lo ha confermato.','Non trasformare una voce in un fatto.'],
 script:'Scrivi esattamente cosa sai. Scrivi da dove arriva. Scegli il livello. Inserisci indirizzo, data, nome e cosa fare dopo. Salva.'
},
{
 id:'call',code:'F1-OG-040',stage:'TELEFONO',title:'Fai una telefonata',
 role:'Tu, solo quando il sistema ti mostra una persona che puoi chiamare.',
 trigger:'Il nome è nella lista CHIAMATE DI OGGI e la scheda dice CHIAMABILE.',
 doneWhen:'Hai scritto come è andata e cosa fare dopo.',next:'followup',
 commands:[
  {text:'Apri la persona dalla lista CHIAMATE DI OGGI.'},
  {text:'Controlla che ci sia scritto CHIAMABILE. Se non c’è, NON chiamare.'},
  {text:'Leggi l’ultima cosa successa con quella persona.'},
  {text:'Leggi perché devi chiamarla oggi.'},
  {text:'Premi CHIAMA.'},
  {text:'Quando risponde, dì il tuo nome e “F1 Immobiliare”.'},
  {text:'Spiega in una frase perché la stai chiamando.'},
  {text:'Fai la domanda scritta nella scheda.'},
  {text:'Prima di chiudere, chiarisci cosa fare dopo.'},
  {text:'Scrivi subito il risultato.'}
 ],
 branches:[
  ['Non risponde','Scrivi NON RISPONDE.'],
  ['Chiede di essere richiamata','Apri PROGRAMMA UN RICHIAMO.'],
  ['Non vuole più contatti','Apri NON CHIAMARE PIÙ.'],
  ['Vuole sapere il valore o fissare un appuntamento','Apri PASSA LA PERSONA AL CONSULENTE.']
 ],
 record:['Data e ora','Risultato','Cosa ha detto','Cosa fare dopo'],
 stop:['Non chiamare se non c’è scritto CHIAMABILE.','Non richiamare chi ha chiesto di non essere contattato.'],
 script:'Apri il nome. Controlla che sia chiamabile. Leggi perché devi chiamare. Telefona. Presentati. Fai la domanda. Scrivi il risultato.'
},
{
 id:'followup',code:'F1-OG-041',stage:'RICHIAMO',title:'Programma un richiamo',
 role:'Tu, quando una persona accetta di essere ricontattata.',
 trigger:'La persona dice chiaramente che puoi chiamarla di nuovo.',
 doneWhen:'Hai scritto quando richiamarla, perché e chi deve farlo.',next:'end-shift',
 commands:[
  {text:'Apri la scheda della persona.'},
  {text:'Seleziona RICHIAMO AUTORIZZATO. Significa che la persona ha accettato un nuovo contatto.'},
  {text:'Scrivi la DATA del richiamo.'},
  {text:'Scrivi PERCHÉ devi richiamarla.'},
  {text:'Scrivi CHI deve fare la chiamata.'},
  {text:'Scrivi la prima cosa da chiedere quando la richiamerai.'},
  {text:'Premi SALVA.'}
 ],
 branches:[
  ['Dice “non ora” ma non dice di richiamare','Non programmare una nuova chiamata.'],
  ['Ti dà una data precisa','Usa quella data.'],
  ['Dice che non vuole più chiamate','Apri NON CHIAMARE PIÙ.']
 ],
 record:['Data del richiamo','Motivo','Chi deve chiamare','Prima domanda'],
 stop:['Non scrivere solo “RICHIAMARE”. Scrivi sempre quando e perché.'],
 script:'Apri la scheda. Segna che il richiamo è autorizzato. Scrivi quando, perché, chi deve chiamare e cosa chiedere. Salva.'
},
{
 id:'handoff',code:'F1-OG-050',stage:'PASSA IL CONTATTO',title:'Passa la persona al consulente',
 role:'Tu, quando una persona mostra interesse reale.',
 trigger:'La persona dice che potrebbe vendere, vuole sapere il valore o vuole un appuntamento.',
 doneWhen:'Il consulente riceve le informazioni necessarie.',next:'work-civic',
 commands:[
  {text:'Apri PASSA AL CONSULENTE.'},
  {text:'Scrivi NOME e TELEFONO solo se la persona li ha forniti.'},
  {text:'Scrivi quale CASA o ZONA riguarda.'},
  {text:'Scrivi CHI ti ha dato l’informazione.'},
  {text:'Scrivi CHE COSA HA DETTO la persona.'},
  {text:'Se ha detto quando pensa di muoversi, scrivi il periodo.'},
  {text:'Scegli cosa chiede: SAPERE IL VALORE / VENDERE / APPUNTAMENTO / ALTRO.'},
  {text:'Scrivi che cosa avete concordato come prossimo passo.'},
  {text:'Premi INVIA AL CONSULENTE.'}
 ],
 branches:[
  ['Hai sentito solo una voce','Non presentarla come persona interessata. Prima scrivi la voce come informazione.'],
  ['Chiede quanto vale casa','Segna PRIORITÀ ALTA.'],
  ['Avete già fissato un appuntamento','Scrivi giorno e ora esatti.']
 ],
 record:['Nome','Telefono se fornito','Casa o zona','Che cosa ha detto','Quando','Che cosa chiede','Prossimo passo'],
 stop:['Non aggiungere motivi o intenzioni che la persona non ha detto.'],
 script:'Apri passa al consulente. Scrivi nome, telefono, casa, cosa ha detto, cosa chiede e prossimo passo. Invia.'
},
{
 id:'do-not-contact',code:'F1-OG-060',stage:'NON CHIAMARE',title:'Non chiamare più questa persona',
 role:'Tu, quando una persona chiede di non essere più contattata.',
 trigger:'La persona lo dice chiaramente.',
 doneWhen:'Il nome non appare più nelle liste di chiamata.',next:'end-shift',
 commands:[
  {text:'Chiudi subito la conversazione commerciale.'},
  {text:'Apri la scheda della persona.'},
  {text:'Premi NON CONTATTARE / NON CHIAMARE.'},
  {text:'Scrivi la DATA.'},
  {text:'Scrivi dove lo ha chiesto: telefono / WhatsApp / email / di persona.'},
  {text:'Premi SALVA.'},
  {text:'Controlla che il nome non compaia più in CHIAMATE DI OGGI.'}
 ],
 branches:[
  ['È un conoscente che non deve essere chiamato per motivi operativi','Usa NON CHIAMARE OPERATIVO senza cancellare lo storico.']
 ],
 record:['Data','Come lo ha chiesto','Tuo nome'],
 stop:['Non cancellare lo storico solo per togliere il nome dalla lista.','Non rimettere manualmente il nome nella lista chiamate.'],
 script:'Chiudi la conversazione. Apri la scheda. Premi non contattare. Scrivi data e come lo ha chiesto. Salva.'
},
{
 id:'sign',code:'F1-OG-100',stage:'CARTELLO O ANNUNCIO',title:'Registra un cartello o un annuncio',
 role:'Tu, quando vedi pubblicamente una casa proposta in vendita o affitto.',
 trigger:'Vedi un cartello oppure trovi un annuncio pubblico.',
 doneWhen:'Hai scritto i dati visibili senza inventare ciò che manca.',next:'work-civic',
 commands:[
  {text:'Scrivi VIA e NUMERO DEL PALAZZO.'},
  {text:'Scegli: PRIVATO / AGENZIA / NON SI CAPISCE.'},
  {text:'Scrivi la DATA in cui lo hai visto.'},
  {text:'Se il prezzo è pubblico, scrivilo.'},
  {text:'Se hai trovato l’annuncio online, incolla il LINK.'},
  {text:'Se compare il nome di un’agenzia, scrivilo.'},
  {text:'Premi SALVA.'}
 ],
 branches:[
  ['In futuro l’annuncio non si trova più','Scrivi ANNUNCIO NON PIÙ VISTO.'],
  ['Il prezzo cambia','Scrivi la nuova cifra e la data.']
 ],
 record:['Via e numero','Privato/Agenzia/Non si capisce','Prezzo se pubblico','Link se esiste','Data'],
 stop:['Non scrivere “incarico scaduto” senza prova.','Non concludere che il proprietario voglia cambiare agenzia.'],
 script:'Scrivi indirizzo, chi pubblicizza, data, prezzo e link se pubblici. Salva. Non inventare altro.'
},
{
 id:'end-shift',code:'F1-OG-090',stage:'FINE GIORNATA',title:'Chiudi il lavoro di oggi',
 role:'Tu, prima di finire la giornata.',
 trigger:'Hai finito il lavoro o completato la missione.',
 doneWhen:'Tutto ciò che hai fatto è scritto e ogni richiamo ha data e motivo.',next:'start-shift',
 commands:[
  {text:'Apri RIEPILOGO DI OGGI.'},
  {text:'Controlla che ogni palazzo abbia un risultato scritto.'},
  {text:'Controlla che ogni informazione sia stata salvata.'},
  {text:'Controlla le PERSONE DA RICHIAMARE. Ognuna deve avere data e motivo.'},
  {text:'Controlla che chi ha chiesto di non essere chiamato sia fuori dalla lista.'},
  {text:'Scrivi eventuali problemi da mostrare al responsabile domani.'},
  {text:'Premi CHIUDI GIORNATA.'}
 ],
 branches:[
  ['Trovi un richiamo senza data o motivo','Apri la persona e completa i dati.'],
  ['Trovi una attività fatta ma non scritta','Scrivila prima di chiudere.']
 ],
 record:['Ora fine lavoro','Palazzi lavorati','Conversazioni','Informazioni raccolte','Richiami programmati','Problemi da segnalare'],
 stop:['Non chiudere la giornata lasciando attività senza risultato scritto.'],
 script:'Apri il riepilogo. Controlla palazzi, informazioni e richiami. Scrivi i problemi. Poi chiudi la giornata.'
}
];