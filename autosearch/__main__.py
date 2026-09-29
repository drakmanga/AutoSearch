import argparse
import logging
import os
from collections import Counter
from datetime import datetime

from . import config, filters
from .runstate import RunState
from .sources.inpa import InPA
from .sources.linkedin import LinkedIn
from .storage import Store

log = logging.getLogger("autosearch")
SOURCES = {"linkedin": LinkedIn, "inpa": InPA}


class AlreadyRunning(Exception):
    pass


def run(cfg: config.Config, dry_run: bool = False, state: dict | None = None, progress=lambda: None) -> list:
    """Run all searches. `state` is updated in place with progress; `progress()` is called after each update."""
    state = state if state is not None else {}
    store = Store(cfg.db_path)
    sources = {}
    matches = []
    raw, no_title, fetched, no_desc = Counter(), 0, 0, 0  # for health warnings
    state.update(total=len(cfg.searches), step=0, checked=0, matches=0, top=0, warnings=[])
    progress()

    for i, search in enumerate(cfg.searches):
        source = sources.get(search.source) or sources.setdefault(
            search.source, SOURCES[search.source](delay=cfg.request_delay_seconds))
        where = search.location or "Italia"
        log.info("search: [%s] %s / %s", search.source, search.keywords, where)
        state.update(step=i, label=f"{search.keywords} — {where} ({search.source})")
        progress()
        for job in source.search(search):
            raw[search.source] += 1
            no_title += not job.title
            if store.seen(job) or any(m.source == job.source and m.id == job.id for m in matches):
                continue
            state["checked"] += 1
            if search.location_must_contain and not filters.location_matches(job.location, search.location_must_contain):
                continue  # not stored: may still come back via another search (e.g. remote)
            if cfg.fetch_descriptions and not job.description:
                job.description = source.fetch_description(job)
                fetched += 1
                no_desc += not job.description
            job.remote_only = search.remote == ["remote"]
            ok = filters.evaluate(job, cfg.filters)
            if not dry_run:
                store.add(job, ok)
            if ok:
                matches.append(job)
                state["matches"] = len(matches)
                state["top"] = sum(is_top(m, cfg) for m in matches)
            progress()

    state["step"] = len(cfg.searches)
    state["warnings"] = health_warnings(cfg, sources, raw, no_title, fetched, no_desc)
    for w in state["warnings"]:
        log.warning(w)
    log.info("%d matches", len(matches))
    if dry_run:
        for m in sorted(matches, key=lambda m: -m.score):
            print(f"{m.score:3}  {m.title} — {m.company} ({m.location})\n     {m.url}")
    return matches


NAMES = {"linkedin": "LinkedIn", "inpa": "inPA"}


def health_warnings(cfg, sources: dict, raw: Counter, no_title: int, fetched: int, no_desc: int) -> list[str]:
    """Signals that a site changed or blocked us, so an empty result is not mistaken for 'no jobs today'."""
    warnings = []
    for name, src in sources.items():
        n_searches = sum(s.source == name for s in cfg.searches)
        if raw[name] == 0:
            if src.failed:
                warnings.append(f"{NAMES[name]} non ha risposto correttamente ({src.failed} richieste fallite): "
                                "controlla la connessione e riprova più tardi. Se si ripete, il sito potrebbe "
                                "aver cambiato indirizzo o bloccato le richieste.")
            else:
                warnings.append(f"{NAMES[name]} non ha restituito nessun risultato su {n_searches} ricerche: "
                                "potrebbe aver cambiato il sito. Se si ripete, il programma va aggiornato.")
        elif src.failed:
            warnings.append(f"{NAMES[name]}: {src.failed} richieste non riuscite, alcuni risultati potrebbero mancare.")
        if src.rate_limited:
            warnings.append(f"{NAMES[name]} ha rallentato le richieste ({src.rate_limited} volte): "
                            "alcune ricerche potrebbero essere incomplete. Riprova più tardi.")
    total = sum(raw.values())
    if total >= 5 and no_title > total / 2:
        warnings.append(f"{no_title} offerte su {total} senza titolo: il sito potrebbe aver cambiato la pagina.")
    if fetched >= 5 and no_desc > fetched / 2:
        warnings.append(f"Descrizione non letta per {no_desc} offerte su {fetched}: voti poco affidabili, "
                        "il sito potrebbe aver cambiato la pagina.")
    return warnings


def is_top(job, cfg: config.Config) -> bool:
    """Grade A: high score and not asking more experience than allowed."""
    too_senior = cfg.filters.max_years and (job.years or 0) > cfg.filters.max_years
    return job.score >= cfg.grades.get("A", 10) and not too_senior


def run_tracked(cfg: config.Config) -> list:
    """Run with progress saved to data/status.json (read by the web UI). One search at a time."""
    status = RunState(cfg.db_path)
    if status.busy():
        raise AlreadyRunning()
    try:
        Store(cfg.db_path).backup()
    except Exception as e:  # a failed backup must not block the search
        log.warning("backup failed: %s", e)
    state = {"running": True, "pid": os.getpid(), "error": None,
             "started_at": datetime.now().isoformat(timespec="seconds")}
    status.save(state)
    try:
        return run(cfg, state=state, progress=lambda: status.save(state))
    except Exception as e:
        state["error"] = str(e)
        raise
    finally:
        state.update(running=False, finished_at=datetime.now().isoformat(timespec="seconds"))
        status.save(state)


def main() -> None:
    p = argparse.ArgumentParser(prog="autosearch")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("--dry-run", action="store_true", help="no DB writes, console output only")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config.load(args.config)
    if args.dry_run:
        run(cfg, dry_run=True)
        return
    try:
        run_tracked(cfg)
    except AlreadyRunning:
        log.info("a search is already running, skipping")


if __name__ == "__main__":
    main()
