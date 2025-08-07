# Global Health Policy Library (GHPL) - Metadata Extraction System

An AI-powered system for extracting and validating structured metadata from health policy documents using Google's Gemini API with advanced search grounding capabilities.

## Features

- **PDF Metadata Extraction**: Extracts structured metadata from health policy PDFs using Gemini 2.5 Pro
- **Ground Truth Validation**: Compares extracted metadata against reference data
- **Search Grounding**: Resolves metadata conflicts using Google Search to find authoritative sources
- **Interactive Resolution**: User-friendly interface for resolving discrepancies
- **Confidence Scoring**: Each extracted field includes confidence scores and evidence
- **Batch Processing**: Process multiple documents with comprehensive tracking

## Key Components

### 1. Metadata Extraction (`get_metadata.py`)
- Uses Gemini 2.5 Pro for intelligent document analysis
- Extracts: Document Type, Health Topic, Creator, Year, Country, Language, Title
- Provides confidence scores and evidence for each field
- Handles corrupted PDFs with automatic repair

### 2. Validation System (`ground_truth_validation.py`)
- Compares extractions against reference dataset (2659 documents)
- Tracks all deviations for quality assessment
- Calculates accuracy metrics and confidence scores

### 3. Search Grounding (`cli.py`)
- Automatically resolves metadata conflicts using Google Search
- Finds official sources to validate document information
- Single search per document (optimized for API limits)
- Confidence-based auto-resolution

### 4. Interactive CLI (`cli.py`)
- User-friendly command-line interface
- Interactive or automated conflict resolution
- Export capabilities for analysis
- Comprehensive reporting

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ghpl.git
cd ghpl
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up Gemini API key:
```bash
# Option 1: Environment variable
export GOOGLE_API_KEY="your-api-key-here"

# Option 2: Create .env file in project root
echo "GOOGLE_API_KEY=your-api-key-here" > .env

# Get API key from: https://aistudio.google.com/
```

## Usage

### Basic Extraction with Validation
```bash
python cli.py path/to/document.pdf
```

### With Search Grounding (Auto-resolve conflicts)
```bash
python cli.py document.pdf --auto-resolve
```

### Interactive Resolution
```bash
python cli.py document.pdf --interactive
```

### Export Analysis
```bash
python cli.py document.pdf --export-deviations analysis.xlsx
```

### Document Management
```bash
# Download health policy documents from URLs in Excel
python download_docs.py

# Smart download with correct filenames and resume capability
python download_with_correct_names.py

# URL correction and validation utility
python url_corrector.py

# Deduplicate and convert document formats
python dedupe_and_convert.py
```

### Analysis and Validation Tools
```bash
# Examine reference Excel structure and metadata
python examine_excel.py

# CRITICAL: Check filename matching between folder and Excel (run before batch processing)
python check_single_folder.py docs_correct
python check_single_folder.py docs --excel documents-info.xlsx

# Find files that don't match any Excel entry
python find_unmatched_files.py

# Test filename matching logic consistency
python check_filename_matching.py

# Test ground truth validation system
python test_ground_truth_matching.py

# Single document metadata extraction (for testing)
python get_metadata.py path/to/sample.pdf
```

## Complete Command-Line Reference

### Single File Processing Options
- `pdf_path`: Path to PDF file to process
- `--excel`: Path to reference Excel file (default: documents-info.xlsx)
- `--api-key`: Gemini API key (defaults to GOOGLE_API_KEY env var)
- `--export-deviations`: Export deviations analysis to Excel file
- `--stats-only`: Only show ground truth validation statistics
- `--verbose`: Enable detailed output for debugging

### Resolution and Processing Modes
- `--interactive`: Enable interactive resolution of metadata discrepancies
- `--auto-reference`: Automatically use reference values for all conflicts
- `--auto-extracted`: Automatically use extracted values for all conflicts
- `--auto-resolve`: Enable automatic search resolution of conflicts
- `--with-search`: Use search grounding with interactive mode
- `--search-threshold`: Minimum confidence for auto-resolution (default: 0.8)

