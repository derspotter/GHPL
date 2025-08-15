# CSV Import Guide for LibreOffice Calc

## Common Issues with CSV Import

LibreOffice Calc can misinterpret CSV data, especially:
- Decimal numbers (0.875 → 875)
- Dates and times
- Long numbers (scientific notation)
- Mixed content in columns

## Solutions

### 1. Use Text Import Dialog (Recommended)
When opening a CSV in LibreOffice:
1. **File → Open** (not double-click)
2. Select the CSV file
3. In the Text Import dialog:
   - Set **Separator Options** to "Comma"
   - **IMPORTANT**: Check "Detect special numbers" is OFF if decimals are being corrupted
   - Or set specific columns to "Text" format to preserve exact values
   - Preview the data at the bottom

### 2. Import as Text Then Convert
1. Select all numeric columns in the preview
2. Set Column Type to "Text"
3. After import, convert to numbers using Find & Replace or formatting

### 3. Use Import Wizard
**Data → Text to Columns** after pasting data

### 4. Regional Settings Issue
Check **Tools → Options → Language Settings → Languages**
- Some locales use comma as decimal separator (European)
- This conflicts with comma-delimited CSV files
- Try switching to English (USA) temporarily

### 5. Alternative Approaches
- Use **pandas** in Python to view/analyze the data
- Use **csvkit** command-line tools
- Use Google Sheets (handles CSV better)
- Use a dedicated CSV viewer

## Quick Python Viewer
```python
import pandas as pd
df = pd.read_csv('meta_gpt5_results_20250810_190823_repaired.csv')
# View specific columns
print(df[['filename', 'metadata_completeness', 'overall_confidence']].head(20))
```