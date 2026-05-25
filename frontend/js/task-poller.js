// SPDX-License-Identifier: AGPL-3.0-or-later
// © 2026 Harald Weiss
/**
 * Task Polling Helper
 *
 * Polls GET /api/tasks/<taskId> until the task reaches a terminal state
 * (done / failed / cancelled). Uses Auth.fetch() which auto-adds the
 * Authorization header and returns parsed JSON (throws on non-2xx).
 *
 * Usage:
 *   const result = await pollTask(task_id, task => {
 *       // optional progress callback — receives the raw task object
 *   });
 *   // result has the same shape as the old synchronous response
 */

/**
 * Poll task status until done / failed / cancelled.
 *
 * @param {string} taskId      — UUID returned by the 202 enqueue response
 * @param {(task: object) => void} [onProgress]  — called after each poll tick
 * @returns {Promise<object>}  — task.result payload on success
 * @throws {Error}             — on failure, cancellation, or timeout-induced error
 */
async function pollTask(taskId, onProgress) {
    const startMs = Date.now();
    let interval = 2000;

    while (true) {
        // Auth.fetch returns parsed JSON and throws on non-2xx
        const task = await Auth.fetch(`/tasks/${taskId}`);

        if (onProgress) onProgress(task);

        if (task.status === 'done')      return task.result;
        if (task.status === 'failed')    throw new Error(task.error || 'Task fehlgeschlagen');
        if (task.status === 'cancelled') throw new Error('Task abgebrochen');

        // Back-off after 30 s: poll every 5 s instead of every 2 s
        if (Date.now() - startMs > 30_000) interval = 5000;

        await new Promise(r => setTimeout(r, interval));
    }
}
