// SPDX-License-Identifier: AGPL-3.0-or-later
// © 2026 Harald Weiss
/**
 * Jest setup shared by every suite.
 *
 * The legacy `lib/__tests__` suites import the Anthropic SDK, which needs
 * `TextEncoder`/`TextDecoder` at import time. The jsdom environment (required
 * by the frontend suites) does not provide them, so polyfill from Node's
 * `util` module instead of switching environments.
 */
const { TextDecoder, TextEncoder } = require('node:util');

if (typeof global.TextEncoder === 'undefined') {
  global.TextEncoder = TextEncoder;
}
if (typeof global.TextDecoder === 'undefined') {
  global.TextDecoder = TextDecoder;
}
