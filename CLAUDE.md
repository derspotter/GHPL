# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Global Health Policy Library (GHPL) - An AI-powered system for extracting and validating structured metadata from health policy PDFs using Google's Gemini API with advanced search grounding capabilities. The system processes thousands of health policy documents, validates against ground truth data, and uses Google Search to resolve metadata conflicts.

## Key Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set API key (required)
export GOOGLE_API_KEY="your-api-key-here"
# Or create .env file with: GOOGLE_API_KEY=your-api-key
```

### Main CLI Operations

**Single File Processing:**
```bash
# Basic extraction with ground truth validation
python cli.py docs_correct/sample.pdf

# With search grounding (auto-resolves conflicts)
python cli.py docs_correct/sample.pdf --auto-resolve

# Interactive resolution mode
python cli.py docs_correct/sample.pdf --interactive

# Combined interactive with search grounding
python cli.py docs_correct/sample.pdf --interactive --with-search

# Export deviations analysis
python cli.py docs_correct/sample.pdf --export-deviations deviations.xlsx

# Show only ground truth statistics
python cli.py docs_correct/sample.pdf --stats-only

# Custom search confidence threshold
python cli.py docs_correct/sample.pdf --auto-resolve --search-threshold 0.9
```

**Batch Processing:**
```bash
# Basic batch processing (use docs_correct for best results)
python cli.py --batch --docs-dir docs_correct --workers 4

# Batch with search grounding and export
python cli.py --batch --docs-dir docs_correct --workers 4 --limit 100 --with-search \
  --batch-results results.xlsx --batch-deviations deviations.xlsx

# Resume interrupted batch processing
python cli.py --batch --resume --workers 4 --with-search

# Retry only failed files from previous batch
python cli.py --batch --retry-failed --workers 2

# Test batch with small limit and verbose output
python cli.py --batch --docs-dir docs_correct --limit 10 --verbose --workers 2

# Export updated ground truth after batch processing
python cli.py --batch --workers 4 --batch-ground-truth updated_ground_truth.xlsx
```

**Advanced Options:**
```bash
# Custom Excel file and progress tracking
python cli.py --batch --excel custom-data.xlsx --progress-file custom_progress.json

# Rate limiting control for high-volume processing
python cli.py --batch --workers 8 --max-retries 5

# Export user corrections and decisions
python cli.py sample.pdf --interactive --export-corrections corrections.xlsx \
  --log-decisions decisions.json
```

### Document Management
```bash
# Download documents from Excel URLs
python download_docs.py

# Smart download with resume capability
python download_docs_smart.py

# Resume interrupted downloads  
python download_docs_resume.py

# Analyze Excel structure
python examine_excel.py

# Test single document extraction
python get_metadata.py
```

### Testing and Validation
```bash
# Test validation system
python test_validation.py

# Test metadata extraction
python test_metadata.py

# Check specific document against ground truth
python check_specific_document.py

# Analyze filename matching for any folder against ground truth
python check_single_folder.py docs_correct
python check_single_folder.py docs --excel documents-info.xlsx
```

## Architecture

### Core Components

**1. Metadata Extraction Pipeline (`get_metadata.py`)**
- Uses pikepdf to extract first 3 + last 2 pages for efficiency
- Sends to Gemini 2.5 Pro with structured output schema (Pydantic)
- Includes automatic PDF repair via qpdf for corrupted files
- Returns confidence scores and evidence for each field

**2. Ground Truth Validation (`ground_truth_validation.py`)**
- Loads reference data from `documents-info.xlsx` (2659 documents)
- Compares extracted metadata against reference
- Tracks ALL deviations for quality assessment
- Adjusts confidence scores based on matches/discrepancies

**3. Search Grounding Resolution (`cli.py:resolve_conflicts_with_search`)**
- Uses Google Search via Gemini to resolve metadata conflicts
- Single comprehensive search per document (API limit optimization)
- Auto-resolves conflicts with >0.8 confidence
- Provides source URLs and reasoning for decisions

**4. Batch Processing System (`cli.py:batch_process_pdfs`)**
- ThreadPoolExecutor for concurrent processing
- Progress tracking with resume capability (`batch_progress.json`)
- Thread-safe result collection
- Excel export for results and deviations

**5. Interactive Resolution (`cli.py:handle_discrepancies_interactively`)**
- User-friendly CLI prompts for conflict resolution
- Batch handling options for multiple discrepancies
- Stores corrections separately from original data
- Builds improved reference dataset

### Data Flow

```
PDF → Extract Pages → Gemini API → Structured Metadata
                                          ↓
                                  Ground Truth Validation
                                          ↓
                                  Conflicts Detected?
                                    ↙           ↘
                                  No            Yes
                                  ↓              ↓
                              Complete    Search Grounding
                                              ↓
                                      Auto-resolved?
                                        ↙         ↘
                                      Yes         No
                                       ↓          ↓
                                   Complete  Interactive
