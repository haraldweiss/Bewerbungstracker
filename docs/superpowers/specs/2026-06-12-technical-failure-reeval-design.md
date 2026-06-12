# Technische Fehlbewertungen automatisch neu bewerten + Ollama-Fallback

**Datum:** 2026-06-12
**Status:** Design (zur Umsetzung freigegeben nach User-Review)
**Bereich:** Job-Matching-Pipeline (Claude Code — Care: Anthropic/AI-Client-Pfad)

---

## 1. Problem

JobMatches, die aus **technischen Gründen** nicht bewertet werden konnten, bleiben dauerhaft als
Fehlschlag hängen und werden teils verworfen — obwohl es potenziell gute Jobs sind.

Konkret in Prod gefunden (User `harald.weiss@…`):
- 9 Matches mit `match_reasoning = "Bewertung fehlgeschlagen (ungültiges JSON von Provider)."`,
  `match_score = 0`. Das Free-Modell (`opencode / deepseek-v4-flash-free`) antwortete mit HTTP 200,
  lieferte aber Prosa statt JSON. Diese wurden mit Score 0 gespeichert und anschließend verworfen.
- Der **Backup-Provider** des Users ist ebenfalls `opencode / deepseek-v4-flash-free` — also dasselbe
  Free-Modell. Der bestehende HTTP-Fehler-Fallback (`build_fallback_kwargs` → `fallback_provider`)
  landet damit beim gleichen kaputten Modell → effektiv **kein echter Fallback**.

### Zwei verschiedene technische Fehlerursachen (heute gleich behandelt)

| Ursache | Heute | Problem |
|---|---|---|
| **Infrastruktur** — Provider nicht erreichbar, Tunnel offline, 5xx, Timeout, Queue | `_run_match_via_service` fängt Exception, `return False`, **kein** Score geschrieben → bleibt `score=NULL` | Wird vom Auto-Cron nur erneut versucht, wenn `prefilter_score ≥ 50`. Bei manueller Bewertung (niedriger prefilter) bleibt es liegen. |
| **Inhalt** — Provider antwortet (HTTP 200), liefert aber kein gültiges JSON | `_parse_match_response` → `score=0`, `reasoning="Bewertung fehlgeschlagen …"` | Fake-Score 0 sieht aus wie ein echter schlechter Match → wird verworfen, nie erneut versucht. |

Die bestehende `fallback_kwargs`-Mechanik greift **nur** bei HTTP-Fehlern des Primär-Providers, **nicht**
beim Inhalts-Fehler (HTTP 200 + Prosa).

---

## 2. Ziele

1. Technische Fehlbewertungen erzeugen **keinen** Fake-Score 0 / kein Auto-Dismiss mehr.
2. Bei Fehlschlag des Free-Modells wird automatisch auf ein **lokales Ollama-Modell** zurückgefallen
   (Default `gemma4:12b`, per Env überschreibbar) — für **beide** Fehlerarten (HTTP-Fehler + Inhalts-Fehler).
