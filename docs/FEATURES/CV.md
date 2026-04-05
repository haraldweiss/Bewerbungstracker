# 📋 CV Vergleich & Dateiverarbeitung / CV Comparison Guide

## Überblick / Overview

Das **CV Vergleich Feature** ermöglicht dir, deine CV mit Stellenausschreibungen zu vergleichen, indem du AI-Plattformen nutzt. Die App unterstützt PDF, DOCX und TXT Upload mit automatischer Extraktion und Optimierung.

The **CV Comparison feature** lets you compare your CV against job postings using multiple AI platforms. The app supports PDF, DOCX, and TXT uploads with automatic extraction and optimization.

---

## 📄 Dateiupload / File Upload

### Unterstützte Formate / Supported Formats

| Format | Geschwindigkeit | Status | Besonderheiten |
|--------|-----------------|--------|---|
| **TXT** | ⚡ Instant | ✅ Voll | Direkter Upload |
| **PDF** | 1-3s | ✅ Voll | Text-basierte PDFs (nicht gescannt) |
| **DOCX** | <1s | ✅ Voll | Microsoft Word Dokumente |
| **DOC** | ❌ | ⚠️ Nein | Zu .docx oder PDF konvertieren |

### Upload-Prozess

1. Gehe zu **📋 CV Vergleich** → Upload-Tab
2. Wähle deine Datei (.txt, .pdf, oder .docx)
3. Datei wird automatisch verarbeitet:
   - Text extrahiert
   - Formatierung bereinigt
   - Statistiken berechnet
4. Überprüfe den extrahierten Text
5. Klicke **💾 Speichern**

### Datei-Extraktion / File Extraction

**PDF Dateibearbeitung:**
- Multi-Page Extraktion mit PDF.js
- Text aus allen Seiten zusammengefügt
- Whitespace normalisiert
- Bilder werden ignoriert

**DOCX Dateibearbeitung:**
- Text mit mammoth.js extrahiert
- Bullet Points und Listen erhalten
- Tabellentexte als komma-getrennt
- Komplexe Formatierung entfernt

**Limits:**
- TXT: 50 MB
- PDF: 20 MB (max 100 Seiten)
- DOCX: 10 MB

### Text-Cleanup ✨

Automatische Bereinigung:
- ✅ Extra-Leerzeichen entfernt
- ✅ Zeilenumbrüche normalisiert
- ✅ Randzeichen getrimmt
- ✅ Lesbarkeit optimiert

Manuelle Cleanup anfordern:
Klicke **🧹 Formatieren** um Statistik zu sehen: "✅ Formatiert: 3,200 → 2,950 Zeichen (-250)"

---

## 📊 Text-Validierung & Statistiken

### Statistiken berechnen

Die App zeigt automatisch:
- **Wörter**: Gesamtwortanzahl
- **Zeichen**: Zeichenanzahl (ohne Leerzeichen)
- **Geschätzte Tokens**: Ungefähre AI-Token (~1 Token = 4 Zeichen)

Beispiel:
```
Wörter: 450
Zeichen: 3,000
Geschätzte Tokens: 750
```

### Größen-Limits & Validierung

| Limit | Wert | Funktion |
|-------|------|----------|
| Max Zeichen | 50,000 | Verhindet zu große Eingaben |
| Max Wörter | 10,000 | Angemessene Länge |
| Safe Token-Limit | 30,000 | Funktioniert mit allen APIs |
| Payload Max | 5 MB | Netzwerk-Limit |
| Request Timeout | 60 Sekunden | Verhindert Hängen |

**Warnungen:**
- ⚠️ 20,000-30,000 Token: Warnung (funktioniert noch)
- ❌ >30,000 Token: Fehler (abgelehnt)

### Token-Berechnung

```
Formula: estimatedTokens = chars / 4

Beispiele:
- 1,000 Zeichen ≈ 250 Tokens
- 5,000 Zeichen ≈ 1,250 Tokens
- 10,000 Zeichen ≈ 2,500 Tokens
- 50,000 Zeichen ≈ 12,500 Tokens
```

---

## 🤖 CV Vergleich mit AI

### Unterstützte AI-Plattformen / Supported AI Platforms

