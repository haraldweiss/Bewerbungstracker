# Claude On-Demand + Bulk-Actions für Job-Matches

**Date:** 2026-04-30
**Status:** Design (Ready for Implementation)
**Goal:** Claude API sparsam einsetzen (on-demand statt blind auto), und Bulk-Aktionen für Match-Verwaltung im UI bieten.

---

## Motivation

Aktuell läuft `claude-match` cron-stage alle 30 min und bewertet ALLE neuen JobMatches mit prefilter_score ≥ 15 automatisch. Mit der neuen Adzuna-Integration kommen pro Tag ~130+ neue Jobs rein → das verbraucht Claude-API-Budget für Jobs, die der User vielleicht nie ansieht.

User-Wunsch: Claude soll teure Bewertungen nur dann machen, wenn der User explizit Interesse zeigt (Klick) oder beim Import. Außerdem: Bulk-Verwaltung der Match-Liste — viele wegklicken oder mehrere auf einmal bewerten.

---

## High-Level Architektur

**Vorher:** Crawl → Prefilter → **Auto-Claude alle 30min für ≥15** → Notify

**Nachher:** Crawl → Prefilter → **Auto-Claude 1×/Tag für ≥50** → User sieht prefilter_score → User triggert Claude on-demand (single, bulk oder beim Import) → Notify

**Vier Wege wie Claude jetzt läuft:**

1. **Auto** (sparsam): 1×/Tag um 08:00 UTC, nur prefilter_score ≥ 50, max `job_claude_budget_per_tick` pro User
2. **On-Demand single**: User klickt "🤖 Bewerten lassen" auf einer Card
3. **On-Demand bulk**: User wählt mehrere Cards, klickt "🤖 Bewerten" in der Floating Action Bar
4. **Beim Import** (implizit): Wenn `match_score=None` und User klickt "Übernehmen", wird Claude vorher gerufen → Reasoning landet in den Notes der Application

Alle Wege respektieren `User.job_daily_budget_cents`.

---

## Backend: API-Änderungen

### Neue Endpoints

```
POST   /api/jobs/matches/<id>/score
       → Claude-Match für einen einzelnen Match
       → Budget-Check vorher
       → Returns:
           200 {match_score, match_reasoning, missing_skills}
           402 {error: "Tagesbudget erreicht"} (Payment Required)
           404 wenn nicht gefunden
           403 wenn nicht Owner

POST   /api/jobs/matches/score-bulk
       Body: {match_ids: [1, 2, 3]}
       → Claude für mehrere Matches; stoppt bei Budget-Erschöpfung
       → Returns: 200 {scored: [{id, match_score}, ...],
                       skipped_budget: [id, ...],
                       errors: [{id, error}, ...]}

PATCH  /api/jobs/matches/bulk
       Body: {match_ids: [1, 2, 3], status: "seen" | "dismissed"}
       → Bulk-Statuswechsel, kein Claude
       → Returns: 200 {updated: 3, not_found: [], forbidden: []}
```

### Geänderte Endpoints

```
POST   /api/jobs/matches/<id>/import   (existing)
       → NEU: Wenn match.match_score is None:
           1. Budget-Check
           2. Claude-Match aufrufen (oder skip wenn Budget erschöpft)
           3. match_score/reasoning/missing_skills schreiben
           4. Application anlegen mit Reasoning in Notes (wie bisher)
       → Notes-Format unverändert; "–" wird gezeigt wenn Claude geskippt wurde
```

### Geteilte Helper-Funktion

In `api/jobs_cron.py` extrahieren:

```python
def _run_claude_match_for(client, user, match) -> dict | None:
    """Claude-Match für eine Match-Row. Returns dict oder None bei Budget-Stop.

    Macht Budget-Check, Claude-Call, DB-Update (match_score/reasoning/missing_skills,
    raw.crawl_status='matched'), ApiCall-Tracking. Idempotent: returnt direkt
    wenn match_score schon gesetzt ist.
    """
```

Wird von Cron, single-endpoint, bulk-endpoint, import benutzt — DRY.

---

## Backend: Cron-Änderungen

### `/etc/cron.d/job-discovery`

