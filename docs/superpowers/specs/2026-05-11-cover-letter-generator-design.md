# Cover Letter Generator - Design Specification
**Date:** 2026-05-11  
**Author:** Harald Weiss  
**Status:** Approved for Implementation

---

## Overview

The Cover Letter Generator creates personalized, factual cover letters from job postings and user CVs. It uses AI to match CV content with job requirements, marks confidence scores for factual vs. interpreted content, and exports to PDF/DOCX. It integrates into the CV Comparison tab and Job Discovery flow, supporting three usage modes: quick one-click generation, detailed analysis with sources, and configurable tone/length/focus settings.

---

## 1. Data Model

### New Table: `CoverLetter`

```python
class CoverLetter(db.Model):
    __tablename__ = 'cover_letters'
    
    # Primary & Foreign Keys
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=True)
    
    # Job & CV Context
    job_title = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    cv_used = db.Column(db.String(255))
    
    # Generated Content
    content = db.Column(db.Text)  # HTML: <p data-confidence="0.95">...</p>
    analysis_json = db.Column(db.Text)  # JSON: {matched_skills, matched_experience, interpreted_requirements}
    
    # Configuration & Generation Settings
    tone = db.Column(db.String(50), default='professional')  # professional|casual|technical
    length = db.Column(db.String(50), default='medium')  # short|medium|long
    focus = db.Column(db.String(50), default='balanced')  # technical|leadership|projects|balanced
    
    # Status & Metadata
    status = db.Column(db.String(50), default='draft')  # draft|finalized|sent
    exported_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='cover_letters')
    application = db.relationship('Application', backref='cover_letter', uselist=False)
```

---

## 2. User Experience Flows

### Flow A: Quick-Click (One-Step)

**Entry Points:**
- CV Comparison tab: "Anschreiben" tab → Paste job posting → Click "⚡ Anschreiben generieren"
- Job Discovery: Suggestion card → "✍️ Anschreiben generieren" button

**Process:**
1. User provides job posting + CV selection
2. Single KI call: Generate draft with confidence scores
3. Result shows: Full text with color-coded confidence (green/yellow/red)
4. User can: Edit inline, view analysis, configure style, or export

---

### Flow B: Detail Analysis (Show Sources)

**Entry Point:**
- From Quick-Click result: Click "📊 Detailanalyse" button
- Or direct entry: "🔍 Mit Analyse-Vorschau" button

**Process:**
1. System shows structured analysis:
   - **Matched Skills:** {skill, cv_source_line, job_match_text, confidence}
   - **Matched Experience:** {experience, cv_source, job_alignment, confidence}
   - **Interpreted Requirements:** {requirement, reasoning, confidence}
2. User can: Add/remove points, adjust confidence assessment
3. Click "✍️ Text generieren" → Second KI call generates full text based on validated outline

---

### Flow C: Configuration First

**Entry Point:**
- Before generating: Click "⚙️ Style anpassen"

**Process:**
1. Modal dialog:
   - **Tone:** Professional | Casual | Technical (default: Professional)
   - **Length:** Kurz (200w) | Medium (400w) | Lang (600w+) (default: Medium)
   - **Focus:** Technical Skills | Leadership | Projects | Balanced (default: Balanced)
2. Optionally save as default for future use
3. Click "Speichern" → Proceed with Flow A or B using configured settings

---

## 3. KI Prompts & Confidence Scoring

### Phase 1: Analysis (Internal)

