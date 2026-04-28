# Job-Discovery Phase C — Frontend-Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend-Integration für Phase A+B: neuer Tab "Job-Vorschläge" mit Filter-Bar und Karten-Liste, Settings-Bereiche für Quellen-Verwaltung und KI-Konfiguration. Macht das Feature user-facing.

**Architecture:** Vanilla-JS-Modul `frontend/js/job-discovery.js`, eingebunden in `index.html`. Drei UI-Bereiche: (1) Job-Vorschläge-View mit Karten-Liste, (2) Settings-Tab "Job-Suche" für Quellen, (3) Settings-Tab "KI-Konfiguration" für AI-Credentials. Alle API-Calls über bestehenden `fetchAPI()`-Helper, wiederverwendet die existierenden Modal-/Tab-Patterns.

**Tech Stack:** Vanilla JS (ES6+), HTML5, CSS3 — passt zum existierenden Frontend-Stack. Kein Framework-Build, keine TypeScript-Compilation.

**Voraussetzung:** Phase A + Phase B laufen (alle Backend-APIs verfügbar).

**Spec:** [docs/superpowers/specs/2026-04-28-job-discovery-design.md](../specs/2026-04-28-job-discovery-design.md) — Sektion 6.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `frontend/js/job-discovery.js` | Hauptmodul: View-Render + State + API-Calls |
| `frontend/js/job-discovery-sources.js` | Quellen-Settings-UI |
| `frontend/js/job-discovery-credentials.js` | KI-Credentials-Settings-UI |
| `frontend/job-discovery.css` | Job-spezifische Styles (Karten-Layout, Score-Badge) |
| `index.html` | + Navigation-Eintrag, View-Container, Settings-Tabs, Skript-Imports |
| `app.py` | + Static-Routes für die neuen JS-Dateien |
| `tests/frontend/job-discovery.test.js` | (optional) Vanilla-JS Tests |

---

## Task 1: Static-Routes & Skript-Einbindung

**Files:**
- Modify: `app.py`
- Modify: `index.html`

- [ ] **Step 1: Static-Route für Job-Discovery-Skripte ergänzen**

In `app.py` bei den anderen `@app.route('/frontend/...')`-Routen ergänzen:
```python
@app.route('/frontend/js/job-discovery.js')
def job_discovery_js():
    return send_file('frontend/js/job-discovery.js')

@app.route('/frontend/js/job-discovery-sources.js')
def job_discovery_sources_js():
    return send_file('frontend/js/job-discovery-sources.js')

@app.route('/frontend/js/job-discovery-credentials.js')
def job_discovery_credentials_js():
    return send_file('frontend/js/job-discovery-credentials.js')

@app.route('/frontend/job-discovery.css')
def job_discovery_css():
    return send_file('frontend/job-discovery.css')
```

- [ ] **Step 2: Skripte und CSS in `index.html` einbinden**

Im `<head>` nach den anderen CSS/JS-Includes einfügen:
```html
<link rel="stylesheet" href="/frontend/job-discovery.css">
<script src="/frontend/js/job-discovery.js" defer></script>
<script src="/frontend/js/job-discovery-sources.js" defer></script>
<script src="/frontend/js/job-discovery-credentials.js" defer></script>
```

- [ ] **Step 3: Kontroll-Run**

Server starten:
```bash
flask run
```
Im Browser http://localhost:5000 öffnen, in DevTools Network-Tab prüfen: alle 4 neuen Files liefern 200 (auch wenn sie noch leer sind).

- [ ] **Step 4: Leere Stub-Files anlegen**

```bash
mkdir -p frontend/js
echo "// job-discovery main module" > frontend/js/job-discovery.js
echo "// job-discovery sources UI" > frontend/js/job-discovery-sources.js
echo "// job-discovery credentials UI" > frontend/js/job-discovery-credentials.js
echo "/* Job-Discovery Styles */" > frontend/job-discovery.css
```

- [ ] **Step 5: Commit**

```bash
git add app.py index.html frontend/js/job-discovery.js frontend/js/job-discovery-sources.js frontend/js/job-discovery-credentials.js frontend/job-discovery.css
git commit -m "feat: Static-Routes + Skript-Stubs für Job-Discovery Frontend"
```

---

## Task 2: Navigation + View-Container in index.html

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Navigation-Eintrag finden**

Suche im `index.html` nach der bestehenden Navigation, z.B.:
```bash
grep -n 'showView\|class="nav-item"\|onclick.*showView' index.html | head -10
```

- [ ] **Step 2: Navigations-Button für "Job-Vorschläge" ergänzen**

Füge bei den anderen Navigations-Items hinzu:
```html
<button class="nav-item" onclick="showView('jobs')" id="nav-jobs">
    🔍 Job-Vorschläge
    <span id="nav-jobs-badge" class="badge" style="display:none">0</span>
</button>
```

- [ ] **Step 3: View-Container hinzufügen**

Bei den anderen View-Containern (`<div id="view-...">`) ergänzen:
```html
<div id="view-jobs" class="view" style="display:none">
    <h2>🔍 Job-Vorschläge</h2>

    <!-- Filter-Bar -->
    <div class="card jd-filter-bar">
        <div class="jd-filter-row">
            <label>Mindest-Match-Score:
                <input type="range" id="jd-min-score" min="0" max="100" value="60">
                <span id="jd-min-score-display">60</span>
            </label>
            <label>Status:
                <select id="jd-status-filter" multiple>
                    <option value="new" selected>Neu</option>
                    <option value="seen">Gesehen</option>
                    <option value="imported">Übernommen</option>
                    <option value="dismissed">Verworfen</option>
                </select>
            </label>
            <label>Quelle:
                <select id="jd-source-filter">
                    <option value="">Alle</option>
                </select>
            </label>
            <input type="text" id="jd-search" placeholder="Titel/Firma suchen…">
            <button class="btn btn-primary btn-sm" onclick="JobDiscovery.refresh()">🔄 Aktualisieren</button>
        </div>
        <div id="jd-stats" class="jd-stats"></div>
    </div>

    <!-- Match-Karten -->
    <div id="jd-matches-list" class="jd-matches-list">
        <p class="text-muted">Lade Vorschläge…</p>
    </div>

    <!-- Pagination -->
    <div class="jd-pagination">
        <button class="btn btn-sm" onclick="JobDiscovery.prevPage()" id="jd-prev">← Zurück</button>
        <span id="jd-page-info">Seite 1</span>
        <button class="btn btn-sm" onclick="JobDiscovery.nextPage()" id="jd-next">Weiter →</button>
    </div>
</div>
```

- [ ] **Step 4: Hook in `showView`-Funktion**

Suche `function showView(name)` in `index.html` und ergänze am Anfang/Ende des Switch-Blocks (oder wo passend):
```javascript
if (name === 'jobs') {
    JobDiscovery.onShow();
}
```

- [ ] **Step 5: Manuell testen — Browser**

