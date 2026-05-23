# Claude-Backup-Cost Cap — Design

**Datum:** 2026-05-23
**Status:** Design, Approval ausstehend
**Verwandt:** `incident_claude_cost_burst_2026_05_22.md`, `feedback_ai_endpoint_user_provider.md`

## Problem

Bewerbungstracker ist seit Mai konfiguriert mit `ai_provider=ollama` für alle Features
(match, cv_summarize, cover_letter, email_analyse). Jedes Feature hat aber einen
Backup-Fallback via `user.ai_provider_backup = "claude"` mit Modell `claude-sonnet-4-6`.

Wenn Ollama-Calls fehlschlagen (Mac-Tunnel down, Timeout, Parse-Error), fällt das
System still auf Sonnet zurück. Konsequenzen:

1. **Sonnet ist ~5x teurer als Haiku** — bei vergleichbarer Quality für unsere Use-Cases
2. **`job_daily_budget_cents = 500` (= $5/Tag) wird umgangen** — Budget-Check existiert
   nur in `api/jobs_cron.py::claude_match()` UND der Cost-Tracker `_user_today_cost_cents()`
   liest nur aus `api_calls`, die wiederum **nur vom Match-Endpoint geschrieben wird**.
   Andere Features (cv_summarize, cover_letter, email_parse, pattern_learner) loggen
   gar nichts → komplett unsichtbar im local Cost-Tracking.
3. Am 22.05. wurden $22.78 verbraucht statt der erlaubten $5 → 4.5× Cap-Überschreitung
4. Der Sonnet-Spike vom 15.05. (1.3M Tokens, "unerklärt" in der Memory) war wahrscheinlich
   genau das Phänomen — Backup-Fallback ungebremst

## Goals

- **Sofort-Effekt:** kein einzelner Backup-Call kostet mehr als nötig
- **Hartes Tagescap:** $5/Tag gilt für ALLE Claude-Pfade
- **Sichtbarkeit:** alle Claude-Calls werden lokal getrackt — Cost-Reports sind verlässlich
- **Reversibel:** alle Änderungen müssen ohne grosse Eingriffe rückgängig zu machen sein

## Non-Goals (für diese Iteration)

- Untersuchen WARUM Backup so oft feuert (separates späteres Spec, "Phase 3")
- Cap im ai-provider-service-Gateway durchsetzen (späteres Spec, multi-tenant later)
- Re-architecting der per-feature-Provider-Config

## Phasen-Plan: 1 → 2A → 2B

Drei Phasen, jede einzeln Production-ready und rollback-fähig.

---

## Phase 1 — Backup-Modell auf Haiku umstellen

**Was:** Eine Zeile SQL.

```sql
UPDATE users
SET ai_provider_backup_model = 'claude-haiku-4-5-20251001'
WHERE id = '03bd2c3d-791e-46f7-b9b8-e1e51840c05d';
```

**Warum Haiku statt Sonnet:**
- Für Job-Match-Scoring, CV-Summary, Email-Digest-Parsing reicht Haiku-Quality
  (Console-Daten vom 14.05.-Burst zeigen: 18.435 Haiku-Calls funktional erfolgreich
  als Backup für Job-Match)
- Sonnet ist 3-5× teurer pro Token

**Rollback:** `UPDATE ... SET ai_provider_backup_model = 'claude-sonnet-4-6'`.

**Verifikation:** nächster Backup-Fallback nach dem Update soll Haiku verwenden.
Nachprüfen via Console-Token-Stream oder lokal in `usage_records` von Claudetracker.

---

## Phase 2A — Pragmatic Cut: Backup nur dort, wo getrackt

**Was:** Backup-Fallback wird AUSGESCHALTET für die Features, die nicht in
`api_calls` loggen (cv_summarize, cover_letter, email_parse, pattern_learner).
Der `claude-match`-Cron behält Backup, weil er seinen eigenen Budget-Check hat.

**Wie:** in `services/ai_provider_client.build_fallback_kwargs(user)` — wir lassen
den `feature`-Kontext einfließen. Default: kein Backup. Nur explizite Whitelist
(`feature in ALLOW_BACKUP_FEATURES = {'match'}`) bekommt Backup.

**Code-Skizze:**

```python
ALLOW_BACKUP_FEATURES = {'match'}  # Whitelist: nur diese duerfen Backup nutzen

def build_fallback_kwargs(user, feature: str | None = None) -> dict:
    if feature not in ALLOW_BACKUP_FEATURES:
        return {}
    # bisherige Logik unveraendert
    backup = user.get_backup_config() if user else None
    ...
```

**Caller-Anpassung:** alle ~5 Aufrufer geben jetzt `feature=` mit:
- `pattern_learner.py`: `build_fallback_kwargs(user, feature='pattern_learn')`
- `email_jobs.py` (2 Stellen): `feature='email_parse'`
- `jobs_cron.py` (Match): `feature='match'`
- `cover_letter_service.py` o.ä.: `feature='cover_letter'`

Caller die das `feature`-Argument nicht setzen, bekommen Default `None` → kein
Backup. **Safe by default**.

**Effekt:**
- match-Cron: Backup wie bisher (mit eigenem Budget-Check + Haiku-Modell ab Phase 1)
- alle anderen: bei Ollama-Down → Fail-Loud → User merkt es, weil z.B. cv_summarize
  None liefert oder cover_letter eine Fehlermeldung wirft. Akzeptabel weil bisher
  "still zu Sonnet-fallback" der schlechtere Default war.

**Tests (TDD):**

