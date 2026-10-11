# AutoSearch

Cerca offerte su LinkedIn (endpoint pubblico guest, senza login) e concorsi pubblici su inPA,
filtra e dà un voto, deduplica, e le mostra in una pagina web locale con gestione candidature.

## Setup

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp config.example.yaml config.yaml   # poi personalizza

## Uso

Doppio click su **AutoSearch offerte** (Scrivania o menu): apre http://127.0.0.1:8765 con offerte,
avanzamento e pulsante di ricerca. Il server si chiude da solo dopo 15 min senza pagina aperta.

Da terminale:

    ./run.sh                                    # come il doppio click
    .venv/bin/python -m autosearch.web          # solo server web

    .venv/bin/python -m autosearch              # run normale
    .venv/bin/python -m autosearch --dry-run    # test: niente DB, output a console


## Windows

L'installer è già nella cartella che hai scaricato: doppio click su
**AutoSearch-Setup-1.0.0.exe**. Installa tutto (Python compreso, non serve installarlo a parte)
e mette *AutoSearch* sul Desktop e nel menu Start. Un click apre http://127.0.0.1:8765 come su
Linux. Non serve né scaricare altro né usare i comandi qui sotto.

L'installer non ha firma digitale, quindi Windows avvisa: **"Windows ha protetto il PC"** →
*Ulteriori informazioni* → *Esegui comunque*. Se invece compare **"App bloccata"** senza
alternative, sul PC è attivo *Smart App Control*: blocca ogni eseguibile non firmato e non ha
un'eccezione per singolo file. In quel caso usa l'avvio da sorgente qui sotto.

Configurazione e dati stanno in `%LOCALAPPDATA%\AutoSearch` (`config.yaml`, `data\jobs.db`,
`data\web.log`): restano al loro posto quando aggiorni o disinstalli. Per ricominciare da zero,
cancella quella cartella.

### Da sorgente (se l'installer viene bloccato)

Serve Python 3 (python.org, spunta "Add python.exe to PATH"). Poi doppio click su
**setup.bat**: crea l'ambiente, installa le dipendenze e mette *AutoSearch* sul Desktop,
pronto da usare. Se Windows lo blocca perché scaricato da internet, tasto destro su
`setup.bat` → Proprietà → spunta *Annulla blocco*.

Fa l'equivalente di questi comandi, se preferisci darli a mano da PowerShell:

    py -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\pythonw.exe windows\launcher.py

`setup.bat` si può rilanciare per aggiornare le dipendenze. Dopo un aggiornamento del codice
chiudi la pagina e aspetta 15 min (o termina `pythonw.exe` da Gestione attività) prima di
riaprire.

### Ricostruire l'installer

Serve Inno Setup (`winget install JRSoftware.InnoSetup`):

    powershell -ExecutionPolicy Bypass -File windows\build.ps1

Lo script crea il venv, installa le dipendenze, genera l'icona, impacchetta con PyInstaller
(`windows\autosearch.spec`), compila l'installer (`windows\installer.iss`) e aggiorna la copia
nella radice del repo, che è quella distribuita. Alzando la versione va cambiata in tre punti:
`windows\installer.iss`, `windows\version.txt` e il nome del file citato sopra in questo README.

## Note

- Endpoint non ufficiale: l'HTML di LinkedIn può cambiare e rompere il parser (`autosearch/sources/linkedin.py`).
- Non disponibili: Indeed, Glassdoor, Jooble, Bakeca bloccano le richieste automatiche; InfoJobs Italia ha chiuso.
  Adzuna e Careerjet hanno API ufficiali ma serve registrarsi per una chiave.
- Tieni basso il volume di richieste (delay, max_results) per evitare HTTP 429.
- Log: `data/web.log` (su Windows installato: `%LOCALAPPDATA%\AutoSearch\data\web.log`).
- Avvisi: se LinkedIn o inPA non restituiscono risultati, rispondono con errori o limitano le
  richieste, la pagina lo segnala dopo la ricerca (probabile cambio del sito: va aggiornato il parser).
- Backup: a ogni ricerca copia del database in `data/backup/` (ultimi 10 giorni). Per ripristinare:
  chiudi la pagina, copia il backup scelto su `data/jobs.db`.
- Esporta: pulsante "Esporta Excel" nella pagina (CSV con stato, note, RAL, link).
- Doppioni: annunci con titolo quasi uguale, stessa città e descrizione simile vengono mostrati come uno solo.
- Ricerca automatica: in Impostazioni scegli giorni e orari (ora italiana). Parte solo se il programma è
  acceso: sul server sempre; sul PC, con la ricerca automatica attiva, non si chiude più da solo dopo 15 min.
- Nuove sorgenti: implementa il protocollo in `autosearch/sources/base.py`.

## Server (es. CT Debian su Proxmox)

    apt install -y git python3-venv
    git clone https://github.com/drakmanga/AutoSearch.git /opt/autosearch && cd /opt/autosearch
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp config.example.yaml config.yaml
    cp autosearch.service /etc/systemd/system/ && systemctl enable --now autosearch

Pagina su http://<ip>:8765, raggiungibile da tutta la LAN (nessun login: non esporla su internet, usa una VPN).
Log: `journalctl -u autosearch -f`. Aggiornare: `git pull && systemctl restart autosearch`.
