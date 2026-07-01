const fs = require('fs');
const path = require('path');

describe('calendar view script structure', () => {
  test('defines loadCalendarEvents outside loadDeletedEntries', () => {
    const html = fs.readFileSync(path.join(__dirname, '../../index.html'), 'utf8');
    const sectionStart = html.indexOf('DELETED ENTRIES MANAGEMENT');
    const sectionEnd = html.indexOf('function renderDeletedEntries');
    expect(sectionStart).toBeGreaterThan(-1);
    expect(sectionEnd).toBeGreaterThan(sectionStart);

    const section = html.slice(sectionStart, sectionEnd);
    const deletedFetch = section.indexOf("fetchAPI('/api/applications/deleted')");
    const calendarFunction = section.indexOf('async function loadCalendarEvents');

    expect(deletedFetch).toBeGreaterThan(-1);
    expect(calendarFunction).toBeGreaterThan(-1);
    expect(deletedFetch).toBeLessThan(calendarFunction);
  });
});
