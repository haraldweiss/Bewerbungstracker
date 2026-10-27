// SPDX-License-Identifier: AGPL-3.0-or-later
// © 2026 Harald Weiss
/**
 * Jest configuration for the legacy Claude-era library suites.
 *
 * `lib/` (cost calculation, model routing, batch processing, usage tracking,
 * task analysis) belongs to the retired Anthropic integration. It is not
 * imported by the application — only by `examples/` — and its assertions have
 * drifted (see CHANGELOG 2026-10-27).
 *
 * The suites stay runnable and are excluded from the default `npm test` gate
 * instead of being deleted: `npm run test:legacy` runs them, so the drift stays
 * visible without blocking dependency updates.
 */
const base = require('./package.json').jest;

module.exports = {
  ...base,
  testPathIgnorePatterns: ['/node_modules/'],
  testMatch: ['<rootDir>/lib/__tests__/**/*.test.ts'],
};