```

### Key Data Structures

**DocumentMetadata Schema:**
- `doc_type`: Policy, Law, National Health Strategy, etc. (enum)
- `health_topic`: Cancer, Cardiovascular Health, Non-Communicable Disease (enum)
- `creator`: Parliament, Ministry, Agency, Foundation, etc. (enum)
- `level`: National, Regional (enum)
- `title`, `country`, `language`: Free text fields
- `year`: Integer field
- Each field includes: value, confidence (0-1), evidence, source_page, alternatives

**BatchProgress:**
- Tracks: total_files, completed, failed, pending
- Saves to `batch_progress.json` after each file
- Enables resume from interruption

**Search Resolution:**
- Single search per document covering all conflicts
- Returns: resolved_value, confidence, recommendation, reasoning, sources
- Auto-resolves if confidence >= 0.8

### API Configuration

**Gemini API:**
- Model: `gemini-2.5-pro`
- Environment variable: `GOOGLE_API_KEY` or `GEMINI_API_KEY`
- Rate limits: Follow Google's limits
- Search grounding: 1.5k searches/day on tier 1

**API Key Loading Priority:**
1. Command line argument `--api-key`
2. Environment variable `GOOGLE_API_KEY`
3. Environment variable `GEMINI_API_KEY`
4. `.env` file

### File Structure

```
/home/jay/GHPL/
├── docs/                        # Health policy PDFs (2400+ files)
├── docs_correct/                # Curated PDFs with verified filenames (2452 files)
├── cli.py                       # Main CLI with all features
├── get_metadata.py              # Core extraction logic
├── ground_truth_validation.py   # Validation functions
├── download_docs_resume.py     # Smart downloader
├── check_single_folder.py      # Filename matching analysis tool
├── documents-info.xlsx         # Ground truth data (2659 docs)
├── batch_progress.json         # Batch processing state
├── requirements.txt            # Dependencies
└── .env                        # API key (create this)
```

### Critical Implementation Details

**Thread Safety:**
- BatchResults class uses threading.Lock for safe concurrent writes
- Progress saves use atomic operations
- Each thread gets independent Gemini client

**Error Recovery:**
- PDF repair with qpdf fallback
- Search grounding initialization with empty dict (not None)
- Safe list operations with membership checks
- Comprehensive exception handling

**Performance Optimizations:**
- Only first 3 + last 2 pages sent to Gemini
- Single search query per document
- Concurrent processing with configurable workers
- Ground truth loaded once, shared across threads

**URL Parsing Consistency:**
- All scripts now use consistent URL-to-filename parsing with proper URL decoding
- Handles encoded characters: %20 → space, %28 → (, %29 → )
- Uses `urlparse()` and `unquote()` instead of treating URLs as file paths
- Ensures filename matching works correctly for files like `Hck1ocv.@www.surgeon.fullrpt.pdf`

**State Management:**
- Progress saved after EVERY file completion
- Pending list rebuilt on resume to match actual files
- Failed files tracked with full error details
- Completion rate calculated dynamically

### Common Issues and Solutions

**"File name too long" error:**
- Solution: Scan docs/ directory for actual files instead of using Excel titles

**AttributeError: 'NoneType' object has no attribute 'get':**
- Solution: Initialize search_resolution_results as empty dict, not None

**"list.remove(x): x not in list" error:**
- Solution: Check membership before removal, rebuild pending list on resume

**API key not found:**
- Solution: Check both GOOGLE_API_KEY and GEMINI_API_KEY environment variables

**Files not matching Excel entries during CLI processing:**
- Solution: Use `check_single_folder.py` to analyze filename matching
- Check URL parsing consistency - ensure all scripts use `get_filename_from_url()`
- The tool shows exact match rates and identifies problematic files

### Development Workflow

**Adding New Features:**
1. Check existing patterns in `cli.py` for similar functionality
2. Follow Pydantic models in `get_metadata.py` for data structures
3. Use existing confidence scoring patterns
4. Add command-line arguments following existing convention

**Testing Changes:**
1. Test with single file first: `python cli.py docs/test.pdf`
2. Test batch with small limit: `python cli.py --batch --limit 3`
3. Test resume capability by interrupting and restarting
4. Verify Excel exports contain expected data

**Debugging:**
- Use `--verbose` flag for detailed output
- Check `batch_progress.json` for processing state
- Review Excel exports for patterns in discrepancies
- Monitor thread names in verbose output for concurrent issues