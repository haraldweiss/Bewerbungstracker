# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für AIWordsResearchService."""
from unittest.mock import patch, MagicMock
from services.ai_words_research_service import AIWordsResearchService


def test_scrape_arbeits_abc_returns_words():
    """Prüft dass arbeits-abc.de erfolgreich gescraped wird."""
    mock_html = '''
    <h2>KI-Tabu-Wörter:</h2>
    <ul>
      <li>eintauchen</li>
      <li>versiert</li>
      <li>neues_wort_1</li>
    </ul>
    '''
    
    with patch('services.ai_words_research_service.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_get.return_value = mock_response
        
        svc = AIWordsResearchService()
        words = svc.scrape_arbeits_abc()
        
        assert 'neues_wort_1' in words
        assert 'eintauchen' in words  # Bestehend


def test_compare_with_existing_detects_new_words():
    """Prüft dass neue Wörter vs. bestehende erkannt werden."""
    svc = AIWordsResearchService()
    existing = {'eintauchen', 'versiert'}
    found = {'eintauchen', 'versiert', 'neues_wort_1', 'neues_wort_2'}
    
    new_words = svc.compare_with_existing(existing, found)
    
    assert new_words == {'neues_wort_1', 'neues_wort_2'}
    assert 'eintauchen' not in new_words
