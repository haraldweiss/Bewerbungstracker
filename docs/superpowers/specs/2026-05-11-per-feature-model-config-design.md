# Per-Feature Model-Konfiguration mit Empfehlungs-Engine — Design Specification

**Date:** 2026-05-11
**Author:** Harald Weiss
**Status:** Approved for Implementation

---

## Overview

Der User soll für jeden KI-Task (Job-Matching, Cover-Letter, Email-Analyse, CV-Summarize) ein eigenes Modell konfigurieren können — mit einem Standard-Modell als Default und optionalen Overrides pro Task. Eine heuristische Empfehlungs-Engine im Frontend bewertet jedes verfügbare Modell für jede Task (✅ empfohlen / ⚠️ suboptimal / ❌ wird scheitern) basierend auf Model-Name-Parsing (Parameter-Count, Familie, Reasoning-Flag).

Hintergrund: Bisher hat jeder User _ein_ globales Modell (`User.ai_provider`/`User.ai_provider_model`). Das funktioniert für Job-Matching (Mistral-Nemo 12B liefert OK JSON), aber Cover-Letter braucht ein stärkeres Modell. Statt User zu zwingen vor jedem Cover-Letter-Generate manuell zu switchen, soll er Pro-Task konfigurieren können.

---

## 1. Data Model

### Neue Spalte in `users`

```python
class User(db.Model):
    # ... existing fields ...
    feature_model_overrides = db.Column(db.Text, nullable=True)  # JSON
```

### JSON-Format

```json
{
  "match": {"provider": "ollama", "model": "mistral-nemo:12b-instruct-2407-q5_K_M"},
  "cover_letter": {"provider": "claude", "model": "claude-haiku-4-5-20251001"},
  "email_analyse": null,
  "cv_summarize": null
}
```

- Schlüssel: `match`, `cover_letter`, `email_analyse`, `cv_summarize` (whitelisted)
- Wert: `null` oder Object mit `provider` (required) + `model` (optional)
- Fehlender Schlüssel = `null` = Fallback auf Standard

### Helper-Method auf User

```python
def get_model_for(self, feature: str) -> tuple[str, Optional[str]]:
    """Returns (provider, model) für Feature mit Fallback auf Standard.

    Feature-Keys: 'match', 'cover_letter', 'email_analyse', 'cv_summarize'.
    Bei malformed JSON oder fehlendem Override → Fallback auf
    user.ai_provider / user.ai_provider_model.
    """
    try:
        overrides = json.loads(self.feature_model_overrides or '{}')
    except (json.JSONDecodeError, TypeError):
        overrides = {}
    override = overrides.get(feature)
    if override and override.get('provider'):
        return override['provider'], override.get('model')
    return self.ai_provider, self.ai_provider_model
```

### Alembic-Migration

`a8c9d0e1f2g3_add_feature_model_overrides.py` (down_revision = `a7b8c9d0e1f2`):

```python
def upgrade():
    op.add_column('users', sa.Column('feature_model_overrides', sa.Text, nullable=True))

def downgrade():
    op.drop_column('users', 'feature_model_overrides')
```

---

## 2. Backend Integration

### Service-Layer Anpassungen

Bestehende Endpoints, die aktuell `user.ai_provider`/`user.ai_provider_model` lesen, switchen auf `user.get_model_for(feature)`:

| Datei | Feature-Key | Aktuell |
|-------|-------------|---------|
| `api/cover_letters.py:generate_cover_letter` | `cover_letter` | bereits provider+model parameter — nur Source ändern |
| `api/jobs_user.py:score_match` | `match` | aktuell hardcoded auf `user.ai_provider`/`_model` |
| `api/jobs_cron.py:_run_claude_match_for` | `match` | dito |
| `api/jobs_cron.py:_summarize_description` | `cv_summarize` | dito |
| `claude_integration.py:analyze_email` | `email_analyse` | (falls aktiviert; aktuell inaktiv) |

### Neue Endpoints in `api/profile.py`

