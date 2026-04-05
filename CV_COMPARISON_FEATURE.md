# 📋 CV Comparison Feature - Complete Documentation

## Overview
The CV Comparison feature allows you to compare your CV against job postings using multiple AI platforms. You can use built-in web-based AI tools or add custom AI platforms with API support.

## Features

### 1. CV Management
- **Upload CV**: Upload PDF, DOCX, or TXT files
- **Text Input**: Paste or type your CV directly
- **Auto-Save**: CV is stored locally in your browser
- **Status Display**: See when your CV was last updated

### 2. Job Comparison
- **Paste Job Posting**: Add any job description or posting
- **Auto-Prompt Generation**: Creates an AI-optimized comparison prompt
- **Multi-Format Support**: Works with any job posting format

### 3. Built-in AI Platforms
Pre-configured platforms available without API keys:
- 🧠 **Claude** (https://claude.ai)
- 🤖 **ChatGPT** (https://chat.openai.com)
- ✨ **Google Gemini** (https://gemini.google.com)
- 💬 **Microsoft Copilot** (https://copilot.microsoft.com)

**Usage**: Click "🚀 Öffnen" to open the AI platform, then manually paste the generated prompt.

### 4. Custom AI Platform Management
Add your own AI platforms with the following information:

#### Required Fields
- **Name**: Display name (e.g., "Claude API", "My Custom AI")
- **URL/Endpoint**: 
  - For web platforms: `https://your-ai-platform.com`
  - For API: `https://api.your-platform.com/v1/chat`
- **Type**: Choose between:
  - 🌐 **Web-based**: Opens in new tab (manual prompt entry)
  - ⚡ **API-based**: Direct integration (requires API Key)

#### Optional Fields
- **API Key**: For API-based platforms (stored encrypted)
- **Description**: Short description of the platform

### 5. Comparison Results
- **View & Edit**: Edit AI responses and analysis
- **Save Results**: Store comparisons with custom titles
- **View History**: Browse all saved comparisons
- **Delete Results**: Remove comparisons you no longer need
- **Export**: Export comparison as JSON file

## How to Use

### Basic Workflow (Web-based AI)
1. Go to **"📋 CV Vergleich"** in navigation
2. **Upload Tab**:
   - Upload your CV or paste CV text
   - Click "💾 Speichern"
3. **Comparison Tab**:
   - Paste a job posting
   - Click "⚡ Vergleichs-Prompt generieren"
   - Click "🚀 Öffnen" for your preferred AI
   - Paste the prompt into the AI
   - Copy the AI's response
   - Paste response in "📝 Ergebnisse" section
   - Click "💾 Speichern" to store the comparison

### Advanced Workflow (API-based Custom AI)
1. Go to **"⚙️ KI-Plattformen"** tab
2. **Add Custom Platform**:
   - Enter Name: e.g., "My Claude API"
   - Enter URL: Your API endpoint
   - Enter API Key: Your authentication key
   - Select Type: "⚡ API-basiert"
   - Click "➕ Hinzufügen"
3. Go to **Comparison Tab**:
   - Prepare CV and job posting
   - Generate prompt
   - Click "⚡ Senden" on your custom AI
   - Results auto-populate in results area

## API Key Security

### Storage
- API Keys are **encrypted** before storage
- Uses **PBKDF2 key derivation** with 100,000 iterations
- Stored in local browser storage (not transmitted)

### Best Practices
- Use **dedicated API keys** for AI platforms (avoid main account keys)
- Rotate keys periodically
- Remove keys if you change systems
- Never share keys in comparisons/exports

## API Endpoints (Backend)

### Save Comparison
```
POST /api/cv-comparison/save
{
  "title": "Apple Position - Software Engineer",
  "result": "The analysis shows...",
  "cv_file": "resume.pdf"
}
```

### List Comparisons
```
GET /api/cv-comparison/list
```

### Get Single Comparison
```
GET /api/cv-comparison/{id}
```

### Delete Comparison
```
DELETE /api/cv-comparison/{id}
```

### Export Comparison
```
POST /api/cv-comparison/export
{
  "id": 1
}
```

## Database Schema

### cv_comparisons Table
```sql
CREATE TABLE cv_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    result TEXT,
    cv_file TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

## Tips & Tricks

### For Better Comparisons
1. **Include Metrics**: Add specific numbers (years, percentages)
2. **Use Keywords**: Copy keywords from the job posting into your CV
3. **Highlight Achievements**: Use quantifiable results
4. **Be Specific**: Use full job titles and technologies

### For Custom AI Integration
1. **Test First**: Test your API key and endpoint with the AI platform directly
2. **Rate Limits**: Be aware of API rate limits
3. **Cost**: Some APIs have costs - track usage
4. **Backups**: Keep backup API keys in a secure location

### For Results Management
1. **Name Clearly**: Use titles like "Company - Position - Date"
2. **Export Regularly**: Export important comparisons as backup
3. **Organize**: Delete outdated comparisons to keep list clean

## Troubleshooting

### "CV not saved" error
→ Go to **Upload tab**, paste CV text, click "💾 Speichern"

### Custom AI not responding
→ Check:
- API endpoint is correct
- API key is valid
- Network connection is active
- API rate limits not exceeded

### Prompt not copied
→ Try:
- Click "📋 Kopieren" button again
- Check browser clipboard permissions
- Use manual copy (Ctrl+C/Cmd+C)

### Results not saving
→ Try:
- Ensure you're online
- Check browser localStorage isn't full
- Clear browser cache and try again

## Version Info
- **Feature Added**: v4.4
- **Database**: SQLite3
- **Encryption**: PBKDF2 + Fernet
- **Storage**: Local browser + backend database

## Future Enhancements
- [ ] PDF parsing for CV extraction
- [ ] Automatic skill matching visualization
- [ ] AI-powered recommendations
- [ ] Batch comparison support
- [ ] Integration with job boards
- [ ] Comparison templates
