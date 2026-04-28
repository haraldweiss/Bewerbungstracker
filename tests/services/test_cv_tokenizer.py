from services.job_matching.cv_tokenizer import tokenize_cv, CVTokens


def test_extracts_skills_titles_and_freetext():
    cv_data = {
        "cv": {
            "skills": ["React", "TypeScript", "Python", "Docker"],
            "experiences": [
                {"title": "Senior Frontend Developer", "company": "ACME"},
                {"title": "Full Stack Engineer", "company": "Beta"},
            ],
            "summary": "8 Jahre Erfahrung mit JavaScript, Node.js, Cloud-Architektur."
        }
    }
    tokens = tokenize_cv(cv_data)
    assert isinstance(tokens, CVTokens)
    assert "react" in tokens.skills
    assert "typescript" in tokens.skills
    assert "senior frontend developer" in tokens.titles
    assert "javascript" in tokens.freetext  # case-insensitive

def test_handles_empty_cv():
    tokens = tokenize_cv({"cv": {}})
    assert tokens.skills == set()
    assert tokens.titles == set()

def test_handles_none():
    tokens = tokenize_cv(None)
    assert tokens.skills == set()

def test_handles_german_umlauts():
    cv_data = {"cv": {"skills": ["Verkäufer", "Bürokauffrau"]}}
    tokens = tokenize_cv(cv_data)
    assert "verkäufer" in tokens.skills
    assert "bürokauffrau" in tokens.skills


def test_handles_text_blob_format_from_pdf_upload():
    """Frontend-Upload-Format: PDF/DOCX → text-Blob.

    Der CV-Upload extrahiert mit pdf.js / Mammoth den Plaintext und legt
    ihn unter cvData.text ab. Tokenizer muss das erkennen.
    """
    cv_data = {
        "cvData": {
            "fileName": "harald_cv.pdf",
            "text": "LEBENSLAUF Harald Weiss. Senior Security Engineer mit Python, "
                    "Docker und Kubernetes-Erfahrung. SOC SIEM SOAR Incident Management.",
        },
        "cvComparisons": []
    }
    tokens = tokenize_cv(cv_data)
    # Aus dem Text-Blob landen die Wörter im freetext-Set
    assert "python" in tokens.freetext
    assert "docker" in tokens.freetext
    assert "kubernetes" in tokens.freetext
    assert "siem" in tokens.freetext
    # Strukturierte Sets bleiben leer (kein "cv"-Block)
    assert tokens.skills == set()
    assert tokens.titles == set()


def test_supports_both_formats_simultaneously():
    """Wenn beide Schemas vorhanden sind, werden beide ausgewertet."""
    cv_data = {
        "cv": {"skills": ["Java"]},
        "cvData": {"text": "Senior Engineer mit Python."},
    }
    tokens = tokenize_cv(cv_data)
    assert "java" in tokens.skills
    assert "python" in tokens.freetext


def test_text_blob_empty_text_does_nothing():
    cv_data = {"cvData": {"fileName": "empty.pdf", "text": ""}}
    tokens = tokenize_cv(cv_data)
    assert tokens.freetext == set()