```python
@profile_bp.get('/feature-models')
@token_required
def get_feature_models(user):
    return jsonify({
        'standard': {
            'provider': user.ai_provider,
            'model': user.ai_provider_model,
        },
        'overrides': json.loads(user.feature_model_overrides or '{}'),
    })

@profile_bp.patch('/feature-models')
@token_required
def update_feature_models(user):
    data = request.get_json() or {}
    overrides = data.get('overrides') or {}

    VALID_FEATURES = {'match', 'cover_letter', 'email_analyse', 'cv_summarize'}
    VALID_PROVIDERS = {'claude', 'ollama', 'openai', 'mammouth', 'custom'}

    for feat, cfg in overrides.items():
        if feat not in VALID_FEATURES:
            return jsonify({'error': f'Unknown feature: {feat}'}), 400
        if cfg is None:
            continue
        if not isinstance(cfg, dict):
            return jsonify({'error': f'{feat} muss Object oder null sein'}), 400
        if cfg.get('provider') and cfg['provider'] not in VALID_PROVIDERS:
            return jsonify({'error': f'Unknown provider: {cfg["provider"]}'}), 400

    user.feature_model_overrides = json.dumps(overrides, ensure_ascii=False)
    db.session.commit()
    return jsonify({'status': 'updated', 'overrides': overrides}), 200
```

---

## 3. Empfehlungs-Engine (Frontend)

### Speicherort

Inline in `index.html` (folgt Project-Pattern — keine separaten JS-Files für neue Module).

### Capability-Score Funktion (0-100)

```javascript
function capabilityScore(provider, model) {
    if (!model) return 50;
    const m = model.toLowerCase();

    // Cloud-Modelle: Whitelist
    const CLOUD = [
        ['claude-opus', 98],
        ['claude-sonnet-4', 92],
        ['claude-sonnet-3.5', 88],
        ['claude-haiku-4-5', 82],
        ['claude-haiku-3', 65],
        ['gpt-4o', 92],
        ['gpt-4-turbo', 90],
        ['gpt-4', 88],
        ['gpt-3.5', 60],
        ['o1', 95], ['o3', 96],
        ['gemini-1.5-pro', 90],
        ['gemini-1.5-flash', 70],
    ];
    for (const [pattern, score] of CLOUD) {
        if (m.includes(pattern)) return score;
    }

    // Open-Source: Parameter-Count
    const paramMatch = m.match(/(\d+)b\b/);
    const params = paramMatch ? parseInt(paramMatch[1], 10) : null;

    let score = 50;
    if (params) {
        if (params >= 400)     score = 95;
        else if (params >= 70) score = 88;
        else if (params >= 30) score = 78;
        else if (params >= 13) score = 65;
        else if (params >= 7)  score = 50;
        else                   score = 30;
    }

    // Familie-Modifier
    if (m.includes('qwen2.5') || m.includes('qwen3')) score += 5;
    if (m.includes('llama3.1') || m.includes('llama3.2') || m.includes('llama3.3')) score += 3;
    if (m.includes('deepseek')) score += 5;
    if (m.includes('phi-3') || m.includes('phi3')) score -= 5;

    return Math.min(100, Math.max(0, score));
}
```

### Task-Schwellen

```javascript
const TASK_THRESHOLDS = {
    match:         { ok: 60, warn: 40, label: 'Job-Matching' },
    cover_letter:  { ok: 75, warn: 55, label: 'Cover-Letter' },
    cv_summarize:  { ok: 65, warn: 45, label: 'CV-Summarize' },
    email_analyse: { ok: 50, warn: 30, label: 'Email-Analyse' },
};

function recommendation(provider, model, feature) {
    let score = capabilityScore(provider, model);
    const isReasoning = /(thinking|\br1\b|\bo1\b|\bo3\b)/i.test(model || '');
    if (isReasoning && (feature === 'cover_letter' || feature === 'match')) score += 8;

    const t = TASK_THRESHOLDS[feature];
    if (score >= t.ok)   return { level: 'ok',   icon: '✅', text: 'Empfohlen' };
    if (score >= t.warn) return { level: 'warn', icon: '⚠️', text: 'Geht, aber suboptimal' };
    return                       { level: 'bad',  icon: '❌', text: 'Wird vermutlich scheitern' };
}
```

### Bekannte Limits

- Heuristik kennt keine "echten" Benchmark-Ergebnisse — nur Name-Parsing
- Custom-Endpoints sind unbekannt → Score 50 (neutral, alle Tasks ⚠️)
- Quantization-Level (q4/q5/q8) wird ignoriert (kaum Impact für unsere Zwecke)
- Mistral-Nemo wird per Param-Count auf 65 gescored → ⚠️ für Cover-Letter (Schwelle 75) ✅ für Match (Schwelle 60). Genau das gewünschte Verhalten.

---

## 4. UI-Layout (Settings)

