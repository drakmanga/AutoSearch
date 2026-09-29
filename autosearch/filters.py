import re

from .config import Filters
from .models import Job

# Sentence mentioning a language counts as a requirement unless it also has an optional marker.
REQUIRED = re.compile(
    r"fluen|native|required|mandatory|must|proficien|\bc1\b|\bc2\b|madrelingua|ottim|"
    r"richiest|necessari|obbligatori|padronanza|indispensabil|essential"
)
OPTIONAL = re.compile(
    r"\bplus\b|prefer|nice to have|desirabl|advantage|bonus|gradit|preferenzial|"
    r"apprezzat|vantaggio|costituir|facoltativ|optional"
)
SENTENCE_SPLIT = re.compile(r"[.\n;•·]+")


def requires_language(text: str, languages: list[str]) -> str | None:
    """Return the first language the text requires (not merely prefers), if any."""
    for sentence in SENTENCE_SPLIT.split(text):
        for lang in languages:
            if lang in sentence and REQUIRED.search(sentence) and not OPTIONAL.search(sentence):
                return lang
    return None


# Mentions of the employment contract itself ("contratto a tempo indeterminato", "CCNL", "temporary contract")
# appear in almost every posting: they must not count as contract-management keywords.
EMPLOYMENT_CONTRACT = re.compile(
    r"(?:tipo(?:logia)?|forma|inquadramento)\s+(?:di\s+|del\s+)?contratt\w*[^.\n]{0,40}"
    r"|contratt\w*\s*(?:di\s+lavoro|a\s+tempo|a\s+termine|di\s+somministrazione|collettiv\w*|nazional\w*|iniziale"
    r"|full[- ]?time|part[- ]?time|(?:in)?determinato|di\s+apprendistato|di\s+stage|diretto|:)[^.\n]{0,40}"
    r"|\bccnl\b[^.\n]{0,40}"
    r"|(?:temporary|permanent|fixed[- ]term|full[- ]time|part[- ]time|\d+[- ]months?)\s+contract"
    r"|contract\s+(?:type|duration|length)[^.\n]{0,30}",
    re.I,
)


def score(job: Job, weights: dict[str, int]) -> tuple[int, list[dict]]:
    """Sum keyword weights; a keyword in the title counts double.
    Word-start match: "contratt" hits "contrattuale", "erp" does not hit "interprete".
    Returns (score, breakdown) where breakdown lists each keyword found and its points."""
    title = EMPLOYMENT_CONTRACT.sub(" ", job.title.lower())
    desc = EMPLOYMENT_CONTRACT.sub(" ", job.description.lower())
    total, breakdown = 0, []
    for word, weight in weights.items():
        rx = re.compile(r"\b" + re.escape(word.lower()) + r"\w*")
        if m := rx.search(title):
            where, points = "titolo", 2 * weight
        elif m := rx.search(desc):
            where, points = "descrizione", weight
        else:
            continue
        total += points
        breakdown.append({"word": word, "match": m.group(0), "where": where, "weight": weight, "points": points})
    return total, breakdown


def evaluate(job: Job, f: Filters) -> bool:
    """Score job in place (score, reasons, salary). Return True if it passes filters."""
    title = job.title.lower()
    text = f"{title} {job.description.lower()}"
    company = job.company.lower()
    job.salary = job.salary or extract_salary(job.description)
    job.score, job.breakdown = score(job, f.nice_to_have)
    job.reasons = [b["word"] for b in job.breakdown]
    job.years = extract_years(job.description)
    job.workplace = workplace(job)

    if any(c.lower() in company for c in f.exclude_companies):
        return False
    if any(w.lower() in title for w in f.exclude_title):
        return False
    if any(w.lower() in text for w in f.exclude):
        return False
    if requires_language(text, [l.lower() for l in f.exclude_required_languages]):
        return False
    if not all(w.lower() in text for w in f.must_have):
        return False
    if job.remote_only and not is_remote(job):
        return False
    if f.max_years and f.years_action == "exclude" and (job.years or 0) > f.max_years:
        return False
    return job.score >= f.min_score


def location_matches(location: str, words: list[str]) -> bool:
    """Whole-word match: "Roma" must not hit "Emilia Romagna"."""
    return any(re.search(rf"\b{re.escape(w.lower())}\b", location.lower()) for w in words)


# Years of experience required: "almeno 5 anni di esperienza", "esperienza di 3-5 anni",
# "esperienza triennale", "5+ years of experience". Ranges count by their lower bound.
_N = r"(\d{1,2})\s*\+?(?:\s*(?:-|–|/|a|o|to)\s*\d{1,2})?\s*\+?"
YEARS = [
    re.compile(rf"{_N}\s*ann[io]\b[^.\n]{{0,25}}?esperienz", re.I),
    re.compile(rf"esperienz[^.\n]{{0,40}}?(?:almeno|minim[oa]|di|da|oltre|superiore a)\s*{_N}\s*ann", re.I),
    re.compile(rf"{_N}\s*years?\b[^.\n]{{0,30}}?experience", re.I),
    re.compile(rf"experience[^.\n]{{0,30}}?(?:at least|minimum of|min\.?|of)\s*{_N}\s*years?", re.I),
]
WORD_YEARS = re.compile(r"esperienz[^.\n]{0,30}?\b(biennale|triennale|quadriennale|quinquennale|decennale)", re.I)
WORD_VALUES = {"biennale": 2, "triennale": 3, "quadriennale": 4, "quinquennale": 5, "decennale": 10}


