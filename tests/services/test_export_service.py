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


def test_export_keeps_explicit_line_breaks():
    assert _extract_paragraphs('<p>Hello<br>World<br />Again</p>') == ['Hello\nWorld\nAgain']
    from docx import Document
    import io
    content = ExportService().to_docx('<p>Hello<br>World</p>','Max','Acme','Engineer')
    assert 'Hello\nWorld' in [p.text for p in Document(io.BytesIO(content)).paragraphs]


def test_pdf_escapes_user_text_in_every_paragraph(monkeypatch):
    import sys
    from types import ModuleType
    # Minimal reportlab stand-in captures actual renderer input without network access.
    modules = {name: ModuleType(name) for name in ['reportlab','reportlab.lib','reportlab.lib.pagesizes','reportlab.lib.styles','reportlab.lib.units','reportlab.lib.enums','reportlab.platypus']}
    captured = []
    modules['reportlab.lib.pagesizes'].A4 = (595,842)
    modules['reportlab.lib.units'].inch = 72
    modules['reportlab.lib.enums'].TA_LEFT = 0
    modules['reportlab.lib.enums'].TA_JUSTIFY = 4
    modules['reportlab.lib.styles'].getSampleStyleSheet = lambda: {'Normal':object()}
    modules['reportlab.lib.styles'].ParagraphStyle = lambda *a,**kw: object()
    modules['reportlab.platypus'].Paragraph = lambda text,style: captured.append(text)
    modules['reportlab.platypus'].Spacer = lambda *a: None
    class Doc:
        def __init__(self,*a,**kw): pass
        def build(self,elements): pass
    modules['reportlab.platypus'].SimpleDocTemplate = Doc
    for name,module in modules.items(): monkeypatch.setitem(sys.modules,name,module)
    ExportService().to_pdf('<p>&lt;img src="https://invalid.example/x"/&gt; &amp; text<br>Second</p>', 'A <B> & C','Acme','Dev <Ops>', 'Street <1>')
    assert '<b>A &lt;B&gt; &amp; C</b>' in captured
    assert 'Street &lt;1&gt;' in captured
    assert '<b>Bewerbung als Dev &lt;Ops&gt;</b>' in captured
    assert '&lt;img src="https://invalid.example/x"/&gt; &amp; text<br/>Second' in captured
    assert 'A &lt;B&gt; &amp; C' in captured


def test_real_pdf_preserves_literal_markup_and_line_breaks():
    pytest.importorskip('reportlab')
    pypdf = pytest.importorskip('pypdf')
    import io
    result = ExportService().to_pdf('<p>&lt;b&gt;literal&lt;/b&gt; &amp; text<br>Second line</p>','A <B> & C','Acme','Dev <Ops>','Street <1>')
    text = '\n'.join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(result)).pages)
    assert 'A <B> & C' in text
    assert 'Street <1>' in text
    assert 'Dev <Ops>' in text
    assert '<b>literal</b> & text\nSecond line' in text