Server neu starten, "Job-Vorschläge"-Button klicken — leere View mit "Lade Vorschläge…" sollte erscheinen, keine JS-Errors in DevTools-Console.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat: Navigation + View-Container für Job-Vorschläge in index.html"
```

---

## Task 3: Job-Discovery JS-Hauptmodul (List-Logik)

**Files:**
- Modify: `frontend/js/job-discovery.js`

- [ ] **Step 1: Modul-Skelett mit State + Render**

Komplette Datei `frontend/js/job-discovery.js` schreiben:
```javascript
/**
 * Job-Discovery: Match-Listing + Karten-UI.
 *
 * Globaler Namespace: window.JobDiscovery
 * Abhängigkeiten: window.fetchAPI() (aus index.html)
 */
(function () {
    'use strict';

    const state = {
        matches: [],
        total: 0,
        offset: 0,
        limit: 50,
        sources: [],
        filters: {
            minScore: 60,
            statuses: ['new'],
            sourceId: null,
            q: '',
        },
    };

    function $(id) { return document.getElementById(id); }

    async function fetchSources() {
        const r = await window.fetchAPI('/api/jobs/sources');
        state.sources = (r && r.sources) || [];
        const sel = $('jd-source-filter');
        if (sel) {
            sel.innerHTML = '<option value="">Alle Quellen</option>' +
                state.sources.map(s =>
                    `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
        }
    }

    async function fetchMatches() {
        const params = new URLSearchParams();
        params.set('min_score', state.filters.minScore);
        state.filters.statuses.forEach(s => params.append('status', s));
        if (state.filters.sourceId) params.set('source_id', state.filters.sourceId);
        if (state.filters.q) params.set('q', state.filters.q);
        params.set('limit', state.limit);
        params.set('offset', state.offset);

        const r = await window.fetchAPI(`/api/jobs/matches?${params.toString()}`);
        state.matches = (r && r.matches) || [];
        state.total = (r && r.total) || 0;
        render();
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[ch]));
    }

    function badgeColor(score) {
        if (score == null) return '⚪';
        if (score >= 80) return '🟢';
        if (score >= 60) return '🟡';
        return '⚪';
    }

    function renderCard(m) {
        const raw = m.raw_job || {};
        const score = m.match_score != null ? m.match_score.toFixed(0) : '–';
        const dateStr = raw.posted_at
            ? new Date(raw.posted_at).toLocaleDateString('de-DE')
            : '';
        const missing = (m.missing_skills || []).slice(0, 5);

        return `
        <div class="jd-card" data-id="${m.id}">
            <div class="jd-card-header">
                <span class="jd-score-badge">${badgeColor(m.match_score)} ${score}</span>
                <h3 class="jd-card-title">${escapeHtml(raw.title)}</h3>
                <div class="jd-card-meta">
                    ${escapeHtml(raw.company || '')} ·
                    ${escapeHtml(raw.location || '')} ·
                    ${dateStr} · ${escapeHtml(raw.source_name || '')}
                </div>
            </div>
            ${m.match_reasoning ? `
                <p class="jd-card-reasoning">${escapeHtml(m.match_reasoning)}</p>
            ` : ''}
            ${missing.length ? `
                <p class="jd-card-missing">
                    ⚠ Fehlt im CV: ${missing.map(s => `<span class="jd-skill-pill">${escapeHtml(s)}</span>`).join('')}
                </p>
            ` : ''}
            <div class="jd-card-actions">
                <a href="${escapeHtml(raw.url)}" target="_blank" rel="noopener noreferrer"
                   class="btn btn-sm">🔗 Original ansehen</a>
                <button class="btn btn-sm btn-primary"
                        onclick="JobDiscovery.importMatch(${m.id})">📥 Übernehmen</button>
                <button class="btn btn-sm btn-warning"
                        onclick="JobDiscovery.dismissMatch(${m.id})">🗑️ Verwerfen</button>
                <button class="btn btn-sm"
                        onclick="JobDiscovery.markSeen(${m.id})">👁 Verbergen</button>
            </div>
        </div>`;
    }

    function render() {
        const container = $('jd-matches-list');
        if (!container) return;

        if (!state.matches.length) {
            container.innerHTML = `<p class="text-muted">Keine Vorschläge gefunden.
                Hast du Quellen aktiviert und mind. einen Pipeline-Lauf abgewartet?</p>`;
        } else {
            container.innerHTML = state.matches.map(renderCard).join('');
        }

        const stats = $('jd-stats');
        if (stats) {
            stats.textContent = `${state.matches.length} von ${state.total} Vorschlägen`;
        }

        const pageInfo = $('jd-page-info');
        if (pageInfo) {
            const page = Math.floor(state.offset / state.limit) + 1;
            const totalPages = Math.max(1, Math.ceil(state.total / state.limit));
            pageInfo.textContent = `Seite ${page} / ${totalPages}`;
        }
        $('jd-prev').disabled = state.offset === 0;
        $('jd-next').disabled = state.offset + state.limit >= state.total;
    }

    function bindFilterEvents() {
        $('jd-min-score').addEventListener('input', e => {
            state.filters.minScore = parseInt(e.target.value, 10);
            $('jd-min-score-display').textContent = e.target.value;
        });
        $('jd-min-score').addEventListener('change', () => {
            state.offset = 0; fetchMatches();
        });

        $('jd-status-filter').addEventListener('change', e => {
            state.filters.statuses = Array.from(e.target.selectedOptions).map(o => o.value);
            state.offset = 0; fetchMatches();
        });

        $('jd-source-filter').addEventListener('change', e => {
            state.filters.sourceId = e.target.value || null;
            state.offset = 0; fetchMatches();
        });

        let searchTimer = null;
        $('jd-search').addEventListener('input', e => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                state.filters.q = e.target.value;
                state.offset = 0; fetchMatches();
            }, 300);
        });
    }

    let initialized = false;
    function onShow() {
        if (!initialized) {
            bindFilterEvents();
            initialized = true;
        }
        fetchSources().then(fetchMatches);
        updateBadgeCount();
    }

    async function refresh() { await fetchMatches(); }

    function nextPage() {
        if (state.offset + state.limit < state.total) {
            state.offset += state.limit;
            fetchMatches();
        }
    }
    function prevPage() {
        if (state.offset > 0) {
            state.offset = Math.max(0, state.offset - state.limit);
            fetchMatches();
        }
    }

    async function importMatch(id) {
        if (!confirm('Diese Stelle als Bewerbung übernehmen?')) return;
        try {
            const r = await window.fetchAPI(`/api/jobs/matches/${id}/import`, { method: 'POST' });
            if (r && r.application_id) {
                alert(`✅ Bewerbung erstellt (ID ${r.application_id}). Du findest sie in deiner Liste.`);
                fetchMatches();
            }
        } catch (e) {
            alert('❌ Fehler bei Übernahme: ' + e.message);
        }
    }

    async function dismissMatch(id) {
        await window.fetchAPI(`/api/jobs/matches/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status: 'dismissed' }),
        });
        fetchMatches();
    }

    async function markSeen(id) {
        await window.fetchAPI(`/api/jobs/matches/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status: 'seen' }),
        });
        fetchMatches();
    }

    async function updateBadgeCount() {
        try {
            const r = await window.fetchAPI('/api/jobs/matches?status=new&min_score=80&limit=1');
            const badge = $('nav-jobs-badge');
            if (badge && r) {
                if (r.total > 0) {
                    badge.textContent = r.total;
                    badge.style.display = '';
                } else {
                    badge.style.display = 'none';
                }
            }
        } catch (e) {
            // silent
        }
    }

    // Public API
    window.JobDiscovery = {
        onShow, refresh, nextPage, prevPage,
        importMatch, dismissMatch, markSeen,
        updateBadgeCount,
    };

    // Badge alle 5 Min aktualisieren
    setInterval(updateBadgeCount, 5 * 60 * 1000);
})();
```

- [ ] **Step 2: CSS schreiben**

`frontend/job-discovery.css`:
```css
/* Job-Discovery Styles */

.jd-filter-bar { padding: 12px; }
.jd-filter-row {
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
}
.jd-filter-row label {
    display: flex; align-items: center; gap: 6px; font-size: 0.9em;
}
.jd-stats {
    margin-top: 8px; color: var(--text-muted); font-size: 0.85em;
}

.jd-matches-list { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }

.jd-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px;
    transition: border-color .15s;
}
.jd-card:hover { border-color: var(--primary-light); }

.jd-card-header { display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.jd-score-badge {
    background: var(--bg-card2); padding: 6px 12px;
    border-radius: 999px; font-weight: 600; font-size: 1.05em; flex-shrink: 0;
}
.jd-card-title {
    margin: 0; flex: 1; min-width: 200px; font-size: 1.1em;
}
.jd-card-meta {
    flex-basis: 100%; color: var(--text-muted); font-size: 0.85em; margin-top: 4px;
}
.jd-card-reasoning {
    margin: 12px 0 8px 0; color: var(--text);
    border-left: 3px solid var(--primary); padding-left: 10px; font-style: italic;
}
.jd-card-missing { color: var(--warning); margin: 8px 0; font-size: 0.9em; }
.jd-skill-pill {
    display: inline-block; background: var(--bg-card2);
    padding: 2px 8px; border-radius: 4px; margin: 0 4px 0 0;
    font-size: 0.85em;
}
.jd-card-actions {
    display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap;
}

.jd-pagination {
    display: flex; gap: 12px; align-items: center; justify-content: center;
    margin: 16px 0; color: var(--text-muted);
}

.badge {
    background: var(--danger); color: white;
    border-radius: 999px; padding: 2px 8px;
    font-size: 0.75em; margin-left: 6px;
}

@media (max-width: 768px) {
    .jd-filter-row { flex-direction: column; align-items: stretch; }
    .jd-card-actions { flex-direction: column; }
    .jd-card-actions .btn { width: 100%; }
}
```

- [ ] **Step 3: Manuelles Browser-Test**

Server starten, einloggen, Tab "🔍 Job-Vorschläge" öffnen.
- Karten sollten erscheinen, falls Backend Pipeline schon Matches erzeugt hat
- Filter (Score-Slider, Status) sollten funktionieren
- "Verwerfen", "Verbergen" sollte den Match aus der Liste nehmen
- "Übernehmen" sollte eine Bewerbung anlegen (sichtbar in Bewerbungen-View)

Bei Empty-State: erstmal Backend-Pipeline triggern:
```bash
curl -X POST http://localhost:5000/api/jobs/crawl-source -H "X-Cron-Token: $TOKEN"
curl -X POST http://localhost:5000/api/jobs/prefilter -H "X-Cron-Token: $TOKEN"
curl -X POST http://localhost:5000/api/jobs/claude-match -H "X-Cron-Token: $TOKEN"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/js/job-discovery.js frontend/job-discovery.css
git commit -m "feat: Job-Vorschläge UI (Karten, Filter, Pagination, Aktions-Buttons)"
```

---

## Task 4: Settings-Tab "Job-Suche" — Quellen-Verwaltung

**Files:**
- Modify: `index.html`
- Modify: `frontend/js/job-discovery-sources.js`

- [ ] **Step 1: Tab in Settings-Bereich hinzufügen**

Im `index.html` den bestehenden Settings-Tabs-Bereich finden:
```bash
grep -n 'showCVTab\|tab-content\|switchTab' index.html | head -10
```
Füge bei den Tab-Buttons einen neuen ergänzen:
```html
<button class="btn btn-secondary btn-sm" onclick="JdSources.show()">🔍 Job-Quellen</button>
```

Und einen Tab-Container:
```html
<div id="jd-sources-tab" class="card" style="display:none;">
    <h3>🔍 Job-Quellen Verwaltung</h3>
    <p class="text-muted">System-Quellen kannst du nicht löschen, nur eigene.</p>

    <div style="margin-bottom: 16px;">
        <button class="btn btn-primary btn-sm" onclick="JdSources.showCreateModal()">
            + Quelle hinzufügen
        </button>
        <button class="btn btn-secondary btn-sm" onclick="JdSources.refresh()">🔄</button>
    </div>

    <table class="jd-sources-table" id="jd-sources-table">
        <thead>
            <tr><th>Name</th><th>Typ</th><th>Status</th><th>Letzter Crawl</th><th>Aktionen</th></tr>
        </thead>
        <tbody id="jd-sources-tbody"></tbody>
    </table>

    <h3 style="margin-top: 24px;">⚙️ Matching-Einstellungen</h3>
    <div class="jd-settings-form">
        <label>Notification-Schwellwert (Match-Score):
            <input type="range" id="jd-set-threshold" min="50" max="95" step="5">
            <span id="jd-set-threshold-display"></span>
        </label>
        <label>Claude-Budget pro Tick:
            <input type="number" id="jd-set-budget-tick" min="1" max="20">
        </label>
        <label>Tagesbudget (Cent):
            <input type="number" id="jd-set-budget-day" min="1" max="500">
        </label>
        <label>Sprachen:
            <select id="jd-set-langs" multiple>
                <option value="de">Deutsch</option>
                <option value="en">English</option>
            </select>
        </label>
        <label>Job-Discovery aktiviert:
            <input type="checkbox" id="jd-set-enabled">
        </label>
        <button class="btn btn-primary" onclick="JdSources.saveSettings()">💾 Speichern</button>
    </div>
</div>
```

- [ ] **Step 2: `frontend/js/job-discovery-sources.js`**

```javascript
/**
 * Job-Discovery Settings: Quellen-Verwaltung + User-Job-Settings.
 */
(function () {
    'use strict';

    const TYPE_LABELS = {
        rss: 'RSS', adzuna: 'Adzuna', bundesagentur: 'Bundesagentur',
        arbeitnow: 'Arbeitnow',
    };

    function $(id) { return document.getElementById(id); }
    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[ch]));
    }

    async function show() {
        // Hide all settings sub-tabs (Pattern aus existing showCVTab)
        document.querySelectorAll('#cv-upload-tab, #cv-compare-tab, #custom-ai-tab, #jd-sources-tab')
            .forEach(el => el.style.display = 'none');
        $('jd-sources-tab').style.display = '';
        await refresh();
        await loadUserSettings();
    }

    async function refresh() {
        const r = await window.fetchAPI('/api/jobs/sources');
        const tbody = $('jd-sources-tbody');
        tbody.innerHTML = ((r && r.sources) || []).map(s => {
            const lastCrawl = s.last_crawled_at
                ? new Date(s.last_crawled_at).toLocaleString('de-DE')
                : '–';
            const status = s.enabled
                ? (s.last_error ? `⚠️ Fehler: ${escapeHtml(s.last_error.substring(0, 60))}` : '✅ Aktiv')
                : '⏸️ Deaktiviert';
            const ownership = s.is_global ? '🌐 Global' : '👤 Eigene';

            return `
            <tr>
                <td>${escapeHtml(s.name)} <small>(${ownership})</small></td>
                <td>${TYPE_LABELS[s.type] || s.type}</td>
                <td>${status}</td>
                <td>${lastCrawl}</td>
                <td>
                    <button class="btn btn-sm" onclick="JdSources.testCrawl(${s.id})"
                            title="Testen">🧪</button>
                    ${s.is_own ? `
                        <button class="btn btn-sm" onclick="JdSources.toggle(${s.id}, ${!s.enabled})"
                                title="${s.enabled ? 'Deaktivieren' : 'Aktivieren'}">
                            ${s.enabled ? '⏸️' : '▶️'}
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="JdSources.del(${s.id})"
                                title="Löschen">🗑️</button>
                    ` : ''}
                </td>
            </tr>`;
        }).join('') || '<tr><td colspan="5" class="text-muted">Keine Quellen vorhanden.</td></tr>';
    }

    async function testCrawl(id) {
        const r = await window.fetchAPI(`/api/jobs/sources/${id}/test-crawl`, { method: 'POST' });
        if (r && r.ok) {
            alert(`✅ Test erfolgreich. ${r.found_jobs} Jobs gefunden.\n\nBeispiel-Titel:\n${(r.sample_titles || []).join('\n')}`);
        } else {
            alert(`❌ Test fehlgeschlagen: ${r && r.error}`);
        }
    }

    async function toggle(id, enabled) {
        await window.fetchAPI(`/api/jobs/sources/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ enabled }),
        });
        refresh();
    }

    async function del(id) {
        if (!confirm('Diese Quelle wirklich löschen?')) return;
        await window.fetchAPI(`/api/jobs/sources/${id}`, { method: 'DELETE' });
        refresh();
    }

    function showCreateModal() {
        const html = `
        <div class="modal-overlay" onclick="JdSources.closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <h3>+ Quelle hinzufügen</h3>
                <label>Typ:
                    <select id="jd-new-type" onchange="JdSources.renderTypeFields()">
                        <option value="rss">RSS-Feed</option>
                        <option value="bundesagentur">Bundesagentur Jobsuche</option>
                        <option value="adzuna">Adzuna</option>
                        <option value="arbeitnow">Arbeitnow</option>
                    </select>
                </label>
                <label>Name (Anzeige):
                    <input type="text" id="jd-new-name" placeholder="z.B. StepStone Berlin Frontend">
                </label>
                <label>Crawl-Intervall (Min):
                    <input type="number" id="jd-new-interval" value="60" min="15" max="1440">
                </label>
                <div id="jd-new-type-fields"></div>
                <div class="modal-actions">
                    <button class="btn" onclick="JdSources.closeModal()">Abbrechen</button>
                    <button class="btn btn-primary" onclick="JdSources.createSource()">Anlegen</button>
                </div>
            </div>
        </div>`;
        const wrap = document.createElement('div');
        wrap.id = 'jd-modal-wrap';
        wrap.innerHTML = html;
        document.body.appendChild(wrap);
        renderTypeFields();
    }

    function renderTypeFields() {
        const t = $('jd-new-type').value;
        const c = $('jd-new-type-fields');
        if (t === 'rss') {
            c.innerHTML = `<label>RSS-URL:
                <input type="url" id="jd-cfg-url" placeholder="https://example.com/feed.xml" required>
            </label>`;
        } else if (t === 'adzuna') {
            c.innerHTML = `
                <label>Adzuna app_id: <input type="text" id="jd-cfg-app-id"></label>
                <label>Adzuna app_key: <input type="password" id="jd-cfg-app-key"></label>
                <label>Land: <input type="text" id="jd-cfg-country" value="de" maxlength="2"></label>
                <label>Stichwort: <input type="text" id="jd-cfg-what" placeholder="frontend"></label>
                <label>Ort: <input type="text" id="jd-cfg-where" placeholder="Berlin"></label>`;
        } else if (t === 'bundesagentur') {
            c.innerHTML = `
                <label>Stichwort (was): <input type="text" id="jd-cfg-was"></label>
                <label>PLZ (wo): <input type="text" id="jd-cfg-wo" maxlength="5"></label>
                <label>Umkreis (km): <input type="number" id="jd-cfg-umkreis" value="25"></label>`;
        } else if (t === 'arbeitnow') {
            c.innerHTML = `<label>Tags (komma-getrennt):
                <input type="text" id="jd-cfg-tags" placeholder="javascript, remote">
            </label>`;
        }
    }

    function buildConfig() {
        const t = $('jd-new-type').value;
        if (t === 'rss') return { url: $('jd-cfg-url').value };
        if (t === 'adzuna') return {
            app_id: $('jd-cfg-app-id').value,
            app_key: $('jd-cfg-app-key').value,
            country: $('jd-cfg-country').value,
            what: $('jd-cfg-what').value,
            where: $('jd-cfg-where').value,
            results_per_page: 50,
        };
        if (t === 'bundesagentur') return {
            was: $('jd-cfg-was').value,
            wo: $('jd-cfg-wo').value,
            umkreis: parseInt($('jd-cfg-umkreis').value, 10) || 25,
        };
        if (t === 'arbeitnow') return {
            tags: $('jd-cfg-tags').value.split(',').map(s => s.trim()).filter(Boolean),
        };
        return {};
    }

    async function createSource() {
        try {
            const r = await window.fetchAPI('/api/jobs/sources', {
                method: 'POST',
                body: JSON.stringify({
                    name: $('jd-new-name').value,
                    type: $('jd-new-type').value,
                    config: buildConfig(),
                    crawl_interval_min: parseInt($('jd-new-interval').value, 10) || 60,
                }),
            });
            if (r && r.source) {
                closeModal();
                refresh();
            }
        } catch (e) {
            alert('❌ Fehler: ' + e.message);
        }
    }

    function closeModal(event) {
        if (event && event.target.id !== 'jd-modal-wrap' && !event.target.classList.contains('modal-overlay')) {
            return;
        }
        const m = $('jd-modal-wrap');
        if (m) m.remove();
    }

    async function loadUserSettings() {
        const r = await window.fetchAPI('/api/profile');
        if (!r || !r.user) return;
        const u = r.user;
        $('jd-set-threshold').value = u.job_notification_threshold || 80;
        $('jd-set-threshold-display').textContent = u.job_notification_threshold || 80;
        $('jd-set-budget-tick').value = u.job_claude_budget_per_tick || 5;
        $('jd-set-budget-day').value = u.job_daily_budget_cents || 50;
        $('jd-set-enabled').checked = !!u.job_discovery_enabled;
        const langs = u.job_language_filter || ['de', 'en'];
        Array.from($('jd-set-langs').options).forEach(o => {
            o.selected = langs.includes(o.value);
        });
        $('jd-set-threshold').addEventListener('input', e => {
            $('jd-set-threshold-display').textContent = e.target.value;
        });
    }

    async function saveSettings() {
        const langs = Array.from($('jd-set-langs').selectedOptions).map(o => o.value);
        await window.fetchAPI('/api/profile', {
            method: 'PATCH',
            body: JSON.stringify({
                job_notification_threshold: parseInt($('jd-set-threshold').value, 10),
                job_claude_budget_per_tick: parseInt($('jd-set-budget-tick').value, 10),
                job_daily_budget_cents: parseInt($('jd-set-budget-day').value, 10),
                job_language_filter: langs,
                job_discovery_enabled: $('jd-set-enabled').checked,
            }),
        });
        alert('✅ Einstellungen gespeichert.');
    }

    window.JdSources = {
        show, refresh, testCrawl, toggle, del,
        showCreateModal, renderTypeFields, createSource, closeModal,
        saveSettings,
    };
})();
```

- [ ] **Step 3: Profile-API erweitern (Backend)**

Damit das Frontend die `job_*`-Felder lesen+schreiben kann, in `api/profile.py`:
- `GET /api/profile` muss die `job_*`-Felder im User-Response inkludieren
- `PATCH /api/profile` muss Updates dieser Felder akzeptieren

Suche `api/profile.py` und füge die neuen Felder zur User-Serialisierung und zum Update-Whitelist hinzu:
```python
JOB_DISCOVERY_FIELDS = (
    'job_discovery_enabled', 'job_notification_threshold',
    'job_claude_budget_per_tick', 'job_daily_budget_cents',
    'job_language_filter', 'job_region_filter',
)


