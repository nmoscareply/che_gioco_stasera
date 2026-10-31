# Che gioco stasera?

Pagina web statica che filtra la tua collezione BoardGameGeek per giocatori, durata, esperienza del gruppo e meccaniche. Una GitHub Action scarica la collezione ogni notte. Non servono server né chiavi esposte.

## File

- `index.html` e `filter.js`: la pagina e la logica di filtro
- `data/collection.json`: dati per la pagina (generato dalla Action)
- `data/collection.txt`: una riga per gioco, da leggere con un agente LLM (generato dalla Action)
- `scripts/sync_bgg.py`: scarica collezione e dettagli da BGG
- `.github/workflows/sync.yml`: aggiornamento notturno
- `tests/test_all.py`: test di parsing e filtri (`python tests/test_all.py`, serve Node)

I dati presenti nel pacchetto sono di esempio (14 giochi): vengono sostituiti dalla tua collezione al primo avvio della Action.

## Messa online

1. Crea un repository su GitHub (pubblico va bene) e carica tutti i file di questa cartella.
2. Vai in **Settings > Secrets and variables > Actions > New repository secret**. Nome `BGG_TOKEN`, valore il tuo token BGG. Il token resta nei Secrets e non compare mai nel repository né nella pagina.
3. Facoltativo: nella scheda **Variables** crea `BGG_USERNAME` se vuoi un utente diverso da `nkbobo`.
4. Vai in **Settings > Actions > General > Workflow permissions** e scegli **Read and write permissions**, altrimenti la Action non può salvare i dati.
5. Vai in **Actions > Aggiorna collezione BGG > Run workflow**. Con 410 giochi servono circa 3-5 minuti.
6. Vai in **Settings > Pages**, scegli **Deploy from branch**, branch `main`, cartella `/ (root)`.

Dopo un minuto trovi:

- la pagina: `https://TUOUTENTE.github.io/NOMEREPO/`
- il file per l'agente: `https://TUOUTENTE.github.io/NOMEREPO/data/collection.txt`

## Se qualcosa non va

- La Action fallisce con 401: il secret `BGG_TOKEN` manca o è sbagliato.
- La Action fallisce con "Collezione vuota": la collezione BGG non è pubblica o lo username è sbagliato.
- La pagina mostra i dati di esempio: la Action non è ancora andata a buon fine.
