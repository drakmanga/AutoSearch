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


## Note

- Endpoint non ufficiale: l'HTML di LinkedIn può cambiare e rompere il parser (`autosearch/sources/linkedin.py`).
- Non disponibili: Indeed, Glassdoor, Jooble, Bakeca bloccano le richieste automatiche; InfoJobs Italia ha chiuso.
  Adzuna e Careerjet hanno API ufficiali ma serve registrarsi per una chiave.
- Tieni basso il volume di richieste (delay, max_results) per evitare HTTP 429.
- Log: `data/web.log`.
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