def serialize_user(u):
    base = { ... existing ... }
    for f in JOB_DISCOVERY_FIELDS:
        base[f] = getattr(u, f)
    return base


# In PATCH-Handler:
for f in JOB_DISCOVERY_FIELDS:
    if f in data:
        if f in ('job_language_filter', 'job_region_filter'):
            setattr(user, f, data[f])  # via property → JSON
        else:
            setattr(user, f, data[f])
```

> ⚠️ Falls `api/profile.py` ein anderes Schema verwendet (z.B. via `settings_json`), die `job_*`-Felder dort konsistent integrieren.

- [ ] **Step 4: Tests + manuelles Browser-Test**

```bash
pytest tests/api/ -v
# Server starten, Settings öffnen, Tab "Job-Quellen", neue RSS-Quelle anlegen,
# Test-Crawl ausführen, Settings ändern + speichern.
```

- [ ] **Step 5: Commit**

```bash
git add index.html frontend/js/job-discovery-sources.js api/profile.py
git commit -m "feat: Settings-Tab Job-Quellen + Matching-Einstellungen"
```

---

## Task 5: Settings-Tab "KI-Konfiguration" — AI-Credentials

**Files:**
- Modify: `index.html`
- Modify: `frontend/js/job-discovery-credentials.js`

- [ ] **Step 1: Tab-Button + Container ergänzen**

Im `index.html` analog zu Task 4:
```html
<button class="btn btn-secondary btn-sm" onclick="JdCredentials.show()">🤖 KI-Konfiguration</button>
```

```html
<div id="jd-credentials-tab" class="card" style="display:none;">
    <h3>🤖 KI-Konfiguration (Bring Your Own Key)</h3>
    <p class="text-muted">
        Hinterlege eigene API-Keys oder Custom-Endpoints, damit Match-Kosten bei deinem
        Account anfallen statt am Server.
    </p>

    <div style="margin-bottom: 16px;">
        <button class="btn btn-primary btn-sm" onclick="JdCredentials.showCreateModal()">
            + Provider hinzufügen
        </button>
        <button class="btn btn-secondary btn-sm" onclick="JdCredentials.refresh()">🔄</button>
    </div>

    <table class="jd-credentials-table" id="jd-credentials-table">
        <thead><tr>
            <th>Provider</th><th>Modell</th><th>Endpoint/Key</th>
            <th>Budget</th><th>Status</th><th>Aktionen</th>
        </tr></thead>
        <tbody id="jd-credentials-tbody"></tbody>
    </table>

    <h3 style="margin-top: 24px;">📊 Verbrauch (letzte 30 Tage)</h3>
    <table class="jd-usage-table" id="jd-usage-tbody"></table>
