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

    const now = Number(nowMs || Date.now());
    const elapsedMs = Math.max(0, now - Number(entry.startedAtMs || now));
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
