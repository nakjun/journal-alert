from __future__ import annotations

import html
import re
from datetime import date
from typing import Iterable

import requests

from .config import JournalConfig
from .models import Paper


CROSSREF_URL = "https://api.crossref.org/works"
USER_AGENT = "slack-paper-alert/0.1 (mailto:example@example.com)"

MODALITY_TERMS: dict[str, tuple[str, ...]] = {
    "Mammography": (
        "mammography",
        "mammogram",
        "mammographic",
        "digital breast tomosynthesis",
        "breast tomosynthesis",
        "dbt",
    ),
    "Chest X-ray": (
        "chest x-ray",
        "chest xray",
        "chest radiograph",
        "chest radiography",
        "cxr",
    ),
    "Breast MRI": (
        "breast mri",
        "breast magnetic resonance",
        "breast dce-mri",
        "dynamic contrast-enhanced breast",
        "abbreviated breast mri",
    ),
}

METHOD_TERMS: dict[str, tuple[str, ...]] = {
    "Deep learning": (
        "deep learning",
        "neural network",
        "convolutional",
        "cnn",
        "transformer",
        "vision transformer",
        "self-supervised",
        "contrastive learning",
        "representation learning",
        "pre-training",
        "pretraining",
    ),
    "Machine learning": (
        "machine learning",
        "random forest",
        "support vector",
        "xgboost",
        "radiomics",
        "classifier",
        "classification model",
    ),
    "Generative AI": (
        "generative ai",
        "generative artificial intelligence",
        "foundation model",
        "large language model",
        "llm",
        "vision-language",
        "vision language",
        "report generation",
        "structured reasoning",
        "reinforcement",
        "prompt",
        "diffusion model",
        "generative adversarial",
        "gan",
        "synthetic image",
    ),
}


def search_papers(
    journals: Iterable[JournalConfig],
    from_date: date,
    to_date: date,
    rows_per_journal: int = 100,
) -> list[Paper]:
    papers: list[Paper] = []
    for journal in journals:
        works = _fetch_crossref_works(journal, from_date, to_date, rows_per_journal)
        for work in works:
            paper = _work_to_paper(work, journal)
            if paper:
                papers.append(paper)
    return _dedupe(papers)


def _fetch_crossref_works(
    journal: JournalConfig,
    from_date: date,
    to_date: date,
    max_rows: int,
) -> list[dict]:
    filters = [
        f"from-pub-date:{from_date.isoformat()}",
        f"until-pub-date:{to_date.isoformat()}",
        "type:journal-article",
    ]
    params = {
        "filter": ",".join(filters),
        "select": "DOI,title,author,published-print,published-online,published,container-title,abstract,URL,ISSN,subject",
        "rows": str(min(max_rows, 1000)),
        "sort": "published",
        "order": "desc",
    }

    if journal.issns:
        params["filter"] = params["filter"] + f",issn:{journal.issns[0]}"
    else:
        params["query.container-title"] = journal.name

    items = _fetch_with_cursor(params, max_rows)

    if journal.issns and len(journal.issns) > 1:
        for issn in journal.issns[1:]:
            next_params = dict(params)
            next_params["filter"] = ",".join(filters) + f",issn:{issn}"
            items.extend(_fetch_with_cursor(next_params, max_rows))

    return items


def _fetch_with_cursor(params: dict[str, str], max_rows: int) -> list[dict]:
    items: list[dict] = []
    cursor = "*"
    page_size = min(max_rows, 1000)

    while len(items) < max_rows:
        page_params = dict(params)
        page_params["rows"] = str(min(page_size, max_rows - len(items)))
        page_params["cursor"] = cursor

        response = requests.get(
            CROSSREF_URL,
            params=page_params,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        message = response.json().get("message", {})
        page_items = message.get("items", [])
        if not page_items:
            break

        items.extend(page_items)
        next_cursor = message.get("next-cursor")
        if not next_cursor or next_cursor == cursor or len(page_items) < page_size:
            break
        cursor = next_cursor

    return items[:max_rows]


def _work_to_paper(work: dict, journal_config: JournalConfig) -> Paper | None:
    title = _first(work.get("title"))
    abstract = _clean_abstract(work.get("abstract", ""))
    journal = _first(work.get("container-title")) or journal_config.name
    haystack = _normalize(" ".join([title, abstract, journal, " ".join(work.get("subject", []))]))

    modality = _match_terms(haystack, MODALITY_TERMS)
    method_family = _match_terms(haystack, METHOD_TERMS)
    if not modality or not method_family:
        return None

    return Paper(
        discovered_date=date.today().isoformat(),
        published_date=_published_date(work),
        journal=journal,
        modality=modality,
        method_family=method_family,
        title=title,
        authors=_authors(work.get("author", [])),
        doi=str(work.get("DOI", "")).strip(),
        url=str(work.get("URL", "")).strip(),
        abstract=abstract,
        source_api="Crossref",
        source_journal_config=journal_config.name,
    )


def _match_terms(text: str, term_map: dict[str, tuple[str, ...]]) -> str | None:
    matches: list[str] = []
    for label, terms in term_map.items():
        if any(_term_in_text(term, text) for term in terms):
            matches.append(label)
    return "; ".join(matches) if matches else None


def _term_in_text(term: str, text: str) -> bool:
    normalized_term = _normalize(term)
    if len(normalized_term) <= 4:
        return re.search(rf"\b{re.escape(normalized_term)}\b", text) is not None
    return normalized_term in text


def _published_date(work: dict) -> str:
    for key in ("published-online", "published-print", "published"):
        parts = work.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            values = [str(v).zfill(2) for v in parts[0]]
            if len(values) == 1:
                return values[0]
            if len(values) == 2:
                return f"{values[0]}-{values[1]}"
            return f"{values[0]}-{values[1]}-{values[2]}"
    return ""


def _authors(authors: list[dict]) -> str:
    names: list[str] = []
    for author in authors[:8]:
        given = author.get("given", "")
        family = author.get("family", "")
        name = " ".join(part for part in [given, family] if part).strip()
        if name:
            names.append(name)
    if len(authors) > 8:
        names.append("et al.")
    return ", ".join(names)


def _clean_abstract(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _first(values: object) -> str:
    if isinstance(values, list) and values:
        return str(values[0]).strip()
    if isinstance(values, str):
        return values.strip()
    return ""


def _normalize(value: str) -> str:
    value = value.lower().replace("-", " ")
    return re.sub(r"\s+", " ", value).strip()


def _dedupe(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    unique: list[Paper] = []
    for paper in papers:
        if paper.unique_key in seen:
            continue
        seen.add(paper.unique_key)
        unique.append(paper)
    return unique
