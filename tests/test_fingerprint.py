from datetime import date

from job_trawler.fingerprint import fingerprint, normalize, normalize_company
from job_trawler.models import Posting


def job(company="The Thirsty Crow", title="Bartender", location="Los Angeles, CA",
        url="https://a.example/1", posted_on=date(2026, 11, 12)) -> Posting:
    return Posting(source="t", url=url, title=title, company=company, location=location,
                   posted_on=posted_on)


def test_normalize_strips_case_punctuation_accents_and_leading_the():
    assert normalize("The Café & Bar!") == "cafe and bar"


def test_company_suffixes_are_dropped():
    assert normalize_company("The Thirsty Crow, LLC.") == "thirsty crow"
    assert normalize_company("Acme Inc") == "acme"


def test_same_job_on_two_boards_matches():
    a = job(url="https://indeed.com/x")
    b = job(company="Thirsty Crow LLC", url="https://ziprecruiter.com/y")
    assert fingerprint(a) == fingerprint(b)


def test_repost_with_new_date_is_the_same_job():
    assert fingerprint(job(posted_on=date(2026, 11, 1))) == fingerprint(job(posted_on=date(2026, 11, 12)))


def test_title_punctuation_variants_match():
    assert fingerprint(job(title="Bartender (Part-Time)")) == fingerprint(job(title="Bartender - Part Time"))


def test_different_title_is_a_different_job():
    assert fingerprint(job(title="Barback")) != fingerprint(job(title="Bartender"))


def test_same_chain_in_another_city_is_a_different_job():
    assert fingerprint(job(location="Pasadena, CA")) != fingerprint(job(location="Los Angeles, CA"))


def test_missing_company_falls_back_to_url():
    a = job(company=None, url="https://a.example/1")
    b = job(company=None, url="https://a.example/2")
    assert fingerprint(a) != fingerprint(b)
    assert fingerprint(a) == fingerprint(job(company=None, url="https://a.example/1", title="Other"))
