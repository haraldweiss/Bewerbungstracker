# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Tests für ExportService."""
import pytest
from services.export_service import (
    ExportService, _strip_confidence_attributes, _extract_paragraphs,
)


def test_strip_confidence_attributes():
    html = '<p data-confidence="0.95" data-source="cv">Hello</p>'
    result = _strip_confidence_attributes(html)
    assert 'data-confidence' not in result
    assert 'data-source' not in result
    assert 'Hello' in result


def test_strip_confidence_preserves_text():
    html = '<p data-confidence="0.85">Wichtiger Inhalt mit Umlauten äöü</p>'
    result = _strip_confidence_attributes(html)
    assert 'Wichtiger Inhalt mit Umlauten äöü' in result


def test_extract_paragraphs_simple():
    html = '<p>First</p>\n<p>Second</p>'
    result = _extract_paragraphs(html)
    assert result == ['First', 'Second']


def test_extract_paragraphs_with_confidence_attrs():
    html = '<p data-confidence="0.95">Erste</p><p data-confidence="0.75">Zweite</p>'
    result = _extract_paragraphs(html)
    assert result == ['Erste', 'Zweite']


def test_extract_paragraphs_strips_inline_html():
    html = '<p>Text mit <strong>bold</strong> und <em>italic</em></p>'
    result = _extract_paragraphs(html)
    assert result == ['Text mit bold und italic']


def test_extract_paragraphs_handles_entities():
    html = '<p>Gr&uuml;&szlig;e &amp; mehr</p>'
    result = _extract_paragraphs(html)
    assert result == ['Grüße & mehr']


def test_extract_paragraphs_empty_skipped():
    html = '<p>  </p><p>Content</p><p></p>'
    result = _extract_paragraphs(html)
    assert result == ['Content']


# DOCX-Test (python-docx ist installiert)
def test_to_docx_returns_zip_bytes():
    svc = ExportService()
    html = '<p data-confidence="0.95">Sehr geehrte Damen und Herren,</p><p>Inhalt.</p>'
    result = svc.to_docx(html, "Max Mustermann", "TechCorp", "Python Engineer")
    assert isinstance(result, bytes)
    assert len(result) > 1000  # Non-trivial size
    assert result[:2] == b'PK'  # ZIP signature


def test_to_docx_with_address():
    svc = ExportService()
    html = '<p>Test</p>'
    result = svc.to_docx(
        html, "Max Mustermann", "TechCorp", "Engineer",
        applicant_address="Hauptstraße 1\n10115 Berlin"
    )
    assert isinstance(result, bytes)
    assert result[:2] == b'PK'


def test_to_docx_strips_confidence():
    """DOCX-Output darf KEINE data-confidence Werte enthalten."""
    svc = ExportService()
    html = '<p data-confidence="0.42">Sekretär-Text</p>'
    result = svc.to_docx(html, "Max", "Corp", "Job")
    # DOCX ist ZIP — entpacken und document.xml prüfen
    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        with zf.open('word/document.xml') as f:
            content = f.read().decode('utf-8')
    assert 'data-confidence' not in content
    assert '0.42' not in content
    assert 'Sekretär-Text' in content


# PDF-Test (Skip wenn reportlab nicht installiert)
def test_to_pdf_returns_pdf_bytes():
    pytest.importorskip("reportlab")
    svc = ExportService()
    html = '<p data-confidence="0.95">Sehr geehrte Damen und Herren,</p><p>Inhalt.</p>'
    result = svc.to_pdf(html, "Max Mustermann", "TechCorp", "Python Engineer")
    assert isinstance(result, bytes)
    assert len(result) > 500
    assert result[:4] == b'%PDF'


def test_to_pdf_with_address():
    pytest.importorskip("reportlab")
    svc = ExportService()
    html = '<p>Test</p>'
    result = svc.to_pdf(
        html, "Max", "Corp", "Engineer",
        applicant_address="Hauptstraße 1\n10115 Berlin"
    )
    assert result[:4] == b'%PDF'
