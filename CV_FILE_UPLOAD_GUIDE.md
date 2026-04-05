# 📄 CV File Upload & Conversion Guide

## Overview
The CV upload feature now supports automatic conversion of PDF and DOCX files to plain text, with intelligent text extraction and cleanup.

## Supported File Formats

### ✅ Fully Supported

#### Plain Text (.txt)
- **Direct Upload**: No conversion needed
- **Speed**: Instant
- **Best For**: Already formatted plain text CVs
- **Example**: `resume.txt`, `lebenslauf.txt`

#### PDF (.pdf)
- **Extraction**: Multi-page PDF text extraction
- **Technology**: PDF.js (Mozilla)
- **Speed**: ~1-3 seconds (depends on file size)
- **Best For**: Professional CVs from Word/Pages converted to PDF
- **Example**: `resume.pdf`, `lebenslauf.pdf`

#### DOCX (.docx)
- **Extraction**: Word document text extraction
- **Technology**: mammoth.js
- **Speed**: Instant
- **Best For**: CVs created in Microsoft Word
- **Example**: `resume.docx`, `lebenslauf.docx`

### ⚠️ Partially Supported

#### DOC (.doc) - Legacy Format
- **Status**: Not Supported
- **Recommendation**: Convert to .docx or PDF first
- **Conversion Tools**:
  - LibreOffice: Free, open-source
  - Microsoft Word: Save As .docx
  - Google Docs: Export as PDF

### ❌ Not Supported
- `.odt` (OpenOffice) - Convert to PDF
- `.pages` (Apple Pages) - Convert to PDF/DOCX
- `.rtf` (Rich Text Format) - Convert to DOCX/TXT
- Images/Scanned PDFs - Use OCR tool first

## How to Upload

### Step 1: Choose File
Click "📤 CV hochladen" in the CV tab and select your file.

### Step 2: File is Processed
- Shows progress: "📄 Liest resume.pdf..."
- Extracts text automatically
- Cleans up formatting
- Calculates statistics

### Step 3: Review & Save
- Text appears in textarea
- Statistics displayed: "✅ CV hochgeladen (450 Wörter, 113 Tokens)"
- Click "💾 Speichern" to finalize

## File Processing Details

### Plain Text (.txt)
```
Input: resume.txt (raw text)
Process: Load directly
Output: Plain text saved
```

### PDF (.pdf)
```
Input: resume.pdf
Process:
1. Read PDF with PDF.js
2. Extract text from each page
3. Join pages with line breaks
4. Cleanup whitespace
5. Save as plain text
Output: Extracted plain text
```

### DOCX (.docx)
```
Input: resume.docx
Process:
1. Read DOCX with mammoth.js
2. Extract text content
3. Strip formatting
4. Cleanup whitespace
5. Save as plain text
Output: Extracted plain text
```

## What Gets Extracted

### From PDF Files
✅ Text content
✅ Page breaks (converted to line breaks)
✅ Basic formatting (preserved as spaces)
❌ Images
❌ Tables (extracted as text)
❌ Colored text (color info lost)

### From DOCX Files
✅ Paragraph text
✅ Bullet points
✅ Numbered lists
✅ Text from tables (as comma-separated)
❌ Images
❌ Headers/footers (sometimes included)
❌ Complex formatting

### Text Cleanup Applied
- Extra spaces removed
- Line breaks normalized
- Whitespace trimmed
- Special characters cleaned

## Examples

### PDF Extraction Example
**Input PDF**: `resume.pdf`
```
John Doe
Senior Software Engineer

Experience:
• 5 years as Software Engineer
• 3 years as Senior Developer
```

**Extracted Text**:
```
John Doe Senior Software Engineer Experience: 5 years as Software Engineer 3 years as Senior Developer
```

**After Cleanup**:
```
John Doe
Senior Software Engineer

Experience:
5 years as Software Engineer
3 years as Senior Developer
```

### DOCX Extraction Example
**Input DOCX**: `resume.docx`
```
Contact Information
Name: Jane Smith
Email: jane@example.com

Skills
• Python
• JavaScript
```

**Extracted & Cleaned**:
```
Contact Information
Name: Jane Smith
Email: jane@example.com

Skills
Python
JavaScript
```

## Troubleshooting

### "Dateiformat nicht unterstützt"
**Problem**: File type not supported
**Solution**:
- Use .txt, .pdf, or .docx
- Convert .doc files to .docx in Word
- Convert .pages files to PDF
- Try exporting again

