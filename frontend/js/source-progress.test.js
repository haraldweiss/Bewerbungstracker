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
            sourceLabel: '',
            stateLabel: 'Wartet',
            progress: 0,
            tone: 'pending',
            detail: 'Position 2 in Warteschlange',
        });
    });

    test('running entries calculate elapsed and eta from progress', () => {
        const state = createSourceOperationState(() => 10_000);
        state.start(12, 'import', 'task-1', 'Indeed');
        state.updateFromTask(12, { status: 'running', progress: 25 });

        expect(buildSourceProgressView(state.get(12), 40_000)).toEqual({
            visible: true,
            operationLabel: 'Import',
            sourceLabel: 'Indeed',
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
            sourceLabel: '',
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
            sourceLabel: '',
            stateLabel: 'Fehler',
            progress: 100,
            tone: 'error',
            detail: 'IMAP timeout',
        });
    });
});