```python
def test_build_fallback_kwargs_returns_empty_without_feature():
    user = mock_user_with_backup('claude', 'claude-haiku-4-5')
    assert build_fallback_kwargs(user) == {}
    assert build_fallback_kwargs(user, feature=None) == {}

def test_build_fallback_kwargs_returns_empty_for_non_whitelisted_feature():
    user = mock_user_with_backup('claude', 'claude-haiku-4-5')
    assert build_fallback_kwargs(user, feature='email_parse') == {}

def test_build_fallback_kwargs_returns_kwargs_for_whitelisted_feature():
    user = mock_user_with_backup('claude', 'claude-haiku-4-5')
    kw = build_fallback_kwargs(user, feature='match')
    assert kw['fallback_provider'] == 'claude'
    assert kw['fallback_model'] == 'claude-haiku-4-5'
```

**Rollback:** `ALLOW_BACKUP_FEATURES = {'match', 'cv_summarize', 'cover_letter',
'email_parse', 'pattern_learn'}` setzen oder Whitelist-Check entfernen.

---

## Phase 2B — Zentrales Cost-Tracking + Cap im chat()-Wrapper

**Vorbedingung:** Phase 2A ist live.

**Ziel:** echte Cost-Sichtbarkeit + Budget-Cap überall, damit Backup für ALLE
Features sicher (re-)aktiviert werden kann.

**Architektur:**

1. **`services/cost_tracker.py` (neu):**
   ```python
   def record_call(user_id, endpoint, model, tokens_in, tokens_out, cost_usd, key_owner='server'):
       """Zentralisierter ApiCall-Insert. Ersetzt die zwei lokalen Inserts in jobs_cron."""
       db.session.add(ApiCall(...))
       db.session.flush()

   def user_today_cost_cents(user_id: str) -> int:
       # bisherige Impl aus jobs_cron extrahiert
       ...

   def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
       # modell-aware (haiku-pricing vs sonnet-pricing)
       ...
   ```

2. **`services/ai_provider_client.chat()` Wrapper:**
   - **VOR call:** wenn `fallback_provider == 'claude'` (oder fallback_model enthält "claude"):
     - Prüfe `user_today_cost_cents(user_id) >= user.job_daily_budget_cents`
     - Wenn überschritten: `fallback_*`-kwargs stripen, Log-Warning, weiter ohne Backup
   - **NACH call:** wenn `response.fallback_used`:
     - `record_call(user_id, endpoint='ai_provider_client', model=response.model, tokens_in=resp.usage.input_tokens, tokens_out=resp.usage.output_tokens, cost_usd=estimate_cost_usd(...))`

3. **`jobs_cron.py`-Cleanup:** die zwei lokalen `db.session.add(ApiCall(...))` durch
   `cost_tracker.record_call(...)` ersetzen. Single Source of Truth.

4. **Phase 2A revert:** ALLOW_BACKUP_FEATURES erweitern auf alle Features, weil
   jetzt globaler Cap überall greift.

**Tests (TDD):**

```python
def test_chat_strips_claude_fallback_when_budget_exhausted(monkeypatch):
    monkeypatch.setattr('services.cost_tracker.user_today_cost_cents',
                        lambda uid: 500)
    user = mock_user(daily_budget_cents=500)
    client = AIProviderClient()
    captured = capture_post_body(client, monkeypatch)
    client.chat(user_id=user.id, provider='ollama', model='x',
                fallback_provider='claude', fallback_model='claude-haiku-4-5-20251001',
                messages=[])
    assert 'fallback_provider' not in captured

def test_chat_keeps_fallback_when_budget_remaining(...): ...

def test_chat_records_cost_on_fallback_used(...):
    # response.fallback_used=True → record_call wird aufgerufen
    ...

def test_chat_records_zero_cost_on_ollama_primary(...):
    # response.fallback_used=False, provider=ollama → record_call mit cost=0
    ...

def test_chat_keeps_non_claude_fallback_unconditionally(...):
    # fallback_provider='ollama' → nicht gecapped (Ollama hat kein Cost)
    ...
```

**Edge-Cases:**
- Wenn `user_today_cost_cents` selbst fehlschlägt (DB-Issue): permissiv durchlassen
  + Log-Warning. Wir wollen nicht dass ein Cost-Tracking-Bug den Hauptpfad killt.
- Race condition: andere Caller könnten parallel den Backup ausgelöst haben →
  akzeptiert, Worst-Case 1-2 Calls über Cap.

**Rollback:** wie immer in Phasen — wenn 2B aufkippt, 2A bleibt drin (sicherer
Zustand). 1+2A allein sind production-ready.

---

## Reihenfolge & Erfolgs-Metriken

1. **Phase 1** (5 Min): SQL-Update durchführen, in 24h prüfen ob `usage_records`
   in Claudetracker `Anthropic API (bewerbungstracker)` mit haiku-Preisen erscheint
   (≤ $5/Tag statt $22).
2. **Phase 2A** (~45 Min): Whitelist-Code, TDD-Tests, deploy. In 24h prüfen ob
   die nicht-match-Features beim Ollama-Down sauber fehlerhaft enden statt Backup
   zu nutzen.
3. **Phase 2B** (~3-4h, eigenes implementation-plan): Cost-Tracker zentralisieren,
   chat()-Wrapper, Tests. In 24h prüfen ob alle Claude-Calls in `api_calls`
   erscheinen UND `user_today_cost_cents()` als Cap funktioniert.

## Verwandte Memories
- `incident_claude_cost_burst_2026_05_22.md` — Ursachenanalyse, hier setzt der Fix an
- `incident_claude_cost_burst_2026_05_14.md` — frühere Burst, ähnliches Pattern
- `feedback_ai_endpoint_user_provider.md` — Anti-Pattern Hardcoded `provider='claude'`
- `project_ai_provider_fallback_pattern.md` — der per-request-Fallback-Mechanismus
