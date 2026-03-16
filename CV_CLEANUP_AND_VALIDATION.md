# 🧹 CV Cleanup & Text Validation - Feature Guide

## Overview
The CV Comparison feature now includes intelligent text cleanup, formatting optimization, and API request validation to ensure your CVs and prompts work perfectly with AI platforms.

## Features

### 1. Automatic CV Cleanup ✨

#### What Gets Cleaned
- **Extra Spaces**: Removes multiple consecutive spaces
- **Line Breaks**: Normalizes excessive blank lines (keeps 1-2 max)
- **Whitespace**: Trims leading/trailing spaces from each line
- **Formatting**: Standardizes overall text structure

#### When It Happens
- **Automatic**: When you click "💾 Speichern"
- **Manual**: Click "🧹 Formatieren" button anytime
- **On Load**: Cleans uploaded files automatically

#### Example
```
Before:
"Name:    John    Doe
Position:   Senior    Developer


Years:     5"

After:
"Name: John Doe
Position: Senior Developer

Years: 5"
```

### 2. Text Statistics & Monitoring 📊

#### What Gets Measured
- **Words**: Total word count
- **Characters**: Total character count (including spaces)
- **Estimated Tokens**: Rough token count (~1 token = 4 chars)

#### Where You See It
- CV Status display (after upload)
- Cleanup button (shows bytes saved)
- Statistics popup (detailed breakdown)
- Prompt generation (token count)

#### Token Estimation
```
Words: 500
Chars: 3,000
Tokens: ~750 (est.)

Formula: chars / 4 ≈ tokens
```

### 3. Size Validation 🚨

#### Built-in Limits
| Limit | Value | Purpose |
|-------|-------|---------|
| Max Characters | 50,000 | Prevent oversized inputs |
| Max Words | 10,000 | Reasonable length |
| Safe Token Limit | 30,000 | Works with all APIs |
| Payload Max | 5 MB | Network limit |
| Request Timeout | 60 seconds | Prevent hangs |

#### When Limits Are Checked
1. **CV Save**: Validates size before saving
2. **Prompt Generation**: Checks total prompt size
3. **API Send**: Validates per-platform limits
4. **Request Size**: Checks JSON payload

#### Warning Levels
- ⚠️ **Warning**: 20,000-30,000 tokens (still works)
- ❌ **Error**: >30,000 tokens (rejected)
- ❌ **Critical**: >50,000 chars or 5MB (blocked)

### 4. AI-Optimized Formatting 🤖

#### What Gets Optimized
- **Section Structure**: Logical organization
- **Keyword Density**: Better keyword matching
- **Readability**: Clear formatting
- **Context**: Proper context for AI analysis

#### Format Improvements
- Consistent spacing between sections
- Clear section headers
- Proper punctuation
- Standardized date formats
- Aligned bullet points

### 5. Platform-Specific API Limits ⚡

#### Claude (Anthropic)
- **Context Window**: 100,000 tokens
- **Safe Limit**: 80,000 tokens
- **Recommended**: <30,000 tokens

#### ChatGPT (OpenAI)
- **GPT-4**: 128,000 tokens
- **GPT-3.5**: 4,096 tokens
- **Safe Limit**: 20,000 tokens

#### Google Gemini
- **Context**: 30,000 tokens
- **Safe Limit**: 25,000 tokens
- **Recommended**: <20,000 tokens

#### Microsoft Copilot
- **Context**: 5,000 tokens
- **Safe Limit**: 4,000 tokens
- **Note**: Smaller model

## How to Use

### Automatic Cleanup (On Save)
1. Paste or upload CV
2. Click "💾 Speichern"
3. Text automatically cleaned
4. See stats: "✅ CV gespeichert (450 Wörter, 113 Tokens)"

### Manual Cleanup
1. Click "🧹 Formatieren"
2. See improvements: "✅ Formatiert: 3,200 → 2,950 Zeichen (-250)"
3. CV cleaned and optimized

### View Statistics
1. Click "📊 Statistik"
2. See detailed breakdown:
   ```
   📊 CV STATISTIK
   
   Wörter: 450
   Zeichen: 3,000
   Geschätzte Tokens: 750
   
   LIMITS:
   Max Zeichen: 50.000 (6.0% genutzt)
   Max Wörter: 10.000 (4.5% genutzt)
   Max Tokens: 12.500 (6.0% genutzt)
   
   ✅ BEREIT für AI-Vergleich
   ```

