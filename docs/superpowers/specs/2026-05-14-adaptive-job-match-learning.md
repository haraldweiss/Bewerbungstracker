# Feature-Spec: Adaptive Job-Match Learning

**Date:** 2026-05-14
**Scope:** Lernen aus User-Feedback (dismissed/imported + Begründungen) via Embedding-Centroids
**Affected Files:** models.py, services/job_matching/, api/jobs_user.py, api/jobs_cron.py, frontend/

## Ziel

Job-Match-Algorithmus passt sich an User-Präferenzen an, indem er aus den getroffenen Bewertungen (`dismissed`, `imported`) und optional strukturierten/freitext-Begründungen lernt. Ergebnis: Weniger irrelevante Jobs in der täglichen Liste, ohne zusätzliche Claude-Tokens zu verbrennen.

## Anforderungen

### Funktional
1. Jeder bewertete `JobMatch` kann mit Feedback versehen werden (strukturierte Reasons + Freitext)
2. System lernt aus diesen Bewertungen ohne explizites Re-Training
3. Konfigurierbar pro User (deaktivierbar, Schwellwerte einstellbar)
4. Cold-Start-Verhalten: keine Anpassung bis ausreichend Daten
5. Robust bei Ausfall externer Services (Ollama down → Fallback)

### Non-Funktional
- Keine zusätzlichen LLM-Kosten (Embedding läuft lokal/Mac-Tunnel)
- Inkrementelle Updates (kein Batch-Retraining)
- Transparenz: User kann sein Lern-Profil einsehen

## Datenmodell

### JobMatch (erweitert)
```python
class JobMatch(db.Model):
    # ... bestehende Felder ...
    feedback_reasons = db.Column(db.Text, nullable=True)  # JSON-Array
    feedback_text = db.Column(db.Text, nullable=True)     # Freitext
```

### Neue Tabelle: JobEmbedding
```python
class JobEmbedding(db.Model):
    __tablename__ = 'job_embeddings'

    raw_job_id = db.Column(db.Integer, db.ForeignKey('raw_jobs.id'), primary_key=True)
    vector = db.Column(db.LargeBinary, nullable=False)  # 768-dim float32 array packed
    model = db.Column(db.String(64), default='nomic-embed-text', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Neue Tabelle: UserLearnProfile
```python
class UserLearnProfile(db.Model):
    __tablename__ = 'user_learn_profiles'

    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    imported_centroid = db.Column(db.LargeBinary, nullable=True)   # 768-dim float32
    dismissed_centroid = db.Column(db.LargeBinary, nullable=True)
    samples_imported = db.Column(db.Integer, default=0, nullable=False)
    samples_dismissed = db.Column(db.Integer, default=0, nullable=False)
    # Pro-Reason Gewichtung als JSON: {"salary_too_low": 5, "wrong_location": 12, ...}
    reason_counts = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### User (erweitert um Settings)
```python
class User(db.Model):
    # ... bestehende Felder ...
    job_learn_enabled = db.Column(db.Boolean, default=True, nullable=False)
    job_learn_min_samples = db.Column(db.Integer, default=3, nullable=False)
    # Faktor 0.0–1.0 als Float gespeichert × 100 (Int) — vermeidet float-Migration
    job_learn_weight_pct = db.Column(db.Integer, default=30, nullable=False)  # = 0.30
```

## Standard-Reasons (Konstanten in `services/job_matching/feedback.py`)

```python
FEEDBACK_REASONS = {
    "wrong_location":   "Falscher Ort",
    "salary_too_low":   "Gehalt zu niedrig",
    "missing_skills":   "Fehlende Skills",
    "wrong_industry":   "Falsche Branche",
    "overqualified":    "Überqualifiziert",
    "underqualified":   "Unterqualifiziert",
    "wrong_seniority":  "Falsches Level",
    "other":            "Sonstiges",
}
```

Erweiterbar ohne Migration (validation list-only).

## Module

