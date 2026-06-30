// SPDX-License-Identifier: AGPL-3.0-or-later
// © 2026 Harald Weiss

const fs = require('fs');
const path = require('path');

describe('application PDF export assets', () => {
  const root = path.resolve(__dirname, '..', '..');
  const indexHtml = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

  test('loads jsPDF and AutoTable from local vendor assets', () => {
    expect(indexHtml).toContain('src="/components/vendor/jspdf.umd.min.js"');
    expect(indexHtml).toContain('src="/components/vendor/jspdf.plugin.autotable.min.js"');
    expect(indexHtml).not.toContain('cdnjs.cloudflare.com/ajax/libs/jspdf/');
    expect(indexHtml).not.toContain('cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/');
  });

  test('does not use unsupported jsPDF underline font style', () => {
    expect(indexHtml).not.toContain("doc.setFont(undefined, 'underline')");
  });
});
