# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Service für Web-basierte Forschung zu KI-verdächtigen Wörtern.

Scraped arbeits-abc.de wöchentlich nach neuen KI-Tabu-Wörtern und erkennt
neue Wörter durch Vergleich mit bestehenden Einträgen.
"""

from __future__ import annotations
import logging
import requests
from html.parser import HTMLParser
from typing import Set, Optional

logger = logging.getLogger(__name__)


class AIWordsHTMLParser(HTMLParser):
    """Parser für HTML-Extraktion von KI-Tabu-Wörtern aus arbeits-abc.de."""
    
    def __init__(self):
        super().__init__()
        self.words = set()
        self.in_list = False
        self.current_li_text = ''
    
    def handle_starttag(self, tag: str, attrs: list):
        if tag == 'ul':
            self.in_list = True
        elif tag == 'li' and self.in_list:
            self.current_li_text = ''
    
    def handle_endtag(self, tag: str):
        if tag == 'li' and self.in_list and self.current_li_text.strip():
            # Normalisieren: lowercase, whitespace trimmen
            word = self.current_li_text.strip().lower()
            if word:
                self.words.add(word)
            self.current_li_text = ''
        elif tag == 'ul':
            self.in_list = False
    
    def handle_data(self, data: str):
        if self.in_list:
            self.current_li_text += data


class AIWordsResearchService:
    """Service für automatische Forschung zu KI-verdächtigen Wörtern."""
    
    ARBEITS_ABC_URL = 'https://arbeits-abc.de/ki-tabu-worter/'
    REQUEST_TIMEOUT = 30
    
    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = timeout
    
    def scrape_arbeits_abc(self) -> Set[str]:
        """Scraped arbeits-abc.de und extrahiert KI-Tabu-Wörter.
        
        Versucht, die HTML-Seite zu fetchen und alle <li>-Elemente aus
        <ul>-Listen zu extrahieren. Wörter werden normalisiert (lowercase).
        
        Returns:
            Set von Wörtern (lowercase, trimmed).
        
        Raises:
            requests.RequestException: Wenn HTTP-Fehler oder Netzwerk-Fehler.
        """
        response = requests.get(self.ARBEITS_ABC_URL, timeout=self.timeout)
        response.raise_for_status()
        
        parser = AIWordsHTMLParser()
        parser.feed(response.text)
        
        return parser.words
    
    def compare_with_existing(self, existing: Set[str], found: Set[str]) -> Set[str]:
        """Vergleicht gefundene Wörter mit bestehenden und findet neue.
        
        Args:
            existing: Set von bereits bekannten Wörtern.
            found: Set von neu gescrapten Wörtern.
        
        Returns:
            Set von neuen Wörtern (in found aber nicht in existing).
        """
        return found - existing
    
    def research(self, existing: Optional[Set[str]] = None) -> dict:
        """Führt vollständige Forschung durch: scrapen und vergleichen.
        
        Args:
            existing: Optional Set von bekannten Wörtern. Wenn None,
                     wird mit leerer Menge verglichen (alle gescrapten
                     Wörter sind "neu").
        
        Returns:
            Dict mit:
                - found: Set aller gescrapten Wörter
                - new: Set von neuen Wörtern
                - count_new: Anzahl der neuen Wörter
        """
        if existing is None:
            existing = set()
        
        found = self.scrape_arbeits_abc()
        new = self.compare_with_existing(existing, found)
        
        return {
            'found': found,
            'new': new,
            'count_new': len(new),
        }
