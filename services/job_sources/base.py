"""Base-Class für Job-Source-Adapter."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod


@dataclass
class FetchedJob:
    """Strukturiertes Roh-Result aus einer Source."""
    external_id: str
    title: str
    url: str
    company: str | None = None
    location: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    raw: dict = field(default_factory=dict)


class JobSourceAdapter(ABC):
    """Abstract Adapter; jede Source implementiert fetch()."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def fetch(self) -> list[FetchedJob]:
        """Lädt aktuelle Jobs von der Quelle. Wirft bei HTTP-Fehler."""
        raise NotImplementedError