3. Inhalts-Fehler werden mit Backoff **bis zu 5×** automatisch erneut versucht; danach einmalig
   **sichtbar markiert** („Technisch nicht bewertbar – bitte manuell prüfen"), kein stiller Verlust,
   kein Endlos-Loop.
4. Infrastruktur-Ausfälle (Ollama auch down) verbrauchen die 5er-Kappe **nicht** — sie heilen sich
   selbst, sobald ein Provider wieder sauber antwortet.
5. **Altbestand** (bereits verworfene technische Fehlschläge ohne menschliches Urteil) wird einmalig
   zur Neubewertung zurückgestellt.

### Nicht-Ziele (YAGNI)

- Keine neue UI für Fallback-Konfiguration (Env-Defaults genügen).
- Kein wiederkehrender Cleanup-Cron — der präventive Fix verhindert Neufälle, ein Einmal-Script
  räumt den Altbestand.
- Keine Änderung an der allgemeinen Backup-Provider-Logik anderer Features (nur der Match-Pfad
  bekommt die Ollama-Kette).

---

## 3. Architektur

### 3.1 Datenmodell

Neue Spalte auf `JobMatch` (Alembic-Migration):

```python
eval_attempts = db.Column(db.Integer, nullable=False, server_default='0', default=0)
```

- Zählt **nur** Inhalts-Fehlversuche (nicht Infra-Fehler).
- Bei erfolgreicher Bewertung → zurück auf `0`.
- `eval_attempts >= 5` = „permanent technisch fehlgeschlagen" (abgeleiteter Zustand, kein eigener Status).

Backoff-Timing nutzt das bestehende `updated_at` (wird bei jedem Versuch ohnehin gesetzt).

### 3.2 Fehler-Klassifizierung (`services/job_matching/claude_utils.py`)

`_parse_match_response` liefert bereits ein Ergebnis mit erkennbarem Fehlschlag. Es wird um ein
explizites Flag erweitert, damit Inhalts-Fehler eindeutig von einem echten Score 0 unterscheidbar sind:

```python
@dataclass
class MatchResult:
    ...
    failed: bool = False   # True = technischer Inhalts-Fehler (kein echter Score)
```

Helper:

```python
MATCH_MAX_EVAL_ATTEMPTS = 5
PERMANENT_FAIL_REASONING = "Technisch nicht bewertbar – bitte manuell prüfen."

def _retry_backoff_hours(attempts: int) -> int:
    return min(2 ** max(attempts - 1, 0), 12)   # 1,2,4,8,12
```

### 3.3 Match-Auswertung mit Ollama-Fallback-Kette

`_run_match_via_service(user, match, raw, cv_summary, provider, model)`:

1. **Fallback-kwargs für Match überschreiben:** statt User-Backup wird die Match-spezifische
   Ollama-Kette gesetzt, wenn `MATCH_FALLBACK_ENABLED` (Default true):
   ```python
   fallback_kwargs = {'fallback_provider': 'ollama',
                      'fallback_model': os.getenv('MATCH_OLLAMA_FALLBACK_MODEL', 'gemma4:12b')}
   ```
   → deckt **HTTP-Fehler** des Free-Modells über den Service-seitigen Fallback ab.
2. `call_match(raw.description)`.
   - **Exception / Queue (Infra):** kein Score, `eval_attempts` unberührt, `return False` (retriable).
3. Antwort parsen. Wenn unparsebar:
   1. bestehender **Summarize-Retry** mit gleichem Primär-Modell.
   2. wenn weiterhin unparsebar → **client-seitiger Inhalts-Fallback**: erneuter `call_match` explizit
      mit `provider='ollama', model=<MATCH_OLLAMA_FALLBACK_MODEL>` (ohne weitere fallback_kwargs).
      - **Ollama nicht erreichbar (Infra):** kein Score, `eval_attempts` unberührt, `return False`.
      - **Ollama liefert gültiges JSON:** Erfolg → Score setzen, `eval_attempts=0`.
      - **Ollama antwortet, aber unparsebar (Inhalt):** Inhalts-Fehler (s. 3.4).
4. Sobald gültiges JSON vorliegt → Score/Reasoning/missing_skills setzen, `eval_attempts=0`,
   Cost-Tracking wie bisher (Ollama via=`ollama` → cost 0, key_owner=`user`).

### 3.4 Behandlung Inhalts-Fehler (Free-Modell UND Ollama liefern kein JSON)

```python
match.eval_attempts += 1
match.match_score = None          # kein Fake-Score 0
if match.eval_attempts >= MATCH_MAX_EVAL_ATTEMPTS:
    match.match_reasoning = PERMANENT_FAIL_REASONING   # sichtbarer Marker
else:
    match.match_reasoning = None  # retriable, unauffällig
# kein Auto-Dismiss, Status bleibt unverändert
return False
```

`_run_match_via_local_factory` (nur Local-Dev): analoge, minimale Behandlung — kein Fake-Score 0,
`eval_attempts`-Inkrement bei Inhalts-Fehler. Ollama-Inhalts-Fallback nur im Service-Pfad (Prod).

### 3.5 Retry-Auswahl (`services/tasks/handlers/cron_claude_match.py`)

Zusätzlicher Kandidaten-Zweig **unabhängig vom `AUTO_CLAUDE_THRESHOLD (=50)`-Gate**:

```python
# Bestehender Zweig: score IS NULL AND prefilter_score >= 50 AND status='new'
# NEU zusätzlich: technische Retry-Kandidaten (jeder prefilter)
# Grobe SQL-Vorfilterung (mindestens 1h alt), feiner Backoff danach in Python:
retry = (JobMatch.query.filter(
            JobMatch.user_id == user.id,
            JobMatch.match_score.is_(None),
            JobMatch.eval_attempts.between(1, MATCH_MAX_EVAL_ATTEMPTS - 1),
            JobMatch.status.in_(['new', 'seen']),
            JobMatch.updated_at < now - timedelta(hours=1))   # grober Mindestabstand
         .all())
retry = [m for m in retry
         if m.updated_at < now - timedelta(hours=_retry_backoff_hours(m.eval_attempts))]
```

- **Backoff pro Zeile:** Da der Mindestabstand von `eval_attempts` abhängt (1→2→4→8→12h), lässt er
  sich nicht als ein Skalar in die Query packen. Lösung: grober SQL-Vorfilter (`> 1h`), dann
  exakter Per-Row-Check in Python (`_retry_backoff_hours(m.eval_attempts)`).
- Budget + Per-Tick-Limit (`job_claude_budget_per_tick`) wie im bestehenden Zweig.
- Beide Mengen vereinigt, dedupliziert, sortiert (`eval_attempts ASC`, dann `prefilter_score DESC`).

### 3.6 Einmal-Cleanup `scripts/reeval_technical_failures.py`

Findet Altfälle und stellt sie zur Neubewertung zurück:

- **Auswahl:** `match_reasoning LIKE 'Bewertung fehlgeschlagen%'`
  AND `feedback_reasons IS NULL` (kein menschliches Urteil)
  AND `feedback_text` ist keine manuelle Begründung (NULL oder bekannter System-Tag).
- **Aktion:** `status='new'` (falls dismissed), `match_score=NULL`, `match_reasoning=NULL`,
  `missing_skills=NULL`, `notified_at=NULL`, `eval_attempts=1`
  → der neue Retry-Zweig (3.5) greift sie auch bei niedrigem prefilter auf.
- **Flags:** Dry-run-Default, `--apply` schreibt; vorher JSON-Backup der betroffenen Rows. Idempotent.
- Erfasst konsistent auch die 8 bereits manuell zurückgesetzten Matches.

### 3.7 Notify

Unverändert. `cron_notify` filtert `match_score IS NOT NULL` → NULL-Score (retriable **und**
permanent-fehlgeschlagen) löst keine Benachrichtigung aus. Benachrichtigt erst nach echter
Neubewertung bei Score ≥ Schwellwert. Keine Spam-Gefahr.

### 3.8 Frontend (minimal)

`index.html`: die `PERMANENT_FAIL_REASONING`-Begründung anzeigen (Match erscheint als „unbewertet"
mit technischem Hinweis). Beim Planen prüfen, ob ein „erneut bewerten"-Button bereits existiert;
falls ja, genügt das Anzeigen des Hinweises.

---

## 4. Konfiguration (Env, mit Defaults)

| Env | Default | Zweck |
|---|---|---|
| `MATCH_FALLBACK_ENABLED` | `true` | Ollama-Fallback-Kette fürs Matching an/aus |
| `MATCH_OLLAMA_FALLBACK_MODEL` | `gemma4:12b` | Lokales Ollama-Modell für HTTP- und Inhalts-Fallback |
| `MATCH_MAX_EVAL_ATTEMPTS` | `5` | Kappe für Inhalts-Fehlversuche (Konstante; bei Bedarf Env) |

---

## 5. Fehler-/Edge-Cases

- **Ollama-Ausfall + Free-Modell-Prosa gleichzeitig:** als Infra-Fehler gewertet (kein Score, Kappe
  unberührt) → heilt sich, sobald Ollama zurück. Verhindert, dass ein guter Job während eines
  Ollama-Ausfalls die 5er-Kappe verbrennt.
- **Permanenter Inhalts-Fehler (5×):** sichtbarer Marker, Score bleibt NULL, kein Dismiss; User
  entscheidet manuell. `eval_attempts=5` schließt ihn vom Auto-Retry aus.
- **Erfolgreiche Bewertung nach Fehlern:** `eval_attempts` zurück auf 0 (saubere Historie).
- **Manuell vom User verworfen (echtes `feedback_reasons`):** vom Cleanup ausgeschlossen — menschliches
  Urteil wird respektiert (z.B. Match 3053 `["wrong_seniority"]`).
- **SQLite WAL / Multi-Writer:** Migration + Cleanup mit `busy_timeout` (Projekt-Standard).

---

## 6. Tests

- `_parse_match_response`: `failed`-Flag bei ungültigem JSON, nicht bei gültigem Score 0.
- Infra- vs. Inhalts-Fehler-Unterscheidung in `_run_match_via_service` (Mocks: Exception vs. Prosa-Antwort).
- Ollama-Inhalts-Fallback: greift bei Prosa des Primär-Modells; Erfolg setzt `eval_attempts=0`.
- Kappe: 5. Inhalts-Fehler → `PERMANENT_FAIL_REASONING`, danach kein Auto-Retry.
- Backoff: `_retry_backoff_hours` Werte; Retry-Auswahl respektiert `updated_at`-Fenster.
- Retry-Zweig zieht Match mit `eval_attempts 1–4` unabhängig vom prefilter.
- Cleanup-Script: Auswahl (Altfälle ja, menschlich beurteilte nein), `--apply` idempotent.

---

## 7. Verifikation

- `pytest tests/services/ tests/api/` grün (inkl. neuer Tests).
- Alembic-Migration lokal + auf Oracle-VM (Container) angewandt, `eval_attempts`-Spalte vorhanden.
- Cleanup-Script Dry-run auf Prod-DB zeigt erwartete Altfälle; `--apply` mit Backup.
- Smoke: ein zurückgestellter Match wird im nächsten `claude-match`-Lauf neu bewertet (Provider gesund).
- Explizit angeben, ob mit echten Providern oder Mocks getestet (CLAUDE.md §4).