### Export and Logging Options
- `--export-corrections`: Export user corrections to Excel file
- `--export-unresolved`: Export unresolved items to Excel file
- `--log-decisions`: Log all user decisions to JSON file

### Batch Processing Options
- `--batch`: Enable batch processing mode
- `--docs-dir`: Directory containing PDF files (default: docs)
- `--workers`: Number of concurrent workers (default: 4)
- `--batch-size`: Process files in batches of this size (default: 50)
- `--resume`: Resume batch processing from last checkpoint
- `--retry-failed`: Retry only failed files from previous batch
- `--progress-file`: Progress tracking file (default: batch_progress.json)
- `--limit`: Limit number of files to process (useful for testing)
- `--max-retries`: Maximum retries for failed operations (default: 3)

### Batch Export Options
- `--batch-results`: Export all batch results to Excel file
- `--batch-deviations`: Export batch deviations to Excel file
- `--batch-ground-truth`: Export updated ground truth to Excel file

## Data Schema

### Document Types
- Policy
- Law
- National Health Strategy
- National Control Plan
- Action Plan
- Health Guideline

### Health Topics
- Cancer
- Cardiovascular Health
- Non-Communicable Disease

### Creators
- Parliament
- Ministry
- Agency
- Foundation
- Association
- Society

## Requirements

