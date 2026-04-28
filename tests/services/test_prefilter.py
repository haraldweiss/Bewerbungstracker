from services.job_matching.cv_tokenizer import CVTokens
from services.job_matching.prefilter import score_job, PrefilterContext


def _ctx(language_filter=None, region_filter=None):
    return PrefilterContext(
        language_filter=language_filter or ["de", "en"],
        region_filter=region_filter,
    )


def test_score_high_for_full_overlap():
    cv = CVTokens(
        skills={"react", "typescript", "python"},
        titles={"senior frontend developer"},
        freetext={"javascript", "node.js"},
    )
    job = {
        "title": "Senior Frontend Developer (React/TypeScript)",
        "description": "Wir suchen mit React, TypeScript und Python. JavaScript-Profi.",
        "location": "Berlin",
    }
    score = score_job(cv, job, _ctx())
    assert score >= 70

def test_score_low_for_no_overlap():
    cv = CVTokens(skills={"java", "spring"})
    job = {"title": "Designer", "description": "Figma, Adobe XD", "location": "Hamburg"}
    score = score_job(cv, job, _ctx())
    assert score < 20

def test_region_filter_drops_score_to_zero():
    cv = CVTokens(skills={"react"})
    job = {"title": "React Dev", "description": "React", "location": "München, 80331"}
    ctx = _ctx(region_filter={"plz_prefixes": ["10", "11"], "remote_ok": False})
    assert score_job(cv, job, ctx) == 0

def test_remote_ok_overrides_region_filter():
    cv = CVTokens(skills={"react"})
    job = {"title": "React Dev (Remote)", "description": "React, fully remote", "location": "Munich"}
    ctx = _ctx(region_filter={"plz_prefixes": ["10"], "remote_ok": True})
    assert score_job(cv, job, ctx) > 0