**Prompt:**
```
Analyze this job posting and CV. Return structured JSON:

1. For each skill in CV that appears in job posting: 
   - confidence: 0.0-1.0 (1.0 = exact match, 0.5+ = relevant match)
2. For each job requirement not clearly in CV:
   - flag as "interpreted" with confidence 0.5-0.7
3. For any requirement that's speculative:
   - flag as "speculative" with confidence < 0.5

Return JSON (do NOT include markdown, just raw JSON):
{
  "matched_skills": [
    {"skill": "Python", "cv_source": "line 12", "job_requirement": "Python required", "confidence": 0.99},
    {"skill": "Team Leadership", "cv_source": "Project X management", "job_requirement": "Lead teams", "confidence": 0.85}
  ],
  "matched_experience": [
    {"experience": "5 years software engineering", "cv_source": "line 8", "alignment": "Senior role", "confidence": 0.92}
  ],
  "interpreted_requirements": [
    {"requirement": "Fast-paced startup environment", "reasoning": "inferred from job context", "confidence": 0.65}
  ],
  "missing_or_weak": [
    {"requirement": "Kubernetes experience", "cv_status": "not mentioned", "confidence_of_fit": 0.3}
  ]
}
```

### Phase 2: Content Generation

**Prompt:**
```
Write a German cover letter for {company_name} ({job_title} position).

Constraints:
- Use ONLY facts from this analysis (no inventions):
  {JSON analysis from Phase 1}
- Mark confidence in each paragraph as HTML comment: <!-- confidence: 0.95 -->
- Confidence >= 0.85 = factual (green)
- Confidence 0.70-0.85 = mostly factual (yellow)  
- Confidence < 0.70 = interpreted/inferred (orange)
- Never include items with confidence < 0.3

Style:
- Tone: {tone}
- Length: {length}
- Focus: {focus}

Format: Plain paragraphs with confidence comments, no markdown.
```

### Rendering in Frontend

```html
<p data-confidence="0.99" data-source="fact">
  Ich verfüge über 5+ Jahre Python-Erfahrung, exakt wie in der Ausschreibung gefordert.
</p>
<p data-confidence="0.75" data-source="inferred">
  Mein Hintergrund in agilen Umgebungen sollte gut zu Ihrem schnelllebigen Startup passen.
</p>
```

