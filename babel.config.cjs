// SPDX-License-Identifier: AGPL-3.0-or-later
// © 2026 Harald Weiss
/**
 * Babel configuration for the Jest test harness.
 *
 * The `lib/__tests__` suites are TypeScript; without a TypeScript preset
 * Babel leaves the type annotations and ES module syntax untouched and Jest
 * aborts those six suites with a parser error (see CHANGELOG 2026-10-27).
 * The application itself is served as plain browser JavaScript — this config
 * only affects the test transform.
 */
module.exports = {
  presets: [
    ['@babel/preset-env', { targets: { node: 'current' } }],
    '@babel/preset-typescript',
  ],
};