### "Keine Text extrahiert"
**Problem**: No text could be extracted
**Solution**:
- For PDF: Ensure it's text-based (not scanned image)
  - Try re-exporting from Word as PDF
  - Use OCR tool for scanned PDFs
- For DOCX: File might be corrupted
  - Try opening in Word and saving again
- For TXT: File might be empty

### "Fehler beim Lesen der Datei"
**Problem**: File reading error occurred
**Solution**:
- Ensure file is not corrupted
- Try closing file in other applications
- Check file permissions
- Try uploading again

### PDF Text Comes Out Garbled
**Problem**: Special characters or encoding issues
**Solution**:
- Re-export PDF from source application
- Ensure PDF is not password protected
- Try DOCX format instead
- Use plain text paste method

### DOCX File Not Recognized
**Problem**: .docx file not being recognized
**Solution**:
- Verify it's actually a .docx (open in Word)
- File might be saved as .doc - rename/save as .docx
- Check file extension is lowercase (.docx, not .DOCX)

## File Size Limits

| Format | Max Size | Max Pages | Notes |
|--------|----------|-----------|-------|
| .txt | 50 MB | N/A | Usually smaller |
| .pdf | 20 MB | 100 | Larger files = slower |
| .docx | 10 MB | N/A | Rarely this large |

## Performance Tips

### Fast Upload
- Use .txt files (instant)
- Keep DOCX files <5 MB
- Keep PDFs <10 pages

### Large CVs
- Split multi-year CV into relevant section
- Remove outdated experiences
- Use concise formatting
- Remove images/graphics

### Quality Extraction
- Use searchable PDFs (not scanned)
- Ensure DOCX is not password protected
- Use standard formatting
- Avoid complex tables

## Best Practices

### Before Uploading
1. **PDF**: Ensure it's text-based, not image
2. **DOCX**: Save as latest version
3. **All**: Check file size <20 MB

### After Upload
1. Review extracted text in textarea
2. Verify formatting is correct
3. Check for missing content
4. Click "🧹 Formatieren" to clean
5. Click "💾 Speichern" to save

### For Best Results
- Keep CV to <5,000 words
- Use standard fonts
- Avoid complex tables/images
- Use consistent formatting
- Test extraction before major upload

## Technical Details

### PDF.js
- **Library**: Mozilla PDF.js v3.11.174
- **Worker**: https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js
- **Pages**: Extracts all pages sequentially
- **Output**: Plain text with page breaks

### mammoth.js
- **Library**: mammoth v1.6.0
- **Format**: ECMA-376 (.docx)
- **Conversion**: HTML → Plain text
- **Output**: Clean plain text

### Text Cleanup
- **Function**: cleanCVText()
- **Removes**: Extra spaces, excess line breaks
- **Preserves**: Paragraph structure
- **Output**: Readable plain text

## Statistics After Upload

The system automatically calculates:
```
Words: 450
Characters: 3,000
Estimated Tokens: 750
```

This helps you:
- Monitor CV length
- Check AI processing costs
- Validate before API submission
- Optimize for different platforms

## File Upload Security

✅ **Safe Features**:
- All processing done in browser (client-side)
- No files sent to server
- Stored only in browser localStorage
- No cloud storage
- Privacy preserved

## Supported File Encodings

### PDF
- UTF-8 (recommended)
- ISO-8859-1 (Latin-1)
- Most standard encodings

### DOCX
- UTF-8 (standard for Office)
- All versions supported

### TXT
- UTF-8 (recommended)
- ASCII
- Other encodings may have issues

## Version Info
- **Feature Added**: v4.5
- **Libraries**: PDF.js 3.11.174, mammoth 1.6.0
- **Last Updated**: 2025-03-16

## FAQ

**Q: Can I upload a scanned PDF?**
A: No, scanned PDFs need OCR first. Use tools like Adobe Acrobat, Google Docs, or online OCR services.

**Q: How long does upload take?**
A: .txt (instant), .docx (<1s), .pdf (1-3s depending on size).

**Q: Is my CV stored on servers?**
A: No, all files are processed and stored locally in your browser only.

**Q: Can I upload multiple files?**
A: One at a time. Upload CV, then click "💾 Speichern" before uploading another.

**Q: What if PDF has tables?**
A: Tables are extracted as plain text with spaces. Format may not be perfect.

**Q: Can I edit after upload?**
A: Yes! Text appears in textarea and can be edited before saving.

**Q: Does it preserve formatting?**
A: Basic formatting is preserved. Complex formatting (colors, fonts) is not.

**Q: What about images in PDF/DOCX?**
A: Images are skipped. Only text content is extracted.
