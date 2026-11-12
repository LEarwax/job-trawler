"""Fingerprint: decides whether two postings are "the same job".

Pure functions, no I/O. The rule is deliberately simple and deterministic:

    same job  <=>  same normalized (company, title, city)

The posting date is NOT part of it, so a weekly re-post of the same listing
counts as the same job. When the company is missing we can't compare content,
so we fall back to the URL.

Cost of a miss: you see one job twice. Cost of a false match: you never see a
job. So normalization stays conservative; it only removes noise that can't
change meaning (case, punctuation, accents, "The", "LLC").
"""

import hashlib
import re
import unicodedata

from job_trawler.models import Posting

_COMPANY_SUFFIXES = {"llc", "inc", "incorporated", "co", "corp", "corporation", "ltd", "lp", "llp"}


def normalize(text: str | None) -> str:
    """'The Thirsty Crow, LLC.' -> 'thirsty crow llc' (suffixes are handled separately)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))  # café -> cafe
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)                          # punctuation -> space
    words = text.split()
    if words[:1] == ["the"]:
        words = words[1:]
    return " ".join(words)


def normalize_company(name: str | None) -> str:
    words = normalize(name).split()
    while words and words[-1] in _COMPANY_SUFFIXES:
        words.pop()
    return " ".join(words)


def city_of(location: str | None) -> str:
    """'Los Angeles, CA' -> 'los angeles'. Only the part before the first comma."""
    if not location:
        return ""
    return normalize(location.split(",")[0])


def fingerprint(p: Posting) -> str:
    company = normalize_company(p.company)
    if company:
        key = f"job|{company}|{normalize(p.title)}|{city_of(p.location)}"
    else:
        key = f"url|{p.url}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]