### Bestehende Standard-Sektion bleibt unverändert

```
┌──────────────────────────────────────────────────────────────────┐
│ 🤖 KI Provider (Standard)                                        │
│   [Provider-Dropdown: Ollama ▼]                                  │
│   [Modell-Dropdown: mistral-nemo:12b-instruct... ▼]              │
│   ℹ️ Wird für alle KI-Tasks genutzt sofern unten kein Override    │
└──────────────────────────────────────────────────────────────────┘
```

### Neue Sektion darunter

```
┌──────────────────────────────────────────────────────────────────┐
│ 🎯 Pro-Task-Modelle (optional)                                   │
│                                                                  │
│ Wenn du verschiedene Modelle für verschiedene Tasks nutzen       │
│ willst — z.B. ein kleines lokales Modell für Job-Matching        │
│ aber Claude für Cover-Letter.                                    │
│                                                                  │
│ ▼ Job-Matching             ✅ Standard reicht                    │
│ ▼ Cover-Letter             ⚠️ Override empfohlen                 │
│ ▶ Email-Analyse            ✅ Standard reicht                    │
│ ▶ CV-Summarize             ✅ Standard reicht                    │
│                                                                  │
│ [📊 Alle Modelle vergleichen]                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Aufgeklappte Override-Card

```
▼ Cover-Letter

  ☐ Eigenes Modell für diese Task (sonst: Standard)

  [Provider: Claude ▼]    [Modell: claude-haiku-4-5 ▼]

  Empfehlungen für dieses Modell:
    Job-Matching:  ✅ Empfohlen
    Cover-Letter:  ✅ Empfohlen ← aktiv für diese Task
    CV-Summarize:  ✅ Empfohlen
    Email-Analyse: ✅ Empfohlen

  [💾 Speichern]