def extract_years(text: str) -> int | None:
    """Highest minimum experience requirement stated, ignoring sentences marked optional."""
    found = []
    for sentence in SENTENCE_SPLIT.split(text or ""):
        if OPTIONAL.search(sentence.lower()):
            continue
        for rx in YEARS:
            found += [int(m.group(1)) for m in rx.finditer(sentence)]
        found += [WORD_VALUES[m.group(1).lower()] for m in WORD_YEARS.finditer(sentence)]
    found = [n for n in found if 0 < n <= 15]  # "azienda con 30 anni di esperienza" is not a requirement
    return max(found) if found else None


# Salary: an amount (or range) shortly after a salary word. "30.000", "30,000 €", "€ 30.000", "30k", "30-35k".
_AMOUNT = r"(?:€\s?)?\d{1,3}(?:[.,'’]\d{3})+(?:,\d{2})?(?:\s?(?:€|(?:euro|eur)\b))?|(?:€\s?)?\d{2,3}\s?k\b(?:\s?(?:€|(?:euro|eur)\b))?"
SALARY = re.compile(
    r"(?:\bral\b|r\.a\.l\.|retribuzione|stipendio|salary|compenso|compensation|inquadramento economico)"
    r"[^\n]{0,60}?"
    rf"(\d{{2,3}}\s?[-–—]\s?\d{{2,3}}\s?k\b|(?:{_AMOUNT})(?:\s?(?:-|–|—|a|to|e|fino a)\s?(?:{_AMOUNT}))?)"
    r"([^\n]{0,25})",
    re.I,
)
MONTHLY = re.compile(r"mensil|mese|month", re.I)


def extract_salary(text: str) -> str:
    m = SALARY.search(text or "")
    if not m:
        return ""
    amount = re.sub(r"\s*[-–—]\s*", " – ", m.group(1).strip())
    return amount + (" /mese" if MONTHLY.search(m.group(0)) else "")


# Workplace is not provided by the sources (LinkedIn guest API even ignores its own filter f_WT):
# it is inferred from the posting text. Order matters: full remote > "no smart working" > hybrid > remote > on-site.
FULL_REMOTE = re.compile(r"full[ -]?remote|fully remote|100% ?(?:da )?remot|(?:completamente|totalmente|interamente) (?:da |in )?remot")
# "non è previsto smart working", "no smartworking": on-site
NO_REMOTE = re.compile(r"(?:\bno|\bnon\s+(?:è\s+)?previst[oa]|\bsenza)\s+(?:lo\s+|lavoro\s+)?(?:smart[ -]?working|telelavoro|lavoro agile|remote)")
_WFH = r"(?:telelavoro|smart ?working|lavoro agile|da remoto|da casa)"
_DAYS = r"(?:\d+|un[oa]?|due|tre|quattro)\s+giorn\w*"
HYBRID = re.compile(
    r"hybrid|modalit\w*\s+(?:di\s+lavoro\s+)?ibrid|lavoro\s+ibrid|formula\s+ibrid|\bibrid[oa]\s*\("
    r"|smart[ -]?working|lavoro agile|days? (?:a week )?(?:in|from) (?:the )?office"
    rf"|{_DAYS}\s+(?:a settimana\s+)?(?:in|da)\s+(?:sede|ufficio|remoto|casa)"
    rf"|{_WFH}[^.\n]{{0,25}}{_DAYS}|{_DAYS}[^.\n]{{0,20}}{_WFH}"
)
REMOTE = re.compile(r"(?:da|in) remoto|lavoro remoto|telelavoro|work(?:ing)? from home|\bwfh\b"
                    r"|remote(?:[- ]first| work| working| position| role| job| contract)")
REMOTE_HEADER = re.compile(r"\bremote\b|\bremoto\b")  # title/location only: "Remote", "Italia (remoto)"
ONSITE = re.compile(r"on[- ]?site|in sede\b|in presenza|presso (?:la (?:nostra )?sede|i nostri uffici|il cliente|lo stabilimento)"
                    r"|lavoro in ufficio|in office\b")

WORKPLACE_LABEL = {"remote": "Da remoto", "hybrid": "Ibrido", "onsite": "In sede", "": "Non indicata"}


def workplace(job: Job) -> str:
    """remote | hybrid | onsite | "" (not stated)."""
    text = f"{job.title} {job.location} {job.description}".lower()
    if FULL_REMOTE.search(text):
        return "remote"
    if NO_REMOTE.search(text):
        return "onsite"
    if HYBRID.search(text):
        return "hybrid"
    if REMOTE.search(text) or REMOTE_HEADER.search(f"{job.title} {job.location}".lower()):
        return "remote"
    if ONSITE.search(text) or job.source == "inpa":  # public competitions are on-site
        return "onsite"
    return ""


def is_remote(job: Job) -> bool:
    return workplace(job) == "remote"