</div>
```

- [ ] **Step 2: `frontend/js/job-discovery-credentials.js`**

```javascript
/**
 * Job-Discovery: AI-Credentials Settings (BYOK).
 */
(function () {
    'use strict';

    const PROVIDER_LABELS = {
        anthropic: 'Anthropic (offiziell)',
        custom_openai_compat: 'OpenAI-kompatibel (Ollama, vLLM, OpenRouter, Groq)',
        custom_anthropic_compat: 'Anthropic-kompatibel (Proxy)',
        custom_template: 'Custom Template (Profis)',
    };

    function $(id) { return document.getElementById(id); }
    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[ch]));
    }

    async function show() {
        document.querySelectorAll('#cv-upload-tab, #cv-compare-tab, #custom-ai-tab, #jd-sources-tab, #jd-credentials-tab')
            .forEach(el => el.style.display = 'none');
        $('jd-credentials-tab').style.display = '';
        await refresh();
        await loadUsage();
    }

    async function refresh() {
        const r = await window.fetchAPI('/api/ai-credentials');
        const tbody = $('jd-credentials-tbody');
        const creds = (r && r.credentials) || [];
        tbody.innerHTML = creds.length ? creds.map(c => `
            <tr>
                <td>${escapeHtml(PROVIDER_LABELS[c.provider] || c.provider)}</td>
                <td>${escapeHtml(c.default_model || '–')}</td>
                <td>${
                    c.provider === 'anthropic'
                        ? escapeHtml(c.key_preview || '••••••')
                        : escapeHtml(c.endpoint_url || '–')
                }</td>
                <td>${c.monthly_budget_cents != null ? c.monthly_budget_cents + '¢/Mon' : '–'}</td>
                <td>${c.is_active ? '✅ Aktiv' : '⏸️ Inaktiv'}</td>
                <td>
                    <button class="btn btn-sm" onclick="JdCredentials.test(${c.id})">🧪 Test</button>
                    <button class="btn btn-sm btn-danger" onclick="JdCredentials.del(${c.id})">🗑️</button>
                </td>
            </tr>
        `).join('') : '<tr><td colspan="6" class="text-muted">Noch keine Credentials hinterlegt.</td></tr>';
    }

    async function loadUsage() {
        try {
            const r = await window.fetchAPI('/api/ai-credentials/usage?days=30');
            const tbody = $('jd-usage-tbody');
            tbody.innerHTML = `
                <thead><tr><th>Quelle</th><th>Calls</th><th>Tokens In</th><th>Tokens Out</th><th>Kosten</th></tr></thead>
                <tbody>
                ${(r.by_key_owner || []).map(row => `
                    <tr>
                        <td>${row.key_owner === 'user' ? '🔑 Eigener Key' :
                              row.key_owner === 'custom_endpoint' ? '🏠 Custom Endpoint' :
                              '🌐 Server-Key'}</td>
                        <td>${row.calls}</td>
                        <td>${row.tokens_in.toLocaleString()}</td>
                        <td>${row.tokens_out.toLocaleString()}</td>
                        <td>${(row.cost_cents/100).toFixed(2)} €</td>
                    </tr>`).join('')}
                </tbody>`;
        } catch (e) {
            $('jd-usage-tbody').innerHTML = '<tr><td>Verbrauchsdaten nicht verfügbar.</td></tr>';
        }
    }

    function showCreateModal() {
        const html = `
        <div class="modal-overlay" onclick="JdCredentials.closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <h3>+ AI-Provider hinzufügen</h3>
                <label>Provider:
                    <select id="jd-cred-provider" onchange="JdCredentials.renderProviderFields()">
                        <option value="anthropic">Anthropic (offiziell)</option>
                        <option value="custom_openai_compat">OpenAI-kompatibel (Ollama, vLLM, OpenRouter)</option>
                        <option value="custom_anthropic_compat">Anthropic-kompatibel (Proxy)</option>
                        <option value="custom_template">Custom Template (Profis)</option>
                    </select>
                </label>
                <div id="jd-cred-fields"></div>
                <label>Standard-Modell:
                    <input type="text" id="jd-cred-model" placeholder="z.B. claude-haiku-4-5-20251001">
                </label>
                <label>Monatsbudget (optional, Cent):
                    <input type="number" id="jd-cred-budget" placeholder="z.B. 1000 = 10€">
                </label>
                <div class="modal-actions">
                    <button class="btn" onclick="JdCredentials.closeModal()">Abbrechen</button>
                    <button class="btn btn-primary" onclick="JdCredentials.create()">Anlegen + Testen</button>
                </div>
            </div>
        </div>`;
        const wrap = document.createElement('div');
        wrap.id = 'jd-cred-modal-wrap';
        wrap.innerHTML = html;
        document.body.appendChild(wrap);
        renderProviderFields();
    }

    function renderProviderFields() {
        const p = $('jd-cred-provider').value;
        const c = $('jd-cred-fields');
        if (p === 'anthropic') {
            c.innerHTML = `<label>API-Key:
                <input type="password" id="jd-cred-api-key" placeholder="sk-ant-api03-..." autocomplete="off">
            </label>`;
        } else if (p === 'custom_openai_compat' || p === 'custom_anthropic_compat') {
            c.innerHTML = `
                <label>Endpoint-URL:
                    <input type="url" id="jd-cred-endpoint"
                           placeholder="${p === 'custom_openai_compat'
                               ? 'http://localhost:11434/v1/chat/completions'
                               : 'https://my-proxy.example/v1/messages'}">
                </label>
                <label>API-Key (optional):
                    <input type="password" id="jd-cred-api-key" autocomplete="off">
                </label>
                <label>Auth-Header-Name (default: Authorization):
                    <input type="text" id="jd-cred-auth-name" placeholder="Authorization">
                </label>`;
        } else if (p === 'custom_template') {
            c.innerHTML = `
                <label>Endpoint-URL:
                    <input type="url" id="jd-cred-endpoint" placeholder="http://localhost:11434/api/generate">
                </label>
                <label>Request-Template (JSON, mit {{prompt}} Platzhaltern):
                    <textarea id="jd-cred-template" rows="5" style="font-family: monospace;"
                              placeholder='{"model": "llama3", "prompt": "{{prompt}}", "stream": false}'></textarea>
                </label>
                <label>Response-JSONPath (z.B. $.response):
                    <input type="text" id="jd-cred-resp-path" placeholder="$.response">
                </label>
                <label>API-Key (optional):
                    <input type="password" id="jd-cred-api-key" autocomplete="off">
                </label>`;
        }
    }

    async function create() {
        const provider = $('jd-cred-provider').value;
        const body = {
            provider,
            default_model: $('jd-cred-model').value || null,
            monthly_budget_cents: parseInt($('jd-cred-budget').value, 10) || null,
        };
        if (provider === 'anthropic') {
            body.api_key = $('jd-cred-api-key').value;
        } else {
            body.endpoint_url = $('jd-cred-endpoint').value;
            const k = $('jd-cred-api-key');
            if (k && k.value) body.api_key = k.value;
            const an = $('jd-cred-auth-name');
            if (an && an.value) body.auth_header_name = an.value;
            if (provider === 'custom_template') {
                try {
                    body.request_template = JSON.parse($('jd-cred-template').value);
                } catch (e) {
                    return alert('❌ Request-Template ist kein gültiges JSON.');
                }
                body.response_path = $('jd-cred-resp-path').value;
            }
        }

        try {
            const created = await window.fetchAPI('/api/ai-credentials', {
                method: 'POST', body: JSON.stringify(body),
            });
            if (created && created.id) {
                // Direkt testen
                const tested = await window.fetchAPI(`/api/ai-credentials/${created.id}/test`, {
                    method: 'POST',
                });
                if (tested && tested.ok) {
                    alert('✅ Provider hinzugefügt und getestet — aktiv.');
                } else {
                    alert(`⚠️ Provider angelegt, aber Test fehlgeschlagen: ${tested && tested.error}`);
                }
                closeModal();
                refresh();
            }
        } catch (e) {
            alert('❌ Fehler: ' + e.message);
        }
    }

    async function test(id) {
        const r = await window.fetchAPI(`/api/ai-credentials/${id}/test`, { method: 'POST' });
        if (r && r.ok) {
            alert('✅ Test erfolgreich — Provider aktiv.');
        } else {
            alert(`❌ Test fehlgeschlagen: ${r && r.error}`);
        }
        refresh();
    }

    async function del(id) {
        if (!confirm('Diesen Provider entfernen?')) return;
        await window.fetchAPI(`/api/ai-credentials/${id}`, { method: 'DELETE' });
        refresh();
    }

    function closeModal(event) {
        if (event && event.target.id !== 'jd-cred-modal-wrap' &&
            !event.target.classList.contains('modal-overlay')) {
            return;
        }
        const m = $('jd-cred-modal-wrap');
        if (m) m.remove();
    }

    window.JdCredentials = {
        show, refresh, showCreateModal, renderProviderFields,
        create, test, del, closeModal,
    };
})();
```

- [ ] **Step 3: CSS-Erweiterung**

Ergänze `frontend/job-discovery.css`:
```css
.jd-sources-table, .jd-credentials-table, .jd-usage-table {
    width: 100%; border-collapse: collapse;
}
.jd-sources-table th, .jd-credentials-table th, .jd-usage-table th {
    text-align: left; padding: 8px; border-bottom: 1px solid var(--border);
    font-size: 0.85em; color: var(--text-muted);
}
.jd-sources-table td, .jd-credentials-table td, .jd-usage-table td {
    padding: 8px; border-bottom: 1px solid var(--border);
}
.jd-settings-form {
    display: flex; flex-direction: column; gap: 12px; margin-top: 12px;
}
.jd-settings-form label {
    display: flex; align-items: center; gap: 8px;
}
.modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal {
    background: var(--bg-card); border-radius: 8px;
    padding: 24px; max-width: 500px; width: 90%;
    max-height: 80vh; overflow-y: auto;
}
.modal label {
    display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px;
}
.modal-actions {
    display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px;
}
```

- [ ] **Step 4: Manuelle QA**

1. Settings öffnen → Tab "🤖 KI-Konfiguration"
2. "+ Provider hinzufügen" → Anthropic, Key eintragen, anlegen
3. Test sollte automatisch grün durchlaufen
4. Verbrauch-Tabelle sollte erscheinen (anfangs leer)
5. Test mit Ollama (`http://localhost:11434/v1/chat/completions`) als custom_openai_compat
6. Job-Vorschläge-Tab → Pipeline manuell triggern (Backend) → Match erscheint, Verbrauch geht hoch