### `services/job_matching/embedder.py` (neu)
```python
def embed_text(text: str) -> bytes | None:
    """Returns packed float32 array or None on failure.
    Nutzt Ollama via OLLAMA_HOST env (default http://127.0.0.1:11434).
    Model: nomic-embed-text (768-dim).
    """

def embed_raw_job(raw_job: RawJob) -> bool:
    """Embed title+description, store in JobEmbedding. Idempotent."""

def vector_pack(vec: list[float]) -> bytes
def vector_unpack(blob: bytes) -> np.ndarray
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float
```

### `services/job_matching/learner.py` (neu)
```python
def update_centroid_for_feedback(user: User, match: JobMatch) -> None:
    """Triggered nach status-change auf dismissed/imported.
    - Lade User-Profil oder erstelle neu
    - Lade JobEmbedding für match.raw_job_id (oder generiere on-demand)
    - Update Centroid inkrementell: c_new = (c_old × n + v) / (n+1)
    - Persistiere
    """

def compute_score_adjustment(user: User, raw_job_id: int, base_score: float) -> float:
    """Returns adjusted score.
    - Falls user.job_learn_enabled=False → return base_score
    - Falls samples < user.job_learn_min_samples (für BEIDE Klassen) → return base_score
    - Falls kein Embedding für Job → return base_score
    - Sonst: adjusted = base_score × (1 + α × (sim_imp − sim_dis))
    - Clamp auf [0, 100]
    """

def get_learn_profile_stats(user: User) -> dict:
    """Für GET /api/jobs/learn-profile: samples, top_reasons, active_status."""
```

### `services/job_matching/feedback.py` (neu)
```python
FEEDBACK_REASONS: dict[str, str]  # siehe oben

def validate_reasons(reasons: list[str]) -> list[str]:
    """Filtert ungültige Keys raus, returns saubere Liste."""

def increment_reason_counts(profile: UserLearnProfile, reasons: list[str]) -> None:
    """Update reason_counts JSON inkrementell."""
```

### `services/job_matching/prefilter.py` (erweitert)
- `score_job()` erhält optionalen `user_id` Parameter
- Nach Basis-Score: Aufruf `learner.compute_score_adjustment(user, raw_job_id, base_score)`
- Keine Änderung der Public-API (default `user_id=None` → kein Adjustment, backward compat)

## API-Änderungen

### `PATCH /api/jobs/matches/{id}` (erweitert)
Body:
```json
{
  "status": "dismissed",
  "feedback_reasons": ["salary_too_low", "wrong_location"],
  "feedback_text": "Optional Freitext"
}
```
- Validation: `feedback_reasons` müssen aus `FEEDBACK_REASONS.keys()` sein, max 5 Einträge
- `feedback_text`: max 500 Zeichen, optional
- Nach Update: triggert `learner.update_centroid_for_feedback()` async (oder sync wenn klein)

### `POST /api/jobs/matches/bulk` (erweitert)
Body unverändert akzeptiert optional `feedback_reasons` (gilt für alle Items im Batch).

### `GET /api/jobs/learn-profile` (neu)
Returns:
```json
{
  "enabled": true,
  "samples_imported": 8,
  "samples_dismissed": 23,
  "active": true,
  "min_samples": 3,
  "weight_pct": 30,
  "top_reasons": [
    {"reason": "salary_too_low", "label": "Gehalt zu niedrig", "count": 12},
    {"reason": "wrong_location", "label": "Falscher Ort", "count": 8}
  ]
}
```

### `PATCH /api/user/settings` (erweitert)
Akzeptiert neue Felder: `job_learn_enabled`, `job_learn_min_samples`, `job_learn_weight_pct`.

## Frontend-Änderungen

### Dismiss-Modal (neu)
- Bei Klick auf "Verwerfen": Modal öffnet sich (statt direkt zu dismissen)
- Multi-Select-Checkboxes für alle FEEDBACK_REASONS
- Optional Textfeld "Freitext-Begründung" (max 500 chars)
- Buttons: "Skip" (verwirft ohne Feedback) und "Verwerfen mit Feedback"
- Beim "Skip" wird nur status=dismissed gesendet (keine reasons)

