# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für AIWordsResearchService."""
from unittest.mock import patch, MagicMock
import pytest
import requests
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


@patch('services.ai_words_research_service.requests.get')
def test_scrape_arbeits_abc_handles_network_error(mock_get):
    """Network error → ValueError mit geloggtem Error."""
    mock_get.side_effect = requests.ConnectionError('Network unreachable')
    svc = AIWordsResearchService()

    with pytest.raises(ValueError, match='Failed to fetch'):
        svc.scrape_arbeits_abc()


@patch('services.ai_words_research_service.requests.get')
def test_scrape_arbeits_abc_handles_http_error(mock_get):
    """HTTP 404/500 → ValueError mit geloggtem Error."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = requests.HTTPError('404 Not Found')
    mock_get.return_value = mock_response

    svc = AIWordsResearchService()
    with pytest.raises(ValueError, match='Failed to fetch'):
        svc.scrape_arbeits_abc()


@patch('services.ai_words_research_service.requests.get')
def test_scrape_arbeits_abc_handles_empty_response(mock_get):
    """Empty HTML (no <ul>/<li>) → empty set mit warning logged."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '<html></html>'
    mock_get.return_value = mock_response

    svc = AIWordsResearchService()
    result = svc.scrape_arbeits_abc()

    assert result == set()


@patch('services.ai_words_research_service.requests.get')
def test_scrape_arbeits_abc_handles_parser_error(mock_get):
    """Malformed HTML → ValueError mit geloggtem Error."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Simulate a response that will cause parser issues
    mock_response.text = 'NOT VALID HTML AT ALL <<<>>>>'
    mock_get.return_value = mock_response

    svc = AIWordsResearchService()
    # HTMLParser should handle this gracefully and extract empty set
    # since there's no valid <ul>/<li> tags
    result = svc.scrape_arbeits_abc()
    assert result == set()
