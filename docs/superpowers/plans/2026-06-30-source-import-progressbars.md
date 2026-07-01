# Source Import Progressbars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-source progressbars for single email import, "Alle importieren", and pattern learning in Bewerbungstracker.

**Architecture:** Keep long-running work in the existing task queue. Add a small frontend helper module for source-operation state, elapsed time, and ETA formatting, then wire `index.html` to render and update one compact progress area per source row.

**Tech Stack:** Vanilla JavaScript, Jest/jsdom, Flask task polling via existing `/api/tasks/<id>`, single-page `index.html`.

## Global Constraints

- Default branch is `master`, not `main`.
- Business logic stays in `services/`; `api/` remains thin.
- No raw email body, CV content, credentials, or sensitive job text in logs or debug UI.
- No backend schema change for this iteration.
- Imports remain sequential; do not parallelize email imports.
- Use existing async task progress from `GET /api/tasks/<id>`.

---

### Task 1: Progress State Helper

**Files:**
- Create: `frontend/js/source-progress.js`
- Test: `frontend/js/source-progress.test.js`

**Interfaces:**
- Produces: `createSourceOperationState(nowMs?: () => number)` returning an object with `setWaiting`, `start`, `updateFromTask`, `complete`, `fail`, `clear`, `get`, and `snapshot`.
- Produces: `formatDuration(ms: number): string`.
- Produces: `buildSourceProgressView(entry: object | undefined, nowMs?: number): object | null`.

- [ ] **Step 1: Write failing helper tests**

Create `frontend/js/source-progress.test.js`:

```javascript
const {
    createSourceOperationState,
    formatDuration,
    buildSourceProgressView,
} = require('./source-progress.js');

describe('source progress helper', () => {
    test('formatDuration renders seconds and minutes compactly', () => {
        expect(formatDuration(0)).toBe('0s');
        expect(formatDuration(18_400)).toBe('18s');
        expect(formatDuration(75_000)).toBe('1m 15s');
    });

    test('waiting entries expose queue position without eta', () => {
        const state = createSourceOperationState(() => 1_000);
        state.setWaiting(12, 'import', 2);

        expect(buildSourceProgressView(state.get(12), 4_000)).toEqual({
            visible: true,
            operationLabel: 'Import',
            stateLabel: 'Wartet',
            progress: 0,
            tone: 'pending',
            detail: 'Position 2 in Warteschlange',
        });
    });

    test('running entries calculate elapsed and eta from progress', () => {
        const state = createSourceOperationState(() => 10_000);
        state.start(12, 'import', 'task-1');
        state.updateFromTask(12, { status: 'running', progress: 25 });

        expect(buildSourceProgressView(state.get(12), 40_000)).toEqual({
            visible: true,
            operationLabel: 'Import',
            stateLabel: 'Laeuft',
            progress: 25,
            tone: 'active',
            detail: 'seit 30s · noch ca. 1m 30s',
        });
    });

    test('complete entries expose final summary at full progress', () => {
        const state = createSourceOperationState(() => 10_000);
        state.start(12, 'learn', 'task-2');
        state.complete(12, 'Fertig: 72% Hit-Rate');

        expect(buildSourceProgressView(state.get(12), 12_000)).toEqual({
            visible: true,
            operationLabel: 'Lernen',
            stateLabel: 'Fertig',
            progress: 100,
            tone: 'success',
            detail: 'Fertig: 72% Hit-Rate',
        });
    });

    test('failed entries remain visible with concise error', () => {
        const state = createSourceOperationState(() => 10_000);
        state.start(12, 'import', 'task-3');
        state.fail(12, 'IMAP timeout');

        expect(buildSourceProgressView(state.get(12), 12_000)).toEqual({
            visible: true,
            operationLabel: 'Import',
            stateLabel: 'Fehler',
            progress: 100,
            tone: 'error',
            detail: 'IMAP timeout',
        });
    });
});
```

- [ ] **Step 2: Run RED**

Run: `npm test -- frontend/js/source-progress.test.js --runInBand`

Expected: FAIL because `frontend/js/source-progress.js` does not exist.

- [ ] **Step 3: Implement helper**