- [ ] **Step 5: Commit**

```bash
git add index.html frontend/js/job-discovery-credentials.js frontend/job-discovery.css
git commit -m "feat: Settings-Tab KI-Konfiguration (BYOK + Verbrauchs-Statistik)"
```

---

## Task 6: Push-Notification Integration

**Files:**
- Modify: `frontend/js/job-discovery.js`
- Modify: bestehender Notification-Service (z.B. `service-worker.js`) falls vorhanden

- [ ] **Step 1: Bestehende Notification-Infrastruktur prüfen**

```bash
grep -rn "Notification\|service-worker\|registerServiceWorker" \
    index.html frontend/ services/ 2>/dev/null | head -20
```

- [ ] **Step 2: Browser-Notification fallback im Frontend**

In `frontend/js/job-discovery.js` `updateBadgeCount()` erweitern:
```javascript
let lastSeenMatchIds = new Set(JSON.parse(localStorage.getItem('jd-seen-ids') || '[]'));

async function updateBadgeCount() {
    try {
        const r = await window.fetchAPI('/api/jobs/matches?status=new&min_score=80&limit=20');
        const badge = $('nav-jobs-badge');
        if (badge && r) {
            badge.textContent = r.total;
            badge.style.display = r.total > 0 ? '' : 'none';

            // Browser-Notification für neue Top-Matches
            if (r.matches && Notification && Notification.permission === 'granted') {
                for (const m of r.matches) {
                    if (!lastSeenMatchIds.has(m.id)) {
                        new Notification('🔍 Neuer Job-Vorschlag', {
                            body: `${m.match_score.toFixed(0)}: ${m.raw_job.title} @ ${m.raw_job.company || '?'}`,
                            tag: `job-match-${m.id}`,
                        });
                        lastSeenMatchIds.add(m.id);
                    }
                }
                localStorage.setItem('jd-seen-ids',
                    JSON.stringify(Array.from(lastSeenMatchIds).slice(-100)));
            }
        }
    } catch (e) {
        // silent
    }
}
```

