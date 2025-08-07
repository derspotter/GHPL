# Docs Folder Cleanup Script Usage

## Overview

The `dedupe_and_convert.py` script performs two main operations:
1. **Deduplication**: Removes duplicate files based on SHA-256 content hash
2. **Word to PDF Conversion**: Converts .docx files to PDF using pandoc

## Quick Start

### Test First (Recommended)
```bash
# Preview what will be changed without making changes
python dedupe_and_convert.py --dry-run

# Only test deduplication (no conversion)
python dedupe_and_convert.py --dry-run --no-convert
```

### Run Deduplication Only
```bash
# Remove duplicates only (preserves Word documents)
python dedupe_and_convert.py --no-convert
```

### Run Word to PDF Conversion Only
```bash
# Convert Word docs only (no deduplication)
python dedupe_and_convert.py --no-dedup
```

### Full Cleanup
```bash
# Do both deduplication and conversion
python dedupe_and_convert.py
```

## Current Results Summary

**Your docs folder analysis:**
- **Total files**: 2,622
- **Word documents**: 208 (.docx files)
- **Duplicate sets found**: 32 (33 duplicate files to be removed)

## What Each Operation Does

### Deduplication
- Scans all files and calculates SHA-256 hash of content
- Groups files with identical content
- Keeps the first occurrence (alphabetically) of each duplicate set
- Moves duplicates to `docs/duplicates/` folder (preserves file structure)
- **Found duplicates include**:
  - PNG_B3_Non_Communicable_Diseases_Multisecotoral_Strategic_Plan_2015-2020.docx (duplicate)
  - National_Cervical_Cancer_Prevention_Plan_FINALFeb_2012.pdf (duplicate)
  - Strategic-directions2010-2015_1.pdf (duplicate)
  - And 30 more duplicate files

### Word to PDF Conversion
- Finds all .docx files in the docs folder
- Uses pandoc + weasyprint to convert to PDF
- Moves original .docx files to `docs/converted_originals/` folder
- Skips conversion if PDF already exists

## Prerequisites

For Word to PDF conversion, install:
```bash
# Ubuntu/Debian
sudo apt install pandoc weasyprint

# macOS
brew install pandoc
pip install weasyprint

# Alternative: pandoc with pdflatex
sudo apt install pandoc texlive-latex-base texlive-latex-extra
```

## Command Line Options

```bash
python dedupe_and_convert.py [OPTIONS]

Options:
  --dry-run              Preview changes without making them
  --docs-path PATH       Path to docs folder (default: ./docs)
  --no-dedup             Skip deduplication
  --no-convert           Skip Word to PDF conversion  
  --verbose              Enable verbose logging
```

## Output Files

- `cleanup.log` - Detailed log of all operations
- `docs/duplicates/` - Moved duplicate files (preserves structure)
- `docs/converted_originals/` - Original .docx files after conversion

## Safety Features

- **Dry-run mode**: Preview all changes before applying
- **Preserve originals**: Duplicates and Word docs moved, not deleted
- **Detailed logging**: Full audit trail in cleanup.log
- **Error handling**: Graceful handling of file access errors
- **Progress tracking**: Shows progress for large operations

## Example Usage

```bash
# Safe test run first
python dedupe_and_convert.py --dry-run --verbose

# Remove duplicates only
python dedupe_and_convert.py --no-convert

# Convert Word docs only (requires pandoc)
python dedupe_and_convert.py --no-dedup

# Full cleanup (if pandoc available)
python dedupe_and_convert.py
```

The script is ready to use! Run with `--dry-run` first to see exactly what changes will be made.