**Web-basiert (manuell):**
- 🧠 Claude (https://claude.ai)
- 🤖 ChatGPT (https://chat.openai.com)
- ✨ Google Gemini (https://gemini.google.com)
- 💬 Microsoft Copilot (https://copilot.microsoft.com)

**API-basiert (automatisch):**
- Benutzerdefinierte AI-Plattformen mit API-Key

### Basis-Workflow (Web-basiert)

1. Lade deine CV hoch oder paste Text
2. Paste Stellenausschreibung
3. Klicke **⚡ Vergleichs-Prompt generieren**
4. Klicke **🚀 Öffnen** für deine bevorzugte AI
5. Paste den Prompt in die AI-Plattform
6. Kopiere AI's Antwort
7. Paste Antwort in **📝 Ergebnisse** Bereich
8. Klicke **💾 Speichern**

### Advanced Workflow (API-basiert)

1. Gehe zu **⚙️ KI-Plattformen**
2. Klicke **➕ Hinzufügen**:
   - Name: z.B. "Meine Claude API"
   - URL: Dein API-Endpoint
   - API Key: Dein Auth-Key (verschlüsselt)
   - Type: **⚡ API-basiert**
3. Im Comparison-Tab:
   - CV vorbereiten
   - Prompt generieren
   - Klick **⚡ Senden**
   - Ergebnisse auto-füllen

### Platform-spezifische Limits

| Platform | Context | Safe Limit | Empfohlenes Limit |
|----------|---------|------------|---|
| **Claude** | 100k Tokens | 80k | <30k |
| **ChatGPT-4** | 128k Tokens | 30k | <30k |
| **GPT-3.5** | 4k Tokens | 3k | <2k |
| **Gemini** | 30k Tokens | 25k | <20k |
| **Copilot** | 5k Tokens | 4k | <3k |

### API-Key Sicherheit

✅ **Speicherung:**
- Keys werden verschlüsselt (PBKDF2 mit 100,000 Iterationen + Fernet AES)
- Gespeichert nur lokal im Browser
- Nicht auf Servern übertragen

✅ **Best Practices:**
- Nutze dedizierte API-Keys (nicht Haupt-Account)
- Rotiere Keys regelmäßig
- Entferne Keys wenn du Computer wechselst
- Teile Keys nie in Vergleichen/Exports

---

## 💡 Best Practices

### Vor dem CV-Upload
1. Stelle sicher PDF ist text-basiert (nicht gescannt)
2. DOCX sollte in neuester Version sein
3. Dateigröße <20 MB

### Nach dem Upload
1. Überprüfe extrahierten Text
2. Klick **🧹 Formatieren** um zu bereinigen
3. Klick **📊 Statistik** um Limits zu prüfen
4. Klick **💾 Speichern**

### Für bessere Vergleiche
1. **Metrics hinzufügen**: Spezifische Zahlen (Jahre, %)
2. **Keywords nutzen**: Kopiere Keywords aus der Stellenanzeige
3. **Achievements hervorheben**: Quantifizierbare Ergebnisse
4. **Spezifisch sein**: Nutze vollständige Job-Titel und Technologien

### Für große CVs
Wenn >5,000 Wörter:
- Fasse Achievements zusammen
- Entferne alte Positionen (>10 Jahre)
- Konsolidiere Skills
- Nutze prägnante Sprache

---

## ❓ FAQ & Troubleshooting

### "Dateiformat nicht unterstützt"
→ Nutze .txt, .pdf, oder .docx
→ Konvertiere .doc in Word zu .docx
→ Konvertiere .pages zu PDF

### "Keine Text extrahiert"
**PDF:**
- Stelle sicher es ist text-basiert (nicht gescannt)
- Exportiere nochmal aus Word als PDF
- Nutze OCR-Tool für gescannte PDFs

**DOCX:**
- Datei könnte beschädigt sein
- Öffne in Word und speichern erneut

### "CV zu lang" Warnung
- Entferne alte Erfahrung (>10 Jahre alt)
- Verkürze Beschreibungen
- Nutze Bullet Points statt Absätze
- Kombiniere verwandte Skills

### "Prompt zu groß"
- Verkürze CV (entferne ältere Jobs)
- Verkürze Stellenausschreibung (konzentriere dich auf Schlüssel-Anforderungen)
- Nutze Abstract der Ausschreibung
- Splitte in mehrere Vergleiche auf

### "Keine Text extrahiert" für PDF
- Versuche PDF nochmal zu exportieren
- Stelle sicher PDF ist nicht passwort-geschützt
- Versuche DOCX-Format statt
- Nutze plain text paste-Methode

### Request Timeout Error
- Prüfe Netzwerk-Verbindung
- Reduziere Prompt-Größe
- Versuche andere API-Plattform
- Prüfe API-Service-Status

---

## 🔧 Technische Details

### Libraries
- **PDF Extraktion**: PDF.js v3.11.174 (Mozilla)
- **DOCX Extraktion**: mammoth.js v1.6.0
- **Verschlüsselung**: Fernet (AES-128)
- **Key-Derivation**: PBKDF2 (100k iterations)

### Text-Verarbeitung Schritte
1. `cleanCVText()` - Whitespace normalisieren
2. `formatCVForAI()` - Für AI optimieren
3. `getCVStats()` - Metriken berechnen
4. `validateCVSize()` - Limits prüfen

### Datenschutz
✅ Alle Verarbeitung im Browser (client-seitig)
✅ Keine Dateien zum Server gesendet
✅ Gespeichert nur in Browser localStorage
✅ Keine Cloud-Speicherung
✅ Datenschutz gewährleistet

---

## 📝 Version-Info

- **Feature hinzugefügt**: v4.4 (CV Comparison)
- **Upload hinzugefügt**: v4.5 (File Upload)
- **Cleanup hinzugefügt**: v4.5 (Text Cleanup)
- **Datenbank**: SQLite3
- **Letztes Update**: 2025-03-16

---

**Viel Erfolg beim CV-Vergleich! 🎉**
