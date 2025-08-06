# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Global Health Policy Library (GHPL) project focused on PDF document metadata extraction for health policy documents. The codebase includes tools for downloading health policy documents and extracting structured metadata using Google's Gemini AI API.

## Key Commands

### Python Environment
```bash
pip install -r requirements.txt
```

### Main Scripts
- `python cli.py <pdf_path>` - **NEW**: Extract metadata with ground truth validation
- `python get_metadata.py` - Extract metadata from a single PDF using Gemini API  
- `python download_docs.py` - Download documents from URLs in Excel file
- `python examine_excel.py` - Analyze structure of documents-info.xlsx
- `python test_validation.py` - Test ground truth validation system

### CLI Usage Examples
```bash
# Basic extraction with validation
python cli.py docs/sample.pdf

# Export deviations to Excel for analysis
python cli.py docs/sample.pdf --export-deviations deviations.xlsx

# Show only ground truth statistics
python cli.py docs/sample.pdf --stats-only

# Use custom Excel file
python cli.py docs/sample.pdf --excel custom_data.xlsx
```

### Dependencies
The project uses these key dependencies:
- `pandas==2.3.1` - Excel and data manipulation
- `requests==2.32.4` - HTTP requests for downloading
- `openpyxl==3.1.5` - Excel file handling
- `google-genai` - Gemini AI API (installed separately)
- `pikepdf` - PDF processing and repair
- `pydantic` - Data validation and structured output

## Architecture

### Core Components

**PDF Metadata Extraction Pipeline:**
1. **PDF Processing** (`get_metadata.py:91-208`): Uses pikepdf to extract first/last pages, with qpdf fallback for repair
2. **Gemini Integration** (`get_metadata.py:375-474`): Structured metadata extraction using Gemini 2.5 Pro
3. **Confidence Scoring** (`get_metadata.py:49-71`): Each field includes confidence scores and evidence
4. **Data Models** (`get_metadata.py:13-71`): Pydantic models for structured health policy metadata

**Document Management:**
- `download_docs.py` - Bulk document downloading from Excel URLs
- `documents-info.xlsx` - Reference metadata for ground truth validation (2659 documents)
- `docs/` - Directory containing thousands of health policy PDFs

**Ground Truth Validation System:**
- `ground_truth_validation.py` - Core validation functions
- `cli.py` - Command-line interface with integrated validation
- Compares extracted metadata against Excel reference data
- Tracks all deviations for quality assessment
- Adjusts confidence scores based on ground truth matches
- Exports detailed deviation reports to Excel

### Metadata Schema

The system extracts structured metadata for health policy documents:
- **Document Type**: Policy, Law, National Health Strategy, etc.
- **Health Topic**: Cancer, Cardiovascular Health, Non-Communicable Disease
- **Creator**: Parliament, Ministry, Agency, Foundation, etc.
- **Governance Level**: National, Regional
- **Confidence Scoring**: 0.0-1.0 with evidence and alternatives

### AI Integration

**Gemini API Usage:**
- Model: `gemini-2.5-pro`
- Input: First 3 pages + last 2 pages of PDFs
- Output: Structured JSON following Pydantic schema
- Features: Confidence scoring, evidence tracking, alternative values

## Development Workflow

### Working with PDFs
1. Place test PDFs in `/docs/` directory
2. Update `PDF_FILE_PATH` in `get_metadata.py` for single document testing
3. Use pikepdf for PDF manipulation - includes repair functionality for corrupted files

### API Configuration
- Set Gemini API key in `get_metadata.py` (line 480)
- API key is currently hardcoded - consider environment variable for production

### Testing Approach
- Use `test_metadata.py` for validation
- Compare extractions against `documents-info.xlsx` reference data
- Monitor confidence scores and evidence quality

## File Structure

```
/home/justus/Nextcloud/GHPL/
├── docs/                    # Health policy PDFs (4000+ documents)
├── get_metadata.py          # Main metadata extraction script
├── download_docs.py         # Document downloader
├── examine_excel.py         # Excel analysis utility
├── test_metadata.py         # Testing utilities
├── documents-info.xlsx      # Reference metadata
├── plan.md                  # Enhancement roadmap
├── requirements.txt         # Python dependencies
└── failed_downloads.txt     # Download error log
```

## Enhancement Plan

The `plan.md` file contains a comprehensive roadmap for improving the metadata extraction system, including:
- Hybrid approach using built-in PDF metadata
- Ground truth validation against Excel reference data
- Flexible schema with self-correction
- Confidence scoring enhancements

## Important Notes

- This is a research/analysis project focused on health policy document processing
- All PDF processing includes repair mechanisms for corrupted files
- The system prioritizes accuracy over speed with detailed confidence tracking
- Reference data in Excel may contain errors - track all deviations for quality assessment