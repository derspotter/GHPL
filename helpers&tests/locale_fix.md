# LibreOffice CSV Locale Issues - Fix Guide

## The Problem
- Your system locale uses comma (,) as decimal separator (e.g., German, French, Spanish)
- CSV data uses period (.) as decimal separator (US/UK standard)
- LibreOffice interprets "0.875" as "875" (period seen as thousands separator)

## Solutions

### 1. Temporary Locale Change (Quick Fix)
```bash
# Open LibreOffice with US locale just for this session
LC_NUMERIC=en_US.UTF-8 libreoffice --calc meta_gpt5_results_20250810_190823_repaired.csv
```

### 2. Change LibreOffice Language Settings
**Tools → Options → Language Settings → Languages**
- Change "Locale setting" to "English (USA)" temporarily
- Or change "Decimal separator key" settings

### 3. Import with Correct Settings
When opening CSV:
1. **File → Open** (not double-click!)
2. In Text Import Dialog:
   - Check "Separated by: Comma"
   - Language: "English (USA)" 
   - Check preview carefully

### 4. Use Semi-colon Separated Files
For European locales, use semicolon (;) as delimiter:
```python
# Convert to semicolon-separated
import pandas as pd
df = pd.read_csv('meta_gpt5_results_20250810_190823_repaired.csv')
df.to_csv('repaired_semicolon.csv', sep=';', index=False)
```

### 5. System-wide Fix (Permanent)
Edit locale settings:
```bash
# Check current locale
locale | grep LC_NUMERIC

# For current session only
export LC_NUMERIC=en_US.UTF-8

# Or create mixed locale (keep language, change numbers)
export LANG=de_DE.UTF-8  # or your language
export LC_NUMERIC=en_US.UTF-8
```

## Best Practice for International Data
- Always use ISO standard (period for decimal)
- Consider using TSV (tab-separated) to avoid comma conflicts
- Document the expected locale in README
- Use pandas/R for data analysis instead of spreadsheets when possible

## Quick Python Alternative
```python
# View data without locale issues
import pandas as pd
df = pd.read_csv('meta_gpt5_results_20250810_190823_repaired.csv')
df.to_excel('repaired.xlsx', index=False)  # Excel handles it better
# Or view in Jupyter/terminal
print(df[['filename', 'overall_confidence', 'metadata_completeness']].head(20))
```