- [ ] **Step 3: Permission-Request beim ersten Öffnen der Job-View**

```javascript
function onShow() {
    if (!initialized) {
        bindFilterEvents();
        if (Notification && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        initialized = true;
    }
    fetchSources().then(fetchMatches);
    updateBadgeCount();
}
```

- [ ] **Step 4: Test in Browser**

- View öffnen → Permission-Dialog erscheint
- Allow drücken
- Pipeline triggern → Notification sollte kommen, wenn Match-Score ≥ 80

- [ ] **Step 5: Commit**

```bash
git add frontend/js/job-discovery.js
git commit -m "feat: Browser-Notifications für neue Top-Matches"
```

---

## Task 7: Empty-State + Onboarding-Hinweise

**Files:**
- Modify: `frontend/js/job-discovery.js`

- [ ] **Step 1: Onboarding-State erkennen + freundlich anzeigen**

Im `fetchMatches` / `render()` ergänzen:
```javascript
async function fetchMatches() {
    // ... existing code ...
    // Wenn 0 Matches und User noch nicht onboarded:
    if (state.total === 0 && state.filters.statuses.includes('new')) {
        await renderOnboardingIfNeeded();
    }
}

async function renderOnboardingIfNeeded() {
    const container = $('jd-matches-list');
    const profileR = await window.fetchAPI('/api/profile');
    const sourcesR = await window.fetchAPI('/api/jobs/sources');
    const credsR = await window.fetchAPI('/api/ai-credentials');

    const enabled = profileR.user.job_discovery_enabled;
    const hasOwnCreds = (credsR.credentials || []).some(c => c.is_active);
    const enabledSources = (sourcesR.sources || []).filter(s => s.enabled).length;
    const hasCv = !!profileR.user.cv_data_json;

    const checks = [
        { ok: enabled, label: 'Job-Discovery aktiviert',
          fix: 'Settings → Job-Quellen → "Job-Discovery aktiviert" anhaken' },
        { ok: hasCv, label: 'Lebenslauf hinterlegt',
          fix: 'CV-Upload nutzen' },
        { ok: enabledSources > 0, label: 'Mind. 1 aktive Quelle',
          fix: 'Settings → Job-Quellen → System-Quellen sind voraktiviert' },
        { ok: hasOwnCreds, label: 'AI-Credentials hinterlegt (BYOK empfohlen)',
          fix: 'Settings → KI-Konfiguration → Provider hinzufügen' },
    ];

    container.innerHTML = `
        <div class="jd-onboarding card">
            <h3>🚀 So startest du mit Job-Vorschlägen</h3>
            <ul class="jd-onboarding-checklist">
                ${checks.map(c => `
                    <li>${c.ok ? '✅' : '⬜'} <strong>${c.label}</strong>
                        ${c.ok ? '' : `<br><small class="text-muted">→ ${c.fix}</small>`}
                    </li>
                `).join('')}
            </ul>
            ${checks.every(c => c.ok)
                ? '<p>🎉 Alles bereit! Warte auf den nächsten Pipeline-Lauf (max ~90 Min) oder triggere manuell.</p>'
                : '<p>Sobald alle Punkte erfüllt sind, erscheinen hier deine Vorschläge.</p>'
            }
        </div>`;
}
```

