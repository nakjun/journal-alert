from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Paper:
    discovered_date: str
    published_date: str
    journal: str
    modality: str
    method_family: str
    title: str
    authors: str
    doi: str
    url: str
    abstract: str
    source_api: str
    source_journal_config: str

    @property
    def unique_key(self) -> str:
        if self.doi:
            return self.doi.lower().strip()
        return f"{self.title.lower().strip()}|{self.journal.lower().strip()}"