Create `frontend/js/source-progress.js` with CommonJS export and browser global:

```javascript
// SPDX-License-Identifier: AGPL-3.0-or-later
// © 2026 Harald Weiss

function operationLabel(operation) {
    return operation === 'learn' ? 'Lernen' : 'Import';
}

function formatDuration(ms) {
    const totalSeconds = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (minutes <= 0) return `${seconds}s`;
    return `${minutes}m ${seconds}s`;
}

function normalizeProgress(value) {
    const pct = Number(value);
    if (!Number.isFinite(pct)) return 0;
    return Math.max(0, Math.min(100, Math.round(pct)));
}

function createSourceOperationState(nowMs) {
    const now = typeof nowMs === 'function' ? nowMs : () => Date.now();
    const entries = new Map();

    return {
        setWaiting(sourceId, operation, queuePosition) {
            entries.set(Number(sourceId), {
                operation,
                status: 'waiting',
                progress: 0,
                queuePosition: Number(queuePosition) || 1,
                startedAtMs: now(),
            });
        },
        start(sourceId, operation, taskId) {
            entries.set(Number(sourceId), {
                operation,
                taskId,
                status: 'running',
                progress: 0,
                startedAtMs: now(),
            });
        },
        updateFromTask(sourceId, task) {
            const key = Number(sourceId);
            const entry = entries.get(key);
            if (!entry) return;
            entry.progress = normalizeProgress(task && task.progress);
            entry.status = task && task.status === 'queued' ? 'queued' : 'running';
            entries.set(key, entry);
        },
        complete(sourceId, summary) {
            const key = Number(sourceId);
            const entry = entries.get(key);
            if (!entry) return;
            entry.status = 'done';
            entry.progress = 100;
            entry.summary = summary || 'Fertig';
            entries.set(key, entry);
        },
        fail(sourceId, message) {
            const key = Number(sourceId);
            const entry = entries.get(key) || {
                operation: 'import',
                startedAtMs: now(),
            };
            entry.status = 'failed';
            entry.progress = 100;
            entry.error = message || 'Fehler';
            entries.set(key, entry);
        },
        clear(sourceId) {
            entries.delete(Number(sourceId));
        },
        get(sourceId) {
            return entries.get(Number(sourceId));
        },
        snapshot() {
            return Array.from(entries.entries()).reduce((acc, pair) => {
                acc[pair[0]] = pair[1];
                return acc;
            }, {});
        },
    };
}

function buildSourceProgressView(entry, nowMs) {
    if (!entry) return null;
    const status = entry.status || 'running';
    const progress = status === 'done' || status === 'failed'
        ? 100
        : normalizeProgress(entry.progress);
    const base = {
        visible: true,
        operationLabel: operationLabel(entry.operation),
        stateLabel: 'Laeuft',
        progress,
        tone: 'active',
        detail: '',
    };

    if (status === 'waiting') {
        base.stateLabel = 'Wartet';
        base.tone = 'pending';
        base.detail = `Position ${entry.queuePosition || 1} in Warteschlange`;
        return base;
    }
    if (status === 'queued') {
        base.stateLabel = 'Startet';
        base.tone = 'pending';
    }
    if (status === 'done') {
        return {
            ...base,
            stateLabel: 'Fertig',
            tone: 'success',
            detail: entry.summary || 'Fertig',
        };
    }
    if (status === 'failed') {
        return {
            ...base,
            stateLabel: 'Fehler',
            tone: 'error',
            detail: entry.error || 'Fehler',
        };
    }

    const elapsedMs = Math.max(0, Number(nowMs || Date.now()) - Number(entry.startedAtMs || nowMs || Date.now()));
    const parts = [`seit ${formatDuration(elapsedMs)}`];
    if (progress > 5 && progress < 100 && elapsedMs >= 1000) {
        const remainingMs = elapsedMs * ((100 - progress) / progress);
        parts.push(`noch ca. ${formatDuration(remainingMs)}`);
    }
    base.detail = parts.join(' · ');
    return base;
}

const api = {
    createSourceOperationState,
    formatDuration,
    buildSourceProgressView,
};

if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
}
if (typeof window !== 'undefined') {
    window.SourceProgress = api;
}
```