- [ ] **Step 2: CSS**

```css
.jd-onboarding-checklist { list-style: none; padding: 0; }
.jd-onboarding-checklist li { padding: 8px 0; }
```

- [ ] **Step 3: Test im Browser**

Mit einem frischen User-Account → Onboarding-Checkliste sollte erscheinen mit nicht-erfüllten Punkten.

- [ ] **Step 4: Commit**

```bash
git add frontend/js/job-discovery.js frontend/job-discovery.css
git commit -m "feat: Onboarding-Checkliste im Empty-State"
```

---

## Task 8: Mobile-Responsive-Anpassungen + Accessibility

**Files:**
- Modify: `frontend/job-discovery.css`

- [ ] **Step 1: Mobile-spezifische Styles**

Erweitere `frontend/job-discovery.css`:
```css
@media (max-width: 480px) {
    .jd-card-header { flex-direction: column; }
    .jd-score-badge { align-self: flex-start; }
    .jd-card-actions .btn { font-size: 0.85em; }
    .jd-sources-table thead, .jd-credentials-table thead { display: none; }
    .jd-sources-table tr, .jd-credentials-table tr { display: block; margin-bottom: 12px;
                                                      border: 1px solid var(--border); }
    .jd-sources-table td, .jd-credentials-table td { display: block; padding: 4px 8px; }
}

/* Focus-Styles für Tastatur-Navigation */
.jd-card:focus-within { outline: 2px solid var(--primary); }
.btn:focus-visible { outline: 2px solid var(--primary-light); outline-offset: 2px; }
```

