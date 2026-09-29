"""LinkedIn gives English place names: "Rome, Latium, Italy" -> "Roma, Lazio"."""
import re

PLACES = {
    "rome": "Roma", "latium": "Lazio", "italy": "Italia", "milan": "Milano", "lombardy": "Lombardia",
    "turin": "Torino", "piedmont": "Piemonte", "naples": "Napoli", "florence": "Firenze", "tuscany": "Toscana",
    "venice": "Venezia", "genoa": "Genova", "sicily": "Sicilia", "sardinia": "Sardegna", "apulia": "Puglia",
    "padua": "Padova", "mantua": "Mantova", "syracuse": "Siracusa", "leghorn": "Livorno",
}
METRO = re.compile(r"^Greater (.+?) (?:Metropolitan )?Area$", re.I)


def italian(location: str) -> str:
    if not location:
        return ""
    if m := METRO.match(location.strip()):
        return f"{PLACES.get(m.group(1).lower(), m.group(1))} (area metropolitana)"
    parts = [PLACES.get(p.strip().lower(), p.strip()) for p in location.split(",")]
    if len(parts) > 1 and parts[-1] == "Italia":
        parts.pop()  # "Roma, Lazio" is enough
    return ", ".join(parts)