### Generate Prompt with Validation
1. Enter CV and job posting
2. Click "⚡ Vergleichs-Prompt generieren"
3. System validates automatically:
   - Checks CV size
   - Validates job description size
   - Combines and checks total
   - Shows token count
4. If valid: "✅ Prompt generiert und validiert"
5. If oversized: "❌ Prompt zu groß"

### Send to API with Limits
1. Click "⚡ Senden" on custom AI
2. System validates:
   - API platform limits
   - Payload size
   - Token count
3. If valid: Sends with 60-second timeout
4. If invalid: "❌ Request überschreitet Limit"

## Best Practices

### Before Sharing CV
1. Click "🧹 Formatieren"
2. Click "📊 Statistik"
3. Ensure it says "✅ BEREIT"
4. Save to lock in formatting

### For Large CVs
1. Check statistics first
2. If >5,000 words:
   - Summarize achievements
   - Remove old positions
   - Consolidate skills
   - Use concise language
3. Re-check stats

### For API Integration
1. Always copy prompt first
2. Use test with small data
3. Monitor response times
4. Check for timeouts
5. Validate results

### For Different AI Platforms
1. **Claude**: No strict limit (use <80k tokens)
2. **GPT-4**: 128k limit (use <30k safely)
3. **Gemini**: ~30k limit (use <20k safely)
4. **Copilot**: 5k limit (keep very concise)

## Troubleshooting

### "CV zu lang" Warning
→ **Solution**:
1. Remove old experience (>10 years old)
2. Shorten descriptions
3. Use bullet points instead of paragraphs
4. Combine related skills
5. Delete redundant sections

### "Prompt zu groß" Error
→ **Solution**:
1. Shorten CV (remove older jobs)
2. Shorten job posting (focus on key requirements)
3. Use abstract of posting
4. Split into multiple comparisons

### Request Timeout Error
→ **Solution**:
1. Check network connection
2. Reduce prompt size
3. Try different API platform
4. Check API service status

### API Validation Failed
→ **Solution**:
1. Check API endpoint is correct
2. Verify API key is valid
3. Check platform-specific limits
4. Test with smaller CV

## Advanced Features

### Custom Text Processing
```javascript
// All text goes through:
1. cleanCVText() - Normalize whitespace
2. formatCVForAI() - Optimize for AI
3. getCVStats() - Calculate metrics
4. validateCVSize() - Check limits
```

### Token Calculation
```
Formula: estimatedTokens = Math.ceil(chars / 4)

Examples:
- 1,000 chars ≈ 250 tokens
- 5,000 chars ≈ 1,250 tokens
- 10,000 chars ≈ 2,500 tokens
- 50,000 chars ≈ 12,500 tokens
```

### Size Limits
```
Small CV: <2,000 words, 1,500-3,000 chars
Medium CV: 2,000-5,000 words, 8,000-20,000 chars
Large CV: >5,000 words, >20,000 chars
Max Safe: 10,000 words, 50,000 chars
```

## Performance Tips

### Optimize Before Sending
1. Remove formatting characters
2. Use plain text (no special symbols)
3. Group related items
4. Use standard abbreviations
5. Minimize descriptions

### For Faster Processing
1. Keep CVs under 3,000 words
2. Use bullet points
3. Avoid unnecessary formatting
4. Be specific, not verbose
5. Focus on relevant experience

### For Better Results
1. Clean text first (🧹)
2. Check stats (📊)
3. Use consistent formatting
4. Include quantifiable metrics
5. Add relevant keywords

## Version Info
- **Feature Added**: v4.4
- **Last Updated**: v4.5
- **Database**: SQLite3
- **Storage**: Browser + Backend

## FAQ

**Q: Can I use CVs larger than 50,000 chars?**
A: No, system will reject them. Split into multiple files instead.

**Q: What's the difference between chars and tokens?**
A: Tokens are AI-counted units (roughly 4 chars = 1 token). AI APIs charge by tokens.

**Q: Do cleanup functions remove content?**
A: No, only formatting. All actual text is preserved.

**Q: How accurate is token estimation?**
A: ~90% accurate. Actual tokens depend on AI tokenizer.

**Q: Can I disable validation?**
A: No, validation is required for API safety.

**Q: Does cleanup change my CV meaning?**
A: No, only formatting. Meaning/content unchanged.
