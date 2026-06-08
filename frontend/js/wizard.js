(function() {
    'use strict';

    var STEPS = [
        { id: 'welcome', title: 'Willkommen' },
        { id: 'provider', title: 'KI-Provider' },
        { id: 'email', title: 'E-Mail' },
        { id: 'discovery', title: 'Job-Suche' },
        { id: 'cv', title: 'Lebenslauf' },
        { id: 'done', title: 'Fertig' }
    ];

    var state = { step: 0, data: {} };
    var overlay = null;

    function init() {
        var token = localStorage.getItem('access_token');
        if (!token) return;
        Auth.fetch('/api/profile/wizard').then(function(r) {
            if (!r.ok) return r.json().then(function(j) {
                if (!j.onboarding_complete && !localStorage.getItem('wizard_done')) {
                    state.data = j.onboarding_data || {};
                    buildOverlay();
                }
            });
            return r.json().then(function(j) {
                if (!j.onboarding_complete && !localStorage.getItem('wizard_done')) {
                    state.data = j.onboarding_data || {};
                    buildOverlay();
                }
            });
        }).catch(function() {});
    }

    function buildOverlay() {
        overlay = document.createElement('div');
        overlay.className = 'wizard-overlay';

        var html = '<div class="wizard-modal">';
        html += '<div class="wizard-progress" id="wizard-progress">';
        for (var i = 0; i < STEPS.length; i++) {
            html += '<div class="wizard-dot" data-idx="' + i + '"></div>';
        }
        html += '</div>';
        for (var i = 0; i < STEPS.length; i++) {
            html += '<div class="wizard-step" data-step="' + i + '">' + getStepHTML(i) + '</div>';
        }
        html += '</div>';
        overlay.innerHTML = html;
        document.body.appendChild(overlay);
        showStep(0);
    }

    function getStepHTML(idx) {
        switch (idx) {
            case 0: return stepWelcome();
            case 1: return stepProvider();
            case 2: return stepEmail();
            case 3: return stepDiscovery();
            case 4: return stepCV();
            case 5: return stepDone();
        }
    }

    function stepWelcome() {
        return '<h2>👋 Willkommen beim Bewerbungstracker!</h2>'
            + '<p>Wir führen dich in wenigen Schritten durch die Einrichtung. '
            + 'Du kannst jeden Schritt überspringen und später in den Einstellungen nachholen.</p>'
            + '<div style="margin-top:20px;padding:16px;background:rgba(79,70,229,0.1);border-radius:8px;">'
            + '<p style="font-size:13px;margin:0;"><strong>⏱ Dauer:</strong> ca. 3-5 Minuten</p>'
            + '<p style="font-size:13px;margin:4px 0 0;"><strong>🔒 Hinweis:</strong> Deine Daten bleiben verschlüsselt und sicher.</p>'
            + '</div>';
    }

    function stepProvider() {
        var sel = state.data.provider || 'opencode';
        return '<h2>🤖 KI-Assistent wählen</h2>'
            + '<p>Wähle den KI-Dienst für die automatische Bewertung von Stellenanzeigen.</p>'
            + '<div class="wizard-option-card' + (sel === 'opencode' ? ' selected' : '') + '" data-provider="opencode" onclick="selectProvider(\'opencode\')">'
            + '<h3>⭐ opencode.ai (empfohlen)</h3><p>Kostenlose Modelle, keine Anmeldung nötig. Starte sofort durch.</p></div>'
            + '<div class="wizard-option-card' + (sel === 'claude' ? ' selected' : '') + '" data-provider="claude" onclick="selectProvider(\'claude\')">'
            + '<h3>🧠 Claude (Anthropic)</h3><p>Beste Qualität, benötigt einen API-Key von console.anthropic.com</p></div>'
            + '<div class="wizard-option-card' + (sel === 'ollama' ? ' selected' : '') + '" data-provider="ollama" onclick="selectProvider(\'ollama\')">'
            + '<h3>💻 Ollama (Lokal)</h3><p>Läuft auf deinem Rechner. Keine Internetverbindung nötig.</p></div>'
            + '<div id="wizard-provider-extra"></div>';
    }

    function stepEmail() {
        var sel = state.data.email_option || '';
        var gmailScript = '// Google Apps Script für E-Mail-Import\n'
            + '// https://script.google.com/...';
        return '<h2>📧 E-Mail-Anbindung</h2>'
            + '<p>Verbinde dein E-Mail-Postfach, damit der Tracker Bewerbungs-E-Mails importieren kann.</p>'
            + '<div class="wizard-option-card' + (sel === 'gmail' ? ' selected' : '') + '" onclick="selectEmail(\'gmail\')">'
            + '<h3>📧 Gmail / Google Mail</h3><p>Nutze ein Google Apps Script für den E-Mail-Import.</p></div>'
            + '<div class="wizard-option-card' + (sel === 'imap' ? ' selected' : '') + '" onclick="selectEmail(\'imap\')">'
            + '<h3>🔌 Eigener Server (IMAP)</h3><p>Für GMX, Web.de, Posteo, IONOS, etc.</p></div>'
            + '<div class="wizard-option-card' + (sel === 'skip' ? ' selected' : '') + '" onclick="selectEmail(\'skip\')">'
            + '<h3>⏭ Überspringen</h3><p>Richte ich später ein.</p></div>'
            + '<div id="wizard-email-extra"></div>';
    }

    function stepDiscovery() {
        var keywords = state.data.discovery_keywords || '';
        return '<h2>🔍 Job-Suche aktivieren</h2>'
            + '<p>Der Tracker kann automatisch passende Stellenanzeigen für dich finden.</p>'
            + '<p style="font-size:13px;margin-bottom:12px;"><strong>Nach welchen Jobs suchst du?</strong> (Stichworte, z.B. "IT-Sicherheit, Cyber Security, Berlin")</p>'
            + '<textarea class="wizard-input" id="wizard-discovery-input" rows="3" placeholder="Z.B. IT-Sicherheit, Cyber Security, Admin, Berlin">' + keywords + '</textarea>'
            + '<p style="font-size:12px;color:var(--text-muted,#94A3B8);margin-top:8px;">Deine Anfrage wird an den Administrator gesendet. Du bekommst Bescheid, sobald die Job-Suche aktiv ist.</p>';
    }

    function stepCV() {
        return '<h2>📄 Lebenslauf (optional)</h2>'
            + '<p>Lade deinen Lebenslauf hoch, damit die KI deine Qualifikationen besser bewerten kann.</p>'
            + '<div style="border:2px dashed var(--border,#334155);border-radius:10px;padding:32px;text-align:center;margin:16px 0;">'
            + '<p style="font-size:40px;margin:0;">📄</p>'
            + '<p style="margin:8px 0;font-size:13px;">PDF, DOCX oder Text — maximal 10 MB</p>'
            + '<input type="file" accept=".pdf,.docx,.txt" style="margin-top:8px;" id="wizard-cv-file">'
            + '</div>'
            + '<p style="font-size:12px;color:var(--text-muted,#94A3B8);">Du kannst diesen Schritt überspringen und später hochladen.</p>';
    }

    function stepDone() {
        var items = [
            { label: 'KI-Provider', key: 'provider', ok: state.data.provider || 'opencode', success: state.data.provider ? '✅ ' + state.data.provider : '✅ opencode.ai' },
            { label: 'E-Mail-Anbindung', key: 'email_option', ok: state.data.email_option, success: state.data.email_option === 'skip' ? '⏭ Übersprungen' : state.data.email_option === 'gmail' ? '✅ Gmail' : state.data.email_option === 'imap' ? '✅ IMAP' : '⏭ Übersprungen' },
            { label: 'Job-Suche', key: 'discovery_keywords', ok: state.data.discovery_keywords, success: state.data.discovery_keywords ? '✅ Aktiviert (' + state.data.discovery_keywords.substr(0, 30) + '...)' : '⏭ Übersprungen' },
            { label: 'Lebenslauf', key: 'cv_uploaded', ok: state.data.cv_uploaded, success: state.data.cv_uploaded ? '✅ Hochgeladen' : '⏭ Übersprungen' }
        ];
        var html = '<h2>🎉 Fertig!</h2><p>Hier ist eine Zusammenfassung deiner Einstellungen:</p><div class="wizard-summary">';
        for (var i = 0; i < items.length; i++) {
            var badge = items[i].ok ? 'wizard-badge-success' : 'wizard-badge-skip';
            html += '<div class="wizard-summary-item"><span>' + items[i].success + '</span></div>';
        }
        html += '</div><p style="font-size:13px;color:var(--text-muted,#94A3B8);">'
            + 'Du kannst jederzeit in die <strong>Einstellungen</strong> gehen, um etwas zu ändern.</p>';
        return html;
    }

    function showStep(idx) {
        state.step = idx;
        var steps = overlay.querySelectorAll('.wizard-step');
        for (var i = 0; i < steps.length; i++) {
            steps[i].classList.toggle('active', i === idx);
        }
        var dots = overlay.querySelectorAll('.wizard-dot');
        for (var j = 0; j < dots.length; j++) {
            dots[j].classList.toggle('active', j === idx);
            dots[j].classList.toggle('done', j < idx);
        }
        renderActions(idx);
        document.getElementById('wizard-step-content').scrollTop = 0;
    }

    function renderActions(idx) {
        var actions = overlay.querySelector('.wizard-actions');
        if (actions) actions.parentNode.removeChild(actions);
        var container = overlay.querySelector('.wizard-modal');
        var div = document.createElement('div');
        div.className = 'wizard-actions';
        if (idx > 0) {
            div.innerHTML += '<button class="wizard-btn wizard-btn-secondary" onclick="wizardPrev()">← Zurück</button>';
        } else {
            div.innerHTML += '<span></span>';
        }
        if (idx < STEPS.length - 1) {
            div.innerHTML += '<button class="wizard-btn wizard-btn-primary" onclick="wizardNext()" id="wizard-next-btn">Weiter →</button>';
        } else {
            div.innerHTML += '<button class="wizard-btn wizard-btn-primary" onclick="wizardFinish()">🔓 Zum Dashboard</button>';
        }
        div.innerHTML += '<button class="wizard-btn wizard-btn-ghost" onclick="wizardSkip()">Später erinnern</button>';
        container.appendChild(div);
    }

    window.selectProvider = function(p) {
        state.data.provider = p;
        var cards = overlay.querySelectorAll('[data-provider]');
        for (var i = 0; i < cards.length; i++) {
            cards[i].classList.toggle('selected', cards[i].getAttribute('data-provider') === p);
        }
        var extra = document.getElementById('wizard-provider-extra');
        if (p === 'claude') {
            extra.innerHTML = '<input class="wizard-input" placeholder="Dein Claude API-Key (sk-ant-...)" id="wizard-claude-key" value="' + (state.data.claude_key || '') + '">';
        } else {
            extra.innerHTML = '';
        }
    };

    window.selectEmail = function(o) {
        state.data.email_option = o;
        var cards = overlay.querySelectorAll('.wizard-option-card');
        for (var i = 0; i < cards.length; i++) {
            if (cards[i].getAttribute('onclick') && cards[i].getAttribute('onclick').indexOf("selectEmail") > -1) {
                var match = cards[i].getAttribute('onclick').match(/'([^']+)'/);
                cards[i].classList.toggle('selected', match && match[1] === o);
            }
        }
        var extra = document.getElementById('wizard-email-extra');
        if (o === 'gmail') {
            extra.innerHTML = '<p style="font-size:13px;margin:12px 0 4px;">1️⃣ Kopiere dieses Google Apps Script:</p>'
                + '<div class="wizard-code-block">' + '// Google Apps Script\nfunction importEmails() {\n  // ...\n}' + '</div>'
                + '<p style="font-size:13px;margin:8px 0 4px;">2️⃣ Füge die Script-URL hier ein:</p>'
                + '<input class="wizard-input" placeholder="https://script.google.com/..." id="wizard-gmail-url" value="' + (state.data.gmail_url || '') + '">';
        } else if (o === 'imap') {
            extra.innerHTML = '<input class="wizard-input" placeholder="IMAP-Server (z.B. imap.gmx.net)" id="wizard-imap-host" value="' + (state.data.imap_host || '') + '">'
                + '<input class="wizard-input" placeholder="Port (993)" id="wizard-imap-port" value="' + (state.data.imap_port || '993') + '">'
                + '<input class="wizard-input" placeholder="Benutzername" id="wizard-imap-user" value="' + (state.data.imap_user || '') + '">'
                + '<input class="wizard-input" type="password" placeholder="Passwort" id="wizard-imap-pass">';
        } else {
            extra.innerHTML = '';
        }
    };

    window.wizardNext = function() {
        collectData(state.step);
        var next = state.step + 1;
        if (next < STEPS.length) showStep(next);
    };

    window.wizardPrev = function() {
        var prev = state.step - 1;
        if (prev >= 0) showStep(prev);
    };

    window.wizardSkip = function() {
        localStorage.setItem('wizard_remind', 'true');
        closeWizard();
    };

    function collectData(idx) {
        if (idx === 0) { /* welcome - nothing to collect */ }
        if (idx === 1) {
            var keyInput = document.getElementById('wizard-claude-key');
            if (keyInput) state.data.claude_key = keyInput.value;
        }
        if (idx === 2) {
            var gmailUrl = document.getElementById('wizard-gmail-url');
            if (gmailUrl) state.data.gmail_url = gmailUrl.value;
            var imapHost = document.getElementById('wizard-imap-host');
            if (imapHost) state.data.imap_host = imapHost.value;
            var imapPort = document.getElementById('wizard-imap-port');
            if (imapPort) state.data.imap_port = imapPort.value;
            var imapUser = document.getElementById('wizard-imap-user');
            if (imapUser) state.data.imap_user = imapUser.value;
        }
        if (idx === 3) {
            var kw = document.getElementById('wizard-discovery-input');
            if (kw) state.data.discovery_keywords = kw.value;
        }
        if (idx === 4) {
            var fileInput = document.getElementById('wizard-cv-file');
            if (fileInput && fileInput.files.length > 0) state.data.cv_uploaded = true;
        }
        saveState();
    }

    function saveState() {
        Auth.fetch('/api/profile/wizard', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.data)
        }).catch(function() {});
    }

    window.wizardFinish = function() {
        collectData(state.step);
        Auth.fetch('/api/profile/wizard/complete', { method: 'POST' }).catch(function() {});
        localStorage.setItem('wizard_done', 'true');
        localStorage.removeItem('wizard_remind');
        closeWizard();
        if (typeof loadView === 'function') loadView('dashboard');
    };

    function closeWizard() {
        if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
        overlay = null;
    }

    // Auto-init after auth
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
