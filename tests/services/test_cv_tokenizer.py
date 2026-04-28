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
