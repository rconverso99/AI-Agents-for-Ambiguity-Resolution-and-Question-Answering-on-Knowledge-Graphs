

Rappresentazione Stato della Conversazione

Per quanto riguarda la rappresentazione della conversazione tra utente e chatbot, inserirò qui sotto tutti gli aggiornamenti.
Per ora ho integrato tutto il sistema della rappresentazione semantica e sintattica delle frasi che abbiamo realizzato io e ANTONIO DI GERONIMO al task di "Rappresentazione Stato della Conversazione", tramite **LangGraph**.

Di seguito vi condivido un esempio di interazione semplice (domanda -> risposta).

**User:** Posso prendere la tachipirina dopo i pasti?

**System:** La tachipirina può essere assunta dopo i pasti.

Grafo generato:

<img width="1301" height="846" alt="image" src="https://github.com/user-attachments/assets/3958dfb6-31ca-4f62-b8e5-6ef4e1bfb101" />


Solo per fare testing, mi sono limitato a far generare all'LLM la risposta alla domanda, quindi escludendo per ora completamente la parte di estrazione delle informazioni dal database che mi fornirà ANTONIO DI GERONIMO.

Inoltre nel flusso di esecuzione su LangGraph ho aggiunto sia il caso in cui il chatbot dovrà solo rispondere alla domanda e sia il caso in cui dovrà aggiornare la conoscenza contenuta nel DB.

Vi allego la struttura realizzata in LangGraph:

<img width="536" height="743" alt="image" src="https://github.com/user-attachments/assets/aae0e715-8e39-4879-8a5f-7e5f0b3eeb56" />


Nei prossimi giorni mi occuperò di:

1.  Gestire il caso di domande o frasi ambigue, dando la possibilità al chatbot di interrompere il flusso e di chiedere all'utente delucidazioni. (prepariamoci ad una struttura di LangGraph ancora più complessa ![😡](https://statics.teams.cdn.office.net/evergreen-assets/personal-expressions/v2/assets/emoticons/angryface/default/30_f.png?v=v21))
2.  Effettuare qualche test con un database reale, quindi facendo rispondere l'LLM con un supporto di qualche corpus di testo, in attesa che Antonio mi fornisce un suo DB per il testing
3.  Aggiungere timestamp della conversazione



**Aggiornamento: Gestione domande o frasi ambigue**
Mediante l'aggiunta di ulteriori nodi in LangGraph, adesso il sistema è in grado di riconoscere se gli viene fornita una frase ambigua.
Ricevuta la frase genera tutte le possibili interpretazioni e le aggiunge al grafo dello stato della conversazione.
Una volta aggiunte rileva che ci sono più interpretazioni della frase e genera una *domanda di chiarimento* da fornire all'utente.
Di seguito vi condivido la struttura LangGraph attuale (più passano i giorni e più si complica :P )
<img width="784" height="622" alt="image" src="https://github.com/user-attachments/assets/00e12489-0ab1-49b6-a708-536b03036a0d" />


Esempio:
*"Anna guarda Francesco mentre attraversa la strada"*
 
Anna guarda Franscesco mentre ANNA attraversa la strada:
<img width="1416" height="877" alt="image" src="https://github.com/user-attachments/assets/40a4155e-c2bc-4ac7-a0f9-d8e7ac190942" />

Anna guarda Francesco mentre FRANCESCO attraversa la strada: 
<img width="1416" height="877" alt="image" src="https://github.com/user-attachments/assets/d2405f64-115c-4732-aa98-a8b6eb23f513" />

**Domanda di chiarimento:** *Non mi è chiaro, chi sta attraversando la strada, Anna o Francesco?*
<img width="1416" height="877" alt="image" src="https://github.com/user-attachments/assets/d8c23f58-9b56-4ead-8695-473faff0eb54" />


**Aggiornamento: Gestione ambiguità ed eliminazione interpretazioni errate dal grafo**
Nell'ultimo aggiornamento eravamo rimasti alla generazione delle interpretazioni da parte del sistema con il relativo aggiornamento del grafo.
In questa settimana ho lavorato riguardo il tentativo di disambiguare la frase o domanda fornita dall'utente, vi mostro un esempio con la frase ambigua vista settimana scorsa.
 
*Frase: Marco guarda Luca mentre attraversa la strada*
Nell'ultimo aggiornamento eravamo rimasti ad una struttura del genere:
<img width="1350" height="648" alt="image" src="https://github.com/user-attachments/assets/0b250bc4-ccae-4cb8-869d-abec4d14a142" />

In questa struttura possiamo notare come da una delle due interpretazioni otteniamo che **Luca-[ACTS]-attraversare**, mentre dall'altra interpretazione otteniamo che è Marco ad attraversare la strada.
 
Adesso supponiamo che, dopo la domanda di chiarimento del sistema (Non mi è chiaro, Marco sta attraversando la strada o Luca sta attraversando la strada?) l'utente risponda con "Marco".
 
Di conseguenza otteniamo questa nuova struttura modificata:
<img width="1199" height="669" alt="image" src="https://github.com/user-attachments/assets/c2d01fab-11b4-4860-a50f-ea7f1696511e" />

 
Possiamo notare come la relazione **Luca-[ACTS]->attraversare** sia del tutto sparita dal grafo, e anche l'interpretazione da cui avevamo dedotto questo è stata completamente eliminata dal grafo.

La struttura in LangGraph ha subito una piccola modifica.
Abbiamo deciso di separare in due grafi differenti la gestione del dialogo e l'aggiornamento del grafo in Neo4j.
La gestione del dialogo è la seguente:
<img width="784" height="750" alt="image" src="https://github.com/user-attachments/assets/3ec389cb-c02c-4a68-a0ac-fdb7b4efafe1" />


L'aggiornamento del grafo in Neo4j invece è questa:

<img width="337" height="531" alt="image" src="https://github.com/user-attachments/assets/612033e5-fcb4-40db-ac29-25165a75434e" />