```diff
- # Stage 3: Claude-Match (alle 30 Min, Top-N pro User)
- 0,30 * * * *        root /usr/local/bin/job-discovery-cron.sh claude-match
+ # Stage 3: Claude-Match (1×/Tag um 08:00 UTC, nur prefilter_score >= AUTO_CLAUDE_THRESHOLD)
+ 0 8 * * *           root /usr/local/bin/job-discovery-cron.sh claude-match
```

### `api/jobs_cron.py`

Neue Konstante:
```python
AUTO_CLAUDE_THRESHOLD = 50   # nur Top-Treffer auto-bewerten (prefilter_score)
```

In `claude_match()`-Endpoint Filter-Threshold ändern:
```python
candidates = (JobMatch.query
              .filter(JobMatch.user_id == user.id,
                      JobMatch.match_score.is_(None),
                      JobMatch.prefilter_score >= AUTO_CLAUDE_THRESHOLD,  # statt 15
                      JobMatch.status == 'new')
              .order_by(JobMatch.prefilter_score.desc())
              .limit(user.job_claude_budget_per_tick).all())
```

`PREFILTER_DISMISS_THRESHOLD = 15` bleibt unverändert (für Anzeige-Filtering im Frontend).

---

## Frontend: Card-Anzeige

### Wenn `match_score = null` (neue Anzeige)

```
┌─────────────────────────────────────────────────┐
│ ☐  ⚪ Vor-Filter: 42                            │
│    Senior Python Developer (m/w/d)              │
│    ACME GmbH · Berlin · 28.04.2026 · Adzuna     │
│                                                  │
│    [🔗 Original]  [🤖 Bewerten lassen]          │
│    [📥 Übernehmen]  [👁 Verbergen]  [🗑️ Verwerfen]│
└─────────────────────────────────────────────────┘
```

### Wenn `match_score` vorhanden (wie bisher, plus Checkbox)

- Score-Badge in Farbe (grün/gelb/orange basierend auf Score)
- Reasoning + Missing Skills sichtbar
- Buttons unverändert (kein "Bewerten lassen" mehr — schon bewertet)
- ☐ Checkbox links oben — neu

### Click-Verhalten "🤖 Bewerten lassen"

```javascript
async function requestSingleScore(matchId) {
    const r = await Auth.fetch(`/jobs/matches/${matchId}/score`, {method: 'POST'});
    if (r && r.match_score != null) {
        // Card neu rendern mit Reasoning
        await JobsView.fetchMatches();
    } else if (r && r.error) {
        toast.warning(r.error); // "Tagesbudget erreicht"
    }
}
```

### Vor-Filter-Badge

Distinkt von echten Match-Scores:
- **Vor-Filter (grau)**: `⚪ Vor-Filter: 42` — neutral, kein "Bewertet"-Statement
- **Echter Score**: bestehende Farb-Logik (grün ≥ 80, gelb ≥ 60, orange ≥ 30, sonst grau)

---

## Frontend: Bulk-Auswahl + Floating Action Bar

### Bulk-State

```javascript
const state = {
  // ... bestehende felder
  selectedIds: new Set(),  // NEU
};
```

- Checkbox an Card toggelt: `state.selectedIds.add(id) / .delete(id)`
- Counter und Action Bar werden bei Set-Änderung neu gerendert

### Floating Action Bar

```
┌──────────────────────────────────────────────────────────┐
│  3 ausgewählt   [🤖 Bewerten] [👁 Verbergen] [🗑️ Verwerfen] [✕] │
└──────────────────────────────────────────────────────────┘
```

- CSS: `position:fixed; bottom:1rem; left:50%; transform:translateX(-50%); z-index:100`
- Erscheint erst bei `selectedIds.size >= 1`, sonst hidden (`display:none`)
- ✕ Button: `selectedIds.clear()` + Re-Render

### Bulk-Aktionen