- [ ] **Step 4: Run GREEN**

Run: `npm test -- frontend/js/source-progress.test.js --runInBand`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/source-progress.js frontend/js/source-progress.test.js
git commit -m "test: add source progress helper"
```

### Task 2: Wire Progressbars Into Source Rows

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `window.SourceProgress.createSourceOperationState()`.
- Consumes: `window.SourceProgress.buildSourceProgressView(entry, Date.now())`.

- [ ] **Step 1: Load helper script**

Add after `task-poller.js`:

```html
<script src="/frontend/js/source-progress.js"></script>
```

- [ ] **Step 2: Add module state and render helpers**

Inside the `JdSourcesUI` module near `_sourcesCache`, add:

```javascript
const _sourceProgress = window.SourceProgress
    ? window.SourceProgress.createSourceOperationState()
    : null;

function _sourceProgressHtml(sourceId) {
    if (!_sourceProgress || !window.SourceProgress) return '';
    const view = window.SourceProgress.buildSourceProgressView(
        _sourceProgress.get(sourceId),
        Date.now()
    );
    if (!view || !view.visible) return '';
    const tone = view.tone || 'active';
    return `<div class="jd-source-progress jd-source-progress-${tone}" data-source-progress="${sourceId}">
        <div class="jd-source-progress-head">
            <span>${escapeHtml(view.operationLabel)} · ${escapeHtml(view.stateLabel)}</span>
            <span>${view.progress}%</span>
        </div>
        <div class="jd-source-progress-track"><div class="jd-source-progress-fill" style="width:${view.progress}%"></div></div>
        <div class="jd-source-progress-detail">${escapeHtml(view.detail || '')}</div>
    </div>`;
}