### Settings-UI
Neue Sektion "Match-Learning":
- Checkbox: Lernen aktiviert
- Slider: Min. Samples (1–10)
- Slider: Lern-Gewichtung (0–100%)
- Stats-Anzeige: "X imported, Y dismissed Jobs gelernt"
- Link: "Top Gründe anzeigen"

### Job-Card (klein)
- Falls dismissed mit reasons: Kleines Badge zeigen (z.B. "💬 2 Gründe")

## Datenfluss

```
1. Cron: RawJobs neu → /prefilter
   ├─ embedder.embed_raw_job() (falls Ollama up)
   └─ score_job() inkl. learner.compute_score_adjustment()

2. User dismisst Job + Feedback:
   ├─ PATCH /api/jobs/matches/{id} (status, reasons, text)
   ├─ models updaten
   ├─ learner.update_centroid_for_feedback() (sync)
   └─ Reason-Counts incrementiert

3. Nächster /prefilter-Cron:
   ├─ Neue Jobs werden embedded
   └─ Score reflektiert User-Präferenzen
```

## Edge Cases & Fehlerbehandlung

| Szenario | Verhalten |
|---|---|
| Ollama unreachable beim Embed | Log warn, `vector` bleibt NULL, kein Adjustment möglich für diesen Job |
| Ollama unreachable beim Score | `compute_score_adjustment` returns base_score (no crash) |
| <min_samples Samples | Kein Adjustment, base_score bleibt |
| User dismissed-then-imported | Alter Beitrag wird subtrahiert: `c = (c×n − v_old) / (n−1)` |
| feedback_reasons enthält ungültigen Key | Ungültige werden gefiltert, valide bleiben |
| feedback_text > 500 chars | 400-Error mit Hinweis |
| Embedding-Dimension wechselt (Model-Update) | Neue Tabelle `model`-Feld → bei Mismatch ignoriere alten Centroid |

## Migration

1. Alembic-Migration für 3 neue Spalten in `users`
2. Alembic-Migration für 2 neue Spalten in `job_matches` (`feedback_reasons`, `feedback_text`)
3. Alembic-Migration für `job_embeddings` und `user_learn_profiles` Tabellen
4. Backfill-Script (`scripts/backfill_job_embeddings.py`): Embedded alle bestehenden RawJobs schubweise (Rate-Limit-aware)
5. Backfill-Script (`scripts/rebuild_user_centroids.py`): Berechnet Centroids für User mit existierenden dismissed/imported aus Historie

## Testing

### Unit (services/job_matching/)
- `embedder`: Mock Ollama response → korrektes Packing, Unpacking, Cosine
- `learner.update_centroid_for_feedback`: Math-Korrektheit (inkrementeller Mittelwert, Subtraktion)
- `learner.compute_score_adjustment`: Cold-Start, Clamp, disabled-User
- `feedback.validate_reasons`: Ungültige Filter, Limits

### Integration (api/)
- PATCH mit feedback_reasons → DB-Update + Centroid-Update
- GET /api/jobs/learn-profile → korrekte Stats
- Bulk-Update mit Reasons
- Settings-PATCH validiert Felder

### End-to-End
- 3 Jobs dismissen mit "salary_too_low"
- 3 Jobs importen
- Neuer ähnlicher Job (high-salary description) bekommt höheren Score als bei Cold-Start

## Rollback

- Migration-Down: Tabellen + Spalten entfernen
- `job_learn_enabled=false` per User → sofort deaktivieren ohne Datenverlust

## Out-of-Scope (YAGNI)

- Cross-User-Learning (Privacy + Komplexität)
- Auto-Tuning der `weight_pct` per User
- Embedding-Caching jenseits DB (z.B. Redis)
- A/B-Test-Framework für verschiedene α-Werte
- Visualisierung des Embedding-Raums (PCA-Plot etc.)

## Offene Punkte (zur Klärung in Implementation)

- Soll `imported` auch Feedback-Modal triggern? → **Entscheidung: Nein, nur "Skip-Variante" via Settings aktivierbar**
- Centroid-Update sync oder async (Celery)? → **Entscheidung: Sync — Operation ist <50ms**