- Python 3.8+
- Gemini API key (get from [Google AI Studio](https://aistudio.google.com/))
- 8GB+ RAM recommended for processing large PDFs

## Complete Project Structure

```
/home/jay/GHPL/
├── 📁 docs/                        # Downloaded PDFs (2400+ files, may have URL parsing issues)
├── 📁 docs_correct/                # Curated PDFs with verified filenames (2452 files, 92.2% match rate)
├── 🐍 cli.py                       # Main CLI application (2299 lines)
├── 🐍 get_metadata.py              # Core metadata extraction using Gemini 2.5 Pro
├── 🐍 ground_truth_validation.py   # Ground truth comparison and validation
├── 🐍 check_single_folder.py       # Filename matching analysis tool
├── 🐍 find_unmatched_files.py      # Find files not matching Excel entries
├── 🐍 download_with_correct_names.py # Smart downloader with proper URL parsing
├── 🐍 dedupe_and_convert.py        # Document deduplication and format conversion
├── 🐍 url_corrector.py             # URL correction and validation utilities
├── 🐍 examine_excel.py             # Excel structure and content analysis
├── 🐍 test_ground_truth_matching.py # Ground truth validation testing
├── 🐍 check_filename_matching.py   # Filename matching logic validation
├── 📊 documents-info.xlsx          # Ground truth metadata (2659 documents)
├── 🗂️ batch_progress.json          # Batch processing state (resumable)
├── 🗂️ search_quota.json           # Daily search API quota tracking (1.5k/day)
├── 🗂️ folder_analysis_*.json       # Folder analysis reports from check_single_folder.py
├── 📋 requirements.txt             # Python dependencies
├── 📖 CLAUDE.md                    # Comprehensive development instructions
├── 📖 plan.md                      # Feature roadmap and enhancement plans
├── 📖 USAGE_DEDUPE.md             # Document deduplication usage guide
├── 📖 README.md                   # This file - project overview and usage
└── 🔧 .env                        # API keys (create manually: GOOGLE_API_KEY=your-key)
```

## Key Python Scripts Documentation

### Core Processing Scripts

**`cli.py` (2299 lines) - Main CLI Application**
- Comprehensive command-line interface with 25+ arguments
- Single file and batch processing modes
- Interactive and automatic conflict resolution
- Search grounding with Google Search integration
- Thread-safe batch processing with progress tracking
- Excel export capabilities for results and analysis
- Advanced error categorization and retry logic
- Rate limiting and quota management

**`get_metadata.py` - Metadata Extraction Engine**
- Gemini 2.5 Pro integration with structured output (Pydantic schemas)
- Extracts: document type, health topic, creator, level, title, country, language, year
- Confidence scoring and evidence tracking for each field
- PDF page optimization (first 3 + last 2 pages only)
- Automatic PDF repair with qpdf for corrupted files
- Comprehensive error handling and logging

**`ground_truth_validation.py` - Validation System**
- Loads and compares against reference data (documents-info.xlsx)
- Tracks ALL deviations for quality assessment
- Adjusts confidence scores based on ground truth matches
- Supports different validation modes and thresholds
- Generates detailed comparison reports

### Analysis and Quality Assurance

**`check_single_folder.py` - Filename Matching Analysis**
- **CRITICAL TOOL**: Verifies filename matching between folders and Excel
- Shows perfect matches, stem-based matches, and missing files
- Detects format conversions (DOCX → PDF)
- Reports match rates and identifies problematic files
- Generates JSON reports for further analysis
- **Usage**: Always run before batch processing to ensure compatibility

**`find_unmatched_files.py` - Unmatched File Detection**
- Finds files in folders that don't correspond to any Excel entry
- Uses same URL parsing logic as main system
- Suggests similar filenames for potential matches
- Helps identify download or filename issues

**`examine_excel.py` - Excel Analysis Utility**
- Analyzes structure and content of documents-info.xlsx
- Shows data distribution, missing values, and statistics
- Validates URL formats and accessibility
- Essential for understanding reference data quality

### Document Management

**`download_with_correct_names.py` - Smart Downloader**
- Downloads PDFs from URLs in Excel with proper filename parsing
- Uses consistent URL decoding (urlparse + unquote)
- Resume capability for interrupted downloads
- Progress tracking and error handling
- Ensures filename compatibility with processing pipeline

**`dedupe_and_convert.py` - Deduplication System**
- Document deduplication based on content similarity
- Format conversion (DOCX to PDF)
- Handles duplicate detection and removal
- See USAGE_DEDUPE.md for detailed usage instructions

**`url_corrector.py` - URL Validation and Correction**
- Validates and corrects URLs in Excel data
- Handles common URL formatting issues
- Updates Excel with corrected URLs
- Essential for maintaining download pipeline integrity

### Testing and Validation

**`test_ground_truth_matching.py` - Validation Testing**
- Tests ground truth validation logic
- Verifies comparison algorithms work correctly
- Ensures confidence scoring accuracy
- Unit tests for validation components

**`check_filename_matching.py` - Filename Logic Testing**
- Tests URL-to-filename parsing consistency
- Validates filename matching algorithms
- Ensures all scripts use consistent parsing logic
- Critical for preventing filename mismatches

## API Rate Limits and Optimization

### Gemini API Limits
- Model: `gemini-2.5-pro`
- Rate limiting: Built-in exponential backoff and retry logic
- Concurrent workers: Automatically optimized based on rate limits
- Token optimization: Only first 3 + last 2 pages sent to reduce costs

### Search Grounding Limits
- Daily quota: 1.5k searches/day on tier 1 billing
- Optimization: ONE comprehensive search per document (not per field)
- Quota tracking: Automatic daily reset in `search_quota.json`
- Fallback: Interactive resolution when quota exceeded

### Performance Recommendations
- Use `docs_correct/` folder for batch processing (100% filename matching)
- Start with `--limit 10 --verbose` for testing
- Use `--workers 2-4` to avoid rate limiting
- Monitor `cli_errors.log` for API issues

## Development

See `CLAUDE.md` for detailed development instructions and `plan.md` for the enhancement roadmap.

## License

[Add appropriate license]

## Contributing

[Add contribution guidelines]

## Citation

If you use this system in your research, please cite:
```
[Add citation format]
```