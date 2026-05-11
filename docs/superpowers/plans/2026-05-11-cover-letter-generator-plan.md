# Cover Letter Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a factual, confidence-scored cover letter generator that integrates into CV Comparison and Job Discovery, with PDF/DOCX export.

**Architecture:** 
- Backend: CoverLetter model + analysis/generation service + export service + API routes
- Frontend: CV Comparison tab + Job Discovery modal integration + confidence color rendering
- Three UX modes: one-click generation, detail analysis with sources, configurable tone/length/focus

**Tech Stack:** Flask + SQLAlchemy (backend), Claude API (analysis & generation), reportlab (PDF), python-docx (DOCX), vanilla JS (frontend)

**Related Spec:** [2026-05-11-cover-letter-generator-design.md](../specs/2026-05-11-cover-letter-generator-design.md)

---

## File Structure

**Backend (new/modified):**
- Modify: `models.py` → Add `CoverLetter` model
- Create: `services/cover_letter_service.py` → Analysis + generation logic
- Create: `services/export_service.py` → PDF/DOCX rendering
- Create: `api/cover_letter_routes.py` → API endpoints
- Create: `tests/test_cover_letter_service.py` → Service tests
- Create: `tests/test_export_service.py` → Export tests
- Create: `tests/test_cover_letter_routes.py` → API tests

**Frontend (new/modified):**
- Modify: `templates/cv_comparison.html` → Add "Anschreiben" tab
- Create: `static/js/cover_letter.js` → UI logic
- Create: `static/css/cover_letter.css` → Confidence color styling
- Modify: `templates/job_discovery.html` → Add button + modal
- Create: `static/js/job_discovery_cover_letter.js` → Job Discovery integration

---

## Task 1: Add CoverLetter Model

**Files:**
- Modify: `models.py`

- [ ] **Step 1: Add CoverLetter class after User class**

```python
class CoverLetter(db.Model):
    __tablename__ = 'cover_letters'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=True)
    
    job_title = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    cv_used = db.Column(db.String(255))
    
    content = db.Column(db.Text)
    analysis_json = db.Column(db.Text)
    
    tone = db.Column(db.String(50), default='professional')
    length = db.Column(db.String(50), default='medium')
    focus = db.Column(db.String(50), default='balanced')
    
    status = db.Column(db.String(50), default='draft')
    exported_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    application = db.relationship('Application', backref='cover_letter', uselist=False)
    
    def __repr__(self):
        return f'<CoverLetter {self.company_name} - {self.id}>'
```

- [ ] **Step 2: Add to User relationships**

In User class, add to relationships section:
```python
cover_letters = db.relationship('CoverLetter', backref='user_ref', cascade='all, delete-orphan')
```

- [ ] **Step 3: Commit**

```bash
git add models.py
git commit -m "feat(models): Add CoverLetter model with confidence scoring support"
```

---

## Task 2: Create Cover Letter Service (Analysis & Generation)

**Files:**
- Create: `services/cover_letter_service.py`
- Create: `tests/test_cover_letter_service.py`

- [ ] **Step 1: Write tests**

Test analyzes CV+Job returns matched_skills with confidence scores. Test generates content with data-confidence attributes.

- [ ] **Step 2: Implement service with two methods**
- `analyze(cv_text, job_description)` → returns JSON with matched_skills, matched_experience, interpreted_requirements
- `generate(company_name, job_title, analysis, tone, length, focus)` → returns HTML with data-confidence attributes
- Helper `_inject_confidence_attributes(html)` converts `<!-- confidence: 0.95 -->` comments to data attributes

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_cover_letter_service.py -v
git add services/cover_letter_service.py tests/test_cover_letter_service.py
git commit -m "feat(service): Add cover letter analysis & generation with confidence scoring"
```

---

## Task 3: Create Export Service (PDF & DOCX)

**Files:**
- Create: `services/export_service.py`
- Create: `tests/test_export_service.py`

- [ ] **Step 1: Install dependencies if missing**

```bash
pip install reportlab python-docx
```

- [ ] **Step 2: Write tests**
- Test PDF export returns binary with %PDF header
- Test DOCX export returns binary with PK header
- Test confidence attributes stripped from output

- [ ] **Step 3: Implement ExportService**
- `to_pdf(html_content, user_name, company_name, job_title)` → bytes
- `to_docx(html_content, user_name, company_name, job_title)` → bytes  
- `_strip_confidence_attributes(html)` → cleaned HTML

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_export_service.py -v
git add services/export_service.py tests/test_export_service.py
git commit -m "feat(export): Add PDF and DOCX export for cover letters"
```

---

## Task 4: Create API Routes

**Files:**
- Create: `api/cover_letter_routes.py`
- Create: `tests/test_cover_letter_routes.py`

- [ ] **Step 1: Write tests for all endpoints**

- [ ] **Step 2: Implement Blueprint with endpoints:**
- `POST /api/cover-letters/create` — Create draft
- `POST /api/cover-letters/{id}/generate` — Run analysis + generation
- `GET /api/cover-letters/{id}` — Get details
- `GET /api/cover-letters` — List user's letters
- `PATCH /api/cover-letters/{id}` — Update
- `POST /api/cover-letters/{id}/export` — Export PDF/DOCX
- `DELETE /api/cover-letters/{id}` — Delete

- [ ] **Step 3: Register blueprint in app.py**

```python
from api.cover_letter_routes import cover_letter_bp
app.register_blueprint(cover_letter_bp)
```

- [ ] **Step 4: Run tests and commit**

```bash
pytest tests/test_cover_letter_routes.py -v
git add api/cover_letter_routes.py tests/test_cover_letter_routes.py app.py
git commit -m "feat(api): Add cover letter REST endpoints"
```

---

## Task 5: Frontend Tab in CV Comparison

**Files:**
- Modify: `templates/cv_comparison.html`
- Create: `static/js/cover_letter.js`
- Create: `static/css/cover_letter.css`

- [ ] **Step 1: Create cover_letter.css with confidence color styling**
- Green for confidence >= 0.85
- Yellow for confidence 0.70-0.85
- Orange for confidence < 0.70

- [ ] **Step 2: Create cover_letter.js with CoverLetterGenerator class**
- handleGenerate() - 2-step API call
- displayCoverLetter() - render with confidence badges
- displayAnalysis() - show matched skills/experience
- toggleAnalysis() - show/hide analysis view
- openConfigModal() / saveConfig() - configuration
- export(format) - PDF/DOCX download
- saveDraft() - persist
- copyToClipboard()

- [ ] **Step 3: Modify cv_comparison.html**
- Add "✍️ Anschreiben" tab in navigation
- Add tab pane with inputs, actions, content area, modal
- Include JS + CSS files

- [ ] **Step 4: Commit**

```bash
git add templates/cv_comparison.html static/js/cover_letter.js static/css/cover_letter.css
git commit -m "feat(frontend): Add cover letter generator tab with confidence rendering"
```

---

## Task 6: Job Discovery Integration

**Files:**
- Modify: `templates/job_discovery.html`
- Create: `static/js/job_discovery_cover_letter.js`

- [ ] **Step 1: Create JobDiscoveryCoverLetter class**
- Bind to all `.btn-job-cover-letter` buttons
- openCoverLetterModal(jobData) - creates modal with CV input
- generateFromModal() - calls API
- exportFromModal() - downloads PDF

- [ ] **Step 2: Modify job_discovery.html**
- Add button to job card actions
- Add data attributes to job cards (id, title, company, description)
- Include JS file

- [ ] **Step 3: Commit**

```bash
git add templates/job_discovery.html static/js/job_discovery_cover_letter.js
git commit -m "feat(integration): Add cover letter modal to job discovery flow"
```

---

## Task 7: Feature Documentation

**Files:**
- Create: `docs/COVER_LETTER_FEATURE.md`

- [ ] **Step 1: Write feature documentation**
- Overview, user paths, API endpoints, confidence scoring, export, troubleshooting

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add docs/COVER_LETTER_FEATURE.md
git commit -m "docs: Add cover letter generator feature documentation"
```

---

## Verification Checklist

After all tasks complete:
- ✅ CoverLetter model in DB with relationships
- ✅ Analysis returns valid JSON with confidence scores
- ✅ Generation produces HTML with data-confidence attributes
- ✅ PDF/DOCX export strips confidence metadata
- ✅ CV Comparison tab fully functional
- ✅ Job Discovery modal works end-to-end
- ✅ Configuration (tone/length/focus) persists
- ✅ All tests pass