**CSS for Visual Coding:**
- `data-confidence >= 0.85`: Green background (#e8f5e9)
- `data-confidence 0.70-0.85`: Yellow background (#fff9c4)
- `data-confidence < 0.70`: Orange background (#ffe0b2)

**Info Icon on Hover:**
- Shows: "Diese Aussage basiert auf {source}: {detail}"

---

## 4. Export Functionality

### PDF Export

**Backend Endpoint:**
```python
POST /api/cover-letter/{id}/export
{
  "format": "pdf"
}
```

**Implementation:**
- Library: `reportlab` (existing or add)
- Header: User name + address (from CV or user profile)
- Content: Generated cover letter (confidence attributes REMOVED before rendering)
- Footer: Date + optional "Unterschrift" placeholder
- Styling: Professional (Arial 11pt, standard margins)
- Output: Binary download, filename: `{company}_{job_title}_{date}.pdf`

**Content Processing:**
```python
def render_to_pdf(cover_letter):
    # Strip data-confidence and data-source attributes
    clean_html = re.sub(r'data-\w+="[^"]*"', '', cover_letter.content)
    # Render to PDF
    return generate_pdf_from_html(clean_html)
```

### DOCX Export

**Backend Endpoint:**
```python
POST /api/cover-letter/{id}/export
{
  "format": "docx"
}
```

**Implementation:**
- Library: `python-docx`
- Structure: Professional template
- Metadata: Title={company}, Author={user_email}
- Editable: User can modify in Word after download
- Styling: Calibri 11pt, 1.15 line spacing, 2.54cm margins
- Output: Binary download, filename: `{company}_{job_title}_{date}.docx`

**Update Model:**
```python
cover_letter.exported_at = datetime.utcnow()
db.session.commit()
```

---

## 5. Integration Points

### 5.1 CV Comparison Tab

**New Tab in Existing UI:**
```
Navigation:
  📋 CV Vergleich
    - Upload
    - Comparison
    - KI-Plattformen
    - ✨ Anschreiben (NEW)
```

**Tab Content:**
```
[Paste Job Posting Textarea]
[Select CV Dropdown]
[⚙️ Style anpassen] [⚡ Anschreiben generieren]

[Results Section]
  [Generated Cover Letter with confidence coloring]
  [📊 Detailanalyse] [💾 Speichern] [📥 PDF] [📄 DOCX] [🔗 Kopieren]
```

### 5.2 Job Discovery Flow

**Integration Point: Job Suggestion Card**

```html
<div class="job-card">
  <h3>{job_title} at {company}</h3>
  <p>Match: {score}%</p>
  <buttons>
    <button>📋 Details</button>
    <button>✍️ Anschreiben generieren</button> <!-- NEW -->
    <button>💾 Speichern</button>
  </buttons>
</div>
```

**Flow:**
- Click "✍️ Anschreiben generieren"
- Modal opens with job posting pre-filled
- User selects CV, optionally configures style
- Generate button triggers Flow A (one-click) or shows Flow B option
- Result modal: can save, export, or close

---

## 6. Error Handling & Validation

| Scenario | Handling |
|----------|----------|
| No CV uploaded | Show "Bitte laden Sie zuerst einen CV hoch" |
| Job posting < 50 chars | Show "Zu wenig Informationen — ergänzen Sie Details" |
| KI returns generic text | Flag all as red (confidence < 0.5) + warning |
| > 30% of content < 0.5 confidence | ⚠️ Warning "Viel interpretiert — überprüfen Sie vor Versand" |
| Export fails | Show error toast, allow retry |
| Analysis takes > 30s | Show timeout message, allow retry |

---

## 7. Database Persistence

**Create Flow:**
1. POST /api/cover-letters/create → insert row with `status='draft'`
2. Store job_description + cv_used for later regeneration
3. Return CoverLetter ID to frontend

**Read Flow:**
1. GET /api/cover-letters/{id} → return full CoverLetter with content + analysis_json
2. GET /api/cover-letters → return list (user's cover letters, paginated)

**Update Flow:**
1. PATCH /api/cover-letters/{id} → update content, set `status='finalized'`
2. PATCH /api/cover-letters/{id}/link → link to Application

**Export Flow:**
1. POST /api/cover-letters/{id}/export → generate file, update exported_at timestamp
2. Return binary file

**Delete Flow:**
1. DELETE /api/cover-letters/{id} → soft delete (optional: keep in archive)

---

## 8. Configuration Persistence

**User Defaults:**
- Store in `user.settings_json`:
  ```json
  {
    "cover_letter_defaults": {
      "tone": "professional",
      "length": "medium",
      "focus": "balanced"
    }
  }
  ```
- Load on tab open, apply to new generations
- Allow override per generation

---

## 9. Scope & Constraints

✅ **In Scope:**
- One-click generation with confidence scores
- Detail analysis with source attribution
- Configurable tone/length/focus
- PDF + DOCX export
- Two integration points (CV tab + Job Discovery)
- Factual vs. interpreted distinction
- Reusable configuration

⏭️ **Out of Scope (Future):**
- Email integration (send directly)
- Template library
- A/B testing different approaches
- Batch generation for multiple jobs
- Signing/digital signatures

---

## 10. Success Criteria

- ✅ Generated cover letters are factual (no invented skills/experience)
- ✅ Confidence scores accurately reflect source (CV vs. inferred)
- ✅ User can export to PDF/DOCX without loss of content
- ✅ Both integration points work (CV tab + Job Discovery)
- ✅ Generation takes < 20s per request
- ✅ No duplicate cover letters for same job

---

## 11. Implementation Phases

**Phase 1: Backend Core**
- CoverLetter model + migrations
- Analysis prompt + parsing
- Content generation prompt + confidence scoring
- Export (PDF + DOCX)

**Phase 2: Frontend**
- CV Comparison "Anschreiben" tab UI
- Job Discovery modal integration
- Confidence color rendering + hover info
- Save/edit/delete

**Phase 3: Polish**
- Configuration modal (tone/length/focus)
- Detail analysis view
- Edge case handling + error messages
- Testing