function _refreshSourceProgress(sourceId) {
    const existing = document.querySelector(`[data-source-progress-slot="${sourceId}"]`);
    if (!existing) {
        refresh();
        return;
    }
    existing.innerHTML = _sourceProgressHtml(sourceId);
}
```

- [ ] **Step 3: Render progress slot per source row**

In the first `<td>` of the source row, add:

```html
<div data-source-progress-slot="${s.id}">${_sourceProgressHtml(s.id)}</div>
```

Place it after the `<small>` metadata.

- [ ] **Step 4: Add compact CSS**

Add CSS in the page stylesheet:

```css
.jd-source-progress {
    margin-top: 0.45rem;
    max-width: 24rem;
    font-size: 0.78rem;
}
.jd-source-progress-head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    color: var(--text-muted);
}
.jd-source-progress-track {
    height: 0.45rem;
    margin: 0.2rem 0;
    overflow: hidden;
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.22);
}
.jd-source-progress-fill {
    height: 100%;
    border-radius: inherit;
    background: var(--primary);
    transition: width 180ms ease;
}
.jd-source-progress-pending .jd-source-progress-fill { background: var(--warning, #f59e0b); }
.jd-source-progress-success .jd-source-progress-fill { background: var(--success, #10b981); }
.jd-source-progress-error .jd-source-progress-fill { background: var(--danger, #ef4444); }
.jd-source-progress-error .jd-source-progress-detail { color: var(--danger, #ef4444); }
.jd-source-progress-detail {
    color: var(--text-muted);
    overflow-wrap: anywhere;
}
```

- [ ] **Step 5: Manual syntax check**

Run: `npm test -- frontend/js/source-progress.test.js --runInBand`

Expected: PASS. The inline `index.html` JavaScript cannot be parsed directly by Jest, so inspect changed snippets and verify in browser if a dev server is available.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat: render source operation progressbars"
```

### Task 3: Update Import And Learning Flows

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `_sourceProgress.setWaiting(sourceId, operation, queuePosition)`.
- Consumes: `_sourceProgress.start(sourceId, operation, taskId)`.
- Consumes: `_sourceProgress.updateFromTask(sourceId, task)`.
- Consumes: `_sourceProgress.complete(sourceId, summary)`.
- Consumes: `_sourceProgress.fail(sourceId, message)`.
- Consumes: `_refreshSourceProgress(sourceId)`.

- [ ] **Step 1: Update queue waiting state**

In `importFromEmail(id)`, when a source is queued, call:

```javascript
if (_sourceProgress) {
    _sourceProgress.setWaiting(id, 'import', _importQueue.indexOf(id) + 1);
    _refreshSourceProgress(id);
}
```

- [ ] **Step 2: Update `_runImport(id)`**

After enqueue returns `task_id`, start progress:

```javascript
if (_sourceProgress) {
    _sourceProgress.start(id, 'import', enqRes.task_id);
    _refreshSourceProgress(id);
}
```

Inside `pollTask` progress callback:

```javascript
if (_sourceProgress) {
    _sourceProgress.updateFromTask(id, task);
    _refreshSourceProgress(id);
}
```

After success result is known:

```javascript
if (_sourceProgress) {
    _sourceProgress.complete(
        id,
        `Fertig: ${total} Mails geprueft, ${imported} neu${dup ? `, ${dup} Duplikate` : ''}`
    );
    _refreshSourceProgress(id);
}
```

In `catch`, before alert:

```javascript
if (_sourceProgress) {
    _sourceProgress.fail(id, msg);
    _refreshSourceProgress(id);
}
```

- [ ] **Step 3: Update `importAll()`**

Before calling `forEach`, mark every email source with waiting state:

```javascript
emailSources.forEach((source, index) => {
    if (_sourceProgress) {
        _sourceProgress.setWaiting(source.id, 'import', index + 1);
        _refreshSourceProgress(source.id);
    }
});
```

Then keep existing sequential `emailSources.forEach(s => importFromEmail(s.id));`.

- [ ] **Step 4: Update `trainPattern(sourceId)`**

After enqueue returns `task_id`:

```javascript
if (_sourceProgress) {
    _sourceProgress.start(sourceId, 'learn', enqRes.task_id);
    _refreshSourceProgress(sourceId);
}
```

Inside task polling:

```javascript
if (_sourceProgress) {
    _sourceProgress.updateFromTask(sourceId, task);
    _refreshSourceProgress(sourceId);
}
```

On success:

```javascript
if (_sourceProgress) {
    _sourceProgress.complete(sourceId, 'Fertig: ' + pct + '% Hit-Rate');
    _refreshSourceProgress(sourceId);
}
```

On failure/error:

```javascript
if (_sourceProgress) {
    _sourceProgress.fail(sourceId, errorMessage);
    _refreshSourceProgress(sourceId);
}
```

- [ ] **Step 5: Run focused JS tests**

Run: `npm test -- frontend/js/source-progress.test.js --runInBand`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat: update source import and learning progress"
```

### Task 4: Verification And Documentation Touches

**Files:**
- Modify: `CHANGELOG.md` only if a handoff note is needed.
- Modify: `README.md` only if setup, env vars, ports, deploy steps, or caveats change. Expected: no README change.

**Interfaces:**
- Consumes: all previous task changes.

- [ ] **Step 1: Run JS test target**

Run: `npm test -- frontend/js/source-progress.test.js --runInBand`

Expected: PASS.

- [ ] **Step 2: Run relevant API/task regression tests**

Run: `venv/bin/pytest tests/api/test_tasks_api.py tests/api/test_indeed_email_import.py tests/api/test_pattern_learner_api.py -q`

Expected: PASS. If environment lacks dependencies, report the exact blocker.

- [ ] **Step 3: Inspect final diff**

Run: `git diff --stat HEAD~3..HEAD`

Expected: only spec/plan, frontend helper/tests, and `index.html` changes.

- [ ] **Step 4: Final commit if needed**

If verification or documentation changes create files:

```bash
git add CHANGELOG.md README.md
git commit -m "docs: record source progressbar verification"
```

Skip this commit if no docs changed.

## Plan Self-Review

Spec coverage:
- Per-row progress UI: Task 2.
- Single import and "Alle importieren": Task 3.
- Pattern learning: Task 3.
- ETA and elapsed formatting: Task 1.
- Error handling: Task 1 and Task 3.
- No backend schema change: Global Constraints and Task 4.

Placeholder scan:
- No `TBD`, `TODO`, or unspecified code steps remain.

Type consistency:
- `sourceId`, `operation`, `taskId`, `progress`, and helper method names match across Tasks 1-3.