| Button         | API-Call                                              | Bestätigung                          |
|----------------|-------------------------------------------------------|--------------------------------------|
| 🤖 Bewerten    | `POST /jobs/matches/score-bulk` `{match_ids: [...]}` | keine; Toast danach                  |
| 👁 Verbergen   | `PATCH /jobs/matches/bulk` `{ids, status:"seen"}`    | keine                                |
| 🗑️ Verwerfen   | `PATCH /jobs/matches/bulk` `{ids, status:"dismissed"}` | confirm("N Jobs verwerfen?")        |

### "Alle auswählen"

Neuer Button neben den Filter-Controls oben:
```
[Alle auswählen]  → state.selectedIds = new Set(currentlyVisibleMatchIds)
```
Wenn schon alle ausgewählt: Button-Label wechselt zu "Auswahl aufheben".

### Persistenz

Auswahl wird beim Pagination-Wechsel oder Filter-Change zurückgesetzt (Set leeren). Begründung: Cards die nicht mehr sichtbar sind, sollten nicht mehr in der Bulk-Aktion stecken.

---

## Edge Cases & Error Handling

1. **Budget erschöpft mit-while bulk:** Server stoppt nach erster 402, returnt erfolgte + skipped IDs. Frontend zeigt Toast "X von Y bewertet, Rest wegen Budget übersprungen".

2. **Bulk: gemischte ownership:** Falls `match_ids` IDs enthält die nicht dem User gehören → die werden ignoriert in `forbidden`. Kein 403 für den ganzen Request.

3. **Import bei 0-Budget:** Application wird trotzdem angelegt (User soll nicht blockiert werden). Notes enthalten "Bewertung übersprungen — Tagesbudget erschöpft" statt Reasoning.

4. **Race-Condition (Card mehrfach klicken):** Frontend disabled den "Bewerten lassen"-Button während Request läuft.

5. **Auto-Cron + manuelle Bewertung gleichzeitig:** Beide rufen `_run_claude_match_for`, das idempotent ist (returnt früh wenn `match_score` schon gesetzt). Kein Duplicate-Call.

---

## Tests

### Backend Unit-Tests

- `test_score_single_endpoint_runs_claude` — happy path
- `test_score_single_returns_402_when_budget_exhausted`
- `test_score_single_returns_403_when_not_owner`
- `test_score_bulk_stops_at_budget` — first N scored, rest skipped_budget
- `test_score_bulk_handles_mixed_ownership` — forbidden array
- `test_bulk_status_update` — happy + ownership filter
- `test_import_runs_claude_when_match_score_none` — single-flow
- `test_import_skips_claude_when_budget_exhausted` — application still created
- `test_run_claude_match_for_idempotent` — double-call returnt früh
- `test_auto_cron_uses_threshold_50` — query-filter respektiert AUTO_CLAUDE_THRESHOLD

### Frontend Manual Test

- Card mit `match_score=null`: zeigt Vor-Filter-Badge + "Bewerten lassen"
- "Bewerten lassen" → Card refresht mit Reasoning
- 3 Cards selectieren → Action Bar erscheint mit Counter "3 ausgewählt"
- "Verwerfen" → Confirm → Cards verschwinden
- "Bewerten" Bulk → Toast bestätigt, Cards refreshen
- Filter ändern → Auswahl wird zurückgesetzt

---

## Migration

1. **DB:** Keine Schema-Changes. `match_score` ist schon nullable.
2. **Cron:** Nach Deploy: `/etc/cron.d/job-discovery` bearbeiten + `systemctl reload crond`.
3. **Bestehende Matches mit match_score:** Bleiben unverändert. Alle die schon bewertet wurden, behalten ihren Score.
4. **Bestehende Matches ohne match_score:** Werden in der UI mit Vor-Filter-Score angezeigt; User kann manuell bewerten oder Auto-Cron-1x/Tag erledigt das ggf.

---

## Out-of-Scope (Bewusst NICHT in dieser Spec)

- Bulk-Übernehmen (würde N Claude-Calls auf einmal triggern, Budget-Risiko)
- Per-User-Setting "Auto-Match an/aus" (ist global drastisch reduziert; UI-Setting kann später kommen)
- Frontend-Filter "nur bewertete zeigen" (kann via min_score=1 erreicht werden)
- Skill-Matching-Verbesserungen (eigenes Thema)