- [ ] **Step 2: ARIA-Labels in Hauptmodul**

In `frontend/js/job-discovery.js` bei `renderCard`:
```javascript
return `
<article class="jd-card" data-id="${m.id}" aria-label="Job-Vorschlag ${escapeHtml(raw.title)}">
    ...
</article>`;
```

- [ ] **Step 3: Browser-Test auf Mobile-Viewport**

Chrome DevTools → Device-Toolbar → iPhone-Größe → Job-Vorschläge sind sauber readable, Aktions-Buttons gestapelt.

- [ ] **Step 4: Commit**

```bash
git add frontend/job-discovery.css frontend/js/job-discovery.js
git commit -m "style: Mobile-Responsive + ARIA-Labels für Job-Discovery"
```

---

## Task 9: End-to-End-Test (manuell)

- [ ] **Step 1: Komplettes E2E-Szenario**

Frischer User-Account, alle Phasen:

1. **Account anlegen + einloggen.**
2. **CV hochladen** (per existierendem CV-Upload).
3. **Settings → KI-Konfiguration:** Anthropic-Key oder Ollama-Endpoint hinterlegen, "Test" → grün.
4. **Settings → Job-Quellen:** "Job-Discovery aktiviert" anhaken, Save. System-Quellen (Bundesagentur) sind voraktiviert.
5. **Pipeline manuell triggern** (Terminal):
   ```bash
   for stage in crawl-source prefilter claude-match notify; do
     curl -X POST http://localhost:5000/api/jobs/$stage \
       -H "X-Cron-Token: $JOB_CRON_TOKEN"
   done
   ```
6. **Tab "Job-Vorschläge"** → Karten erscheinen mit Match-Score, Begründung, fehlende Skills.
7. **"Übernehmen"** auf einem Match → erstellt Bewerbung, sichtbar in Bewerbungen-Liste mit Match-Notiz.
8. **"Verwerfen"** auf einem Match → verschwindet.
9. **Filter:** Score-Slider auf 80, nur Top-Matches sichtbar.
10. **Browser-Notification:** sichtbar wenn neuer Match mit Score ≥ 80.
11. **Verbrauchs-Statistik:** zeigt korrekten `key_owner` (user/custom_endpoint).

- [ ] **Step 2: Bug-Fixing falls nötig + Commit**

Falls Issues in QA gefunden, separate Fix-Commits. Sonst:
```bash
git commit --allow-empty -m "test: E2E-Smoke-Test Phase C — alles grün"
```

---

## Task 10: Doku-Update + README

**Files:**
- Modify: `docs/FEATURES/JOB_DISCOVERY.md`
- Modify: `README.md`

- [ ] **Step 1: User-facing Doku ergänzen**

In `docs/FEATURES/JOB_DISCOVERY.md`:
```markdown
## Frontend-Nutzung (Phase C)

### Erste Schritte

1. **Lebenslauf hinterlegen** (CV-Upload).
2. **KI-Konfiguration → Provider hinzufügen:**
   - Anthropic (eigener Key) → empfohlen für beste Qualität
   - Ollama lokal → kostenlos, eigene Hardware
   - OpenRouter / Groq → mehrere Modelle, günstig
3. **Job-Quellen → Job-Discovery aktivieren** und ggf. eigene RSS-Feeds hinzufügen.
4. **Tab "🔍 Job-Vorschläge"** prüfen — nach erstem Pipeline-Lauf erscheinen Karten.

### Aktionen pro Karte

- **🔗 Original ansehen** — öffnet die Stelle beim Anbieter
- **📥 Übernehmen** — legt eine Bewerbung mit Status "geplant" an
- **🗑️ Verwerfen** — markiert als irrelevant, taucht nicht wieder auf
- **👁 Verbergen** — markiert als gesehen, blendet aus ohne Negativ-Signal

### Filter

- **Score-Slider:** zeigt nur Matches ab Mindest-Score
- **Status:** Neu / Gesehen / Übernommen / Verworfen
- **Quelle:** Filterung pro Job-Portal
- **Suche:** Volltext-Suche in Titel und Firma
```

- [ ] **Step 2: README-Update**

In `README.md` "Kernfeatures" ergänzen (falls noch nicht in Phase A geschehen):
```markdown
- 🔍 **Job-Discovery** - Automatische Stellensuche aus konfigurierbaren Quellen mit Claude-basiertem Match-Score gegen deinen CV. BYOK-Support für Anthropic / Ollama / OpenRouter.
```

- [ ] **Step 3: Commit**

```bash
git add docs/FEATURES/JOB_DISCOVERY.md README.md
git commit -m "docs: Phase C Frontend-Nutzungs-Doku"
```

---

## Phase C — Definition of Done

- ✅ Tab "Job-Vorschläge" mit Karten-Liste, Filter-Bar, Pagination
- ✅ Settings-Tab "Job-Quellen" mit CRUD + Test-Crawl
- ✅ Settings-Tab "KI-Konfiguration" mit Provider-CRUD + Test + Verbrauchs-Statistik
- ✅ Browser-Notifications für Top-Matches
- ✅ Onboarding-Checkliste im Empty-State
- ✅ Mobile-Responsive + ARIA-Labels
- ✅ E2E-Test: User-Flow von Anlegen bis Bewerbung-Übernahme funktioniert
- ✅ Doku aktualisiert

Mit Phase C ist das Job-Discovery-Feature vollständig und user-facing. User können
ohne Terminal/Postman alles konfigurieren und nutzen.

---

## Out of Scope für diese Phase (Phase 2 Roadmap)

- **Auto-Apply-Drafts:** Claude generiert Anschreiben-Drafts für Top-Matches
- **Match-Erklärung-Detail-View:** Modal mit ausführlicher Begründung + CV-Diff
- **Bulk-Aktionen:** mehrere Matches gleichzeitig verwerfen
- **Export:** Match-Liste als CSV/PDF
- **Advanced Search-Sync:** Suchhistorie zwischen Geräten

Siehe Spec-Sektion 11.
