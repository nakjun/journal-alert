from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote, urlparse

import requests


REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 journal-alert/0.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True)
class AbstractResult:
    abstract: str
    source: str
    final_url: str


def fetch_direct_abstract(url: str, doi: str = "", journal: str = "") -> AbstractResult | None:
    target_url = url or _doi_url(doi)
    if not target_url:
        return None

    final_url, text = _get_html(target_url)
    if not text:
        return None

    fetcher = _select_fetcher(final_url, doi, journal)
    if fetcher == "nature":
        abstract = _parse_nature_abstract(text)
    elif fetcher == "ieee":
        abstract = _parse_ieee_abstract(text)
    elif fetcher == "elsevier":
        abstract = _parse_elsevier_abstract(text)
        if not abstract:
            abstract = _fetch_sciencedirect_abstract(final_url)
        if not abstract:
            abstract = _fetch_pubmed_abstract_by_doi(doi)
    else:
        abstract = _parse_generic_abstract(text)

    if not abstract:
        return None
    return AbstractResult(abstract=abstract, source=f"Direct:{fetcher}", final_url=final_url)


def _select_fetcher(url: str, doi: str, journal: str) -> str:
    host = urlparse(url).netloc.lower()
    journal_lower = journal.lower()
    doi_lower = doi.lower()

    if "nature.com" in host or "nature" in journal_lower or "npj" in journal_lower:
        return "nature"
    if "ieeexplore.ieee.org" in host or "ieee" in journal_lower or doi_lower.startswith("10.1109/"):
        return "ieee"
    if (
        "elsevier" in host
        or "sciencedirect.com" in host
        or "medical image analysis" in journal_lower
        or doi_lower.startswith("10.1016/")
    ):
        return "elsevier"
    return "generic"


def _get_html(url: str) -> tuple[str, str]:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=30, allow_redirects=True)
        if response.status_code >= 400:
            return response.url, ""
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return response.url, ""
        return response.url, response.text
    except requests.RequestException:
        return url, ""


def _parse_nature_abstract(text: str) -> str:
    section = _extract_tag_content_by_id(text, "Abs1-content")
    if section:
        return section
    return _meta_content(text, ("dc.description", "description", "og:description", "twitter:description"))


def _parse_ieee_abstract(text: str) -> str:
    scripted = _parse_ieee_metadata_abstract(text)
    if scripted:
        return scripted
    return _meta_content(text, ("Description", "citation_abstract", "og:description", "twitter:description"))


def _parse_ieee_metadata_abstract(text: str) -> str:
    marker = "xplGlobal.document.metadata="
    start = text.find(marker)
    if start == -1:
        return ""

    json_start = start + len(marker)
    try:
        metadata, _ = json.JSONDecoder().raw_decode(text[json_start:])
    except json.JSONDecodeError:
        return ""

    abstract = metadata.get("abstract", "")
    if not isinstance(abstract, str):
        return ""
    return _clean_text(abstract)


def _parse_elsevier_abstract(text: str) -> str:
    abstract = _meta_content(text, ("citation_abstract", "dc.description", "description", "og:description"))
    if abstract:
        return abstract

    for pattern in (
        r'"abstracts"\s*:\s*\[\s*\{\s*"abstract"\s*:\s*"(?P<value>.*?)"',
        r'"abstract"\s*:\s*"(?P<value>.*?)"',
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_text(match.group("value"))
    return ""


def _fetch_sciencedirect_abstract(final_url: str) -> str:
    pii_match = re.search(r"/pii/([^/?#]+)", final_url)
    if not pii_match:
        return ""

    sciencedirect_url = f"https://www.sciencedirect.com/science/article/pii/{quote(pii_match.group(1))}"
    _, text = _get_html(sciencedirect_url)
    if not text:
        return ""
    return _parse_elsevier_abstract(text)


def _fetch_pubmed_abstract_by_doi(doi: str) -> str:
    doi = doi.strip()
    if not doi:
        return ""

    try:
        search_response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": f"{doi}[doi]", "retmode": "json"},
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        search_response.raise_for_status()
        ids = search_response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return ""

        fetch_response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": ids[0], "retmode": "xml"},
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        fetch_response.raise_for_status()
    except requests.RequestException:
        return ""

    try:
        root = ET.fromstring(fetch_response.text)
    except ET.ParseError:
        return ""

    parts: list[str] = []
    for node in root.findall(".//Abstract/AbstractText"):
        label = node.attrib.get("Label")
        text = _clean_text(" ".join(node.itertext()))
        if not text:
            continue
        parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts).strip()


def _parse_generic_abstract(text: str) -> str:
    return _meta_content(text, ("citation_abstract", "dc.description", "description", "og:description"))


def _meta_content(text: str, names: tuple[str, ...]) -> str:
    for name in names:
        pattern = (
            r'<meta[^>]+(?:name|property)=["\']'
            + re.escape(name)
            + r'["\'][^>]+content=["\'](?P<value>.*?)["\'][^>]*>'
        )
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = _clean_text(match.group("value"))
            if value:
                return value
    return ""


def _extract_tag_content_by_id(text: str, element_id: str) -> str:
    id_pattern = re.compile(r'<(?P<tag>[a-zA-Z0-9]+)[^>]+id=["\']' + re.escape(element_id) + r'["\'][^>]*>', re.I)
    match = id_pattern.search(text)
    if not match:
        return ""

    tag = match.group("tag")
    start = match.end()
    end_match = re.search(r"</" + re.escape(tag) + r">", text[start:], flags=re.IGNORECASE)
    if not end_match:
        return ""
    return _clean_text(text[start : start + end_match.start()])


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace(r"\/", "/")
    if re.search(r"\\[ux][0-9a-fA-F]+", value):
        try:
            value = bytes(value, "utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            pass
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _doi_url(doi: str) -> str:
    doi = doi.strip()
    if not doi:
        return ""
    return f"https://doi.org/{doi}"