```

### Empfehlungs-Tabelle (Modal)

Click auf "Alle Modelle vergleichen" → Modal mit Tabelle aller in den Providers verfügbaren Modelle × 4 Tasks:

```
Modell                            Match  Cover  CV-Sum  Email
─────────────────────────────────────────────────────────────
claude-haiku-4-5                  ✅     ✅     ✅      ✅
claude-opus-4-7                   ✅     ✅     ✅      ✅
mistral-nemo:12b                  ✅     ⚠️     ✅      ✅
llama3.1:8b                       ⚠️     ❌     ⚠️      ✅
qwen2.5:32b                       ✅     ✅     ✅      ✅
```

Click auf eine Zelle (✅/⚠️/❌) übernimmt Modell+Provider als Override für die jeweilige Task.

---

## 5. Data Flow

### On Settings-Page Open

1. `GET /api/profile/feature-models` → returns `{standard, overrides}`
2. `GET /api/providers` → liste verfügbarer Provider
3. Für jeden konfigurierten Provider: `GET /api/providers/{provider}/models` → lade verfügbare Modelle (gefetched on-demand wenn User Override-Card aufklappt)
4. Frontend rendert Standard + 4 collapsed Override-Cards mit aktuellem Empfehlungs-Status

### On Override Activation (Checkbox + Save)

1. User klickt Checkbox "Eigenes Modell für diese Task"
2. Dropdowns werden aktiv
3. User wählt Provider + Modell, Frontend zeigt live Empfehlungs-Badges
4. Click auf "💾 Speichern" → `PATCH /api/profile/feature-models` mit kompletten Overrides-JSON
5. Bei 200: Toast "Gespeichert ✓", Card collapsed mit neuem Status

### Wenn KI-Task läuft (z.B. Cover-Letter generieren)

1. Endpoint ruft `user.get_model_for('cover_letter')` → tuple `(provider, model)`
2. Tuple wird an Service-Layer weitergereicht
3. Service ruft `ai_provider_client.chat(provider=provider, model=model, ...)` an

---

## 6. Error Handling

| Szenario | Verhalten |
|----------|-----------|
| `feature_model_overrides` ist malformed JSON | `get_model_for()` catched, fallback auf Standard |
| Override-Provider ist konfiguriert aber nicht "configured" (kein API-Key) | Existing `ai_provider_client` Fehler → 503 mit "Provider X nicht erreichbar" |
| Override-Model existiert nicht beim Provider | Existing 404/error vom ai-provider-service |
| User PATCH-t ungültigen Feature-Key | 400 mit klarer Message |
| User PATCH-t ungültigen Provider | 400 mit klarer Message |
| User cleared Override (Checkbox aus) | Frontend setzt `overrides[feat] = null`, PATCH → Backend speichert null, `get_model_for()` fällt zurück auf Standard |
| Cloud-Modelle vs. Open-Source: Score von 50 für Custom-Endpoints | UI zeigt "❔ Unbekannt — bitte selbst testen" als zusätzliches Label (nicht Wertung) |

---

## 7. Tests

### Backend

- `tests/test_user_get_model_for.py` (neu):
  - Fallback wenn keine Overrides
  - Fallback bei malformed JSON
  - Override für 'match' returnt korrekte Werte
  - Override mit nur `provider` (kein `model`) → returnt `(provider, None)`
  - Unknown feature-key → fallback

- `tests/api/test_feature_models.py` (neu):
  - GET ohne Auth → 401
  - GET mit Auth → returns `{standard, overrides}`
  - PATCH mit valid overrides → 200, DB aktualisiert
  - PATCH mit `null` für eine Task → 200, override entfernt
  - PATCH mit unknown feature → 400
  - PATCH mit unknown provider → 400
  - User-Isolation (anderer User sieht nicht)

- Bestehende Tests in `tests/api/test_cover_letters.py`, `tests/api/test_jobs_user.py` etc. müssen weiter grün bleiben (sie nutzen `user.ai_provider_model` → Default-Path bleibt unverändert)

### Frontend

- Manuelle Verifikation (Browser-Test)
- Empfehlungs-Engine ist heuristisch → nur kosmetisch, easy to tune nach Live-Test

---

## 8. Scope & Constraints

✅ **In Scope:**
- DB-Migration + Helper-Method
- 2 neue Profile-Endpoints
- Service-Layer-Integration für Cover-Letter, Match, CV-Summarize, Email-Analyse
- UI: Standard bleibt, 4 Override-Cards, Empfehlungs-Tabelle als Modal
- Heuristische Empfehlungs-Engine inline in index.html
- SW-Cache-Bump (v8 → v9) wegen Frontend-Änderungen

⏭️ **Out of Scope (Future):**
- Echte Benchmark-Daten (nur Heuristik)
- A/B-Testing verschiedener Modelle
- Pro-Task-Budget-Limits
- Auto-Switch bei Provider-Ausfall

---

## 9. Risiken & Mitigation

| Risiko | Mitigation |
|--------|------------|
| Migration auf VPS bricht andere Code-Pfade | Spalte ist nullable, alle Aufrufe via `get_model_for()` mit Fallback → Zero Breaking Change |
| Service-Worker zeigt alte UI | Cache-Name bump v8 → v9 mit-committen (siehe Memory `feedback_frontend_release_sw_bump`) |
| Empfehlungs-Engine bewertet falsch | Heuristisch und im Frontend → nur kosmetisch, User hat Final-Word, easy to tune |
| Korrupter JSON in DB | `get_model_for()` catched JSONDecodeError → Fallback auf Standard |

---

## 10. Success Criteria

- ✅ User kann pro Task ein anderes Modell wählen oder den Standard nutzen
- ✅ Empfehlungs-Badges sind sichtbar im Settings UI
- ✅ Override-Cards sind klar als "optional" gekennzeichnet
- ✅ Bestehender Job-Matching-Flow funktioniert ohne Änderungen (Default-Path)
- ✅ Cover-Letter mit Claude-Haiku als Override generiert sauberes JSON + deutsches Anschreiben
- ✅ Empfehlungs-Tabelle (Modal) zeigt alle Modelle × Tasks korrekt bewertet
- ✅ Alle bestehenden Tests bleiben grün
- ✅ Migration auf VPS läuft ohne Daten-Verlust

---

## 11. Implementation Phases

**Phase 1: Backend Foundation**
- Alembic-Migration
- User.get_model_for() Helper + Tests
- Profile-Endpoints (GET/PATCH /feature-models) + Tests

**Phase 2: Service-Layer Integration**
- api/cover_letters.py auf get_model_for umstellen
- api/jobs_user.py + api/jobs_cron.py auf get_model_for umstellen
- claude_integration.py (analyze_email) auf get_model_for umstellen

**Phase 3: Frontend UI**
- Empfehlungs-Engine (capabilityScore, recommendation) inline
- 4 Override-Cards in Settings-View
- Empfehlungs-Tabelle Modal
- Save/Load via neue Endpoints
- Service-Worker-Cache-Bump
