# Global Health Policy Library (GHPL) - Metadata Extraction System

An AI-powered system for extracting and validating structured metadata from health policy PDFs using OpenAI's GPT-5-mini with advanced two-stage relevance assessment and metadata extraction.

## Features

- **Two-Stage Processing**: First assesses health policy relevance, then extracts detailed metadata
- **PDF Metadata Extraction**: Uses GPT-5-mini with flex processing for cost-effective extraction
- **Structured Output**: Pydantic-based schemas ensure consistent data format
- **Confidence Scoring**: Each extracted field includes confidence scores and evidence
- **Concurrent Batch Processing**: Multi-threaded processing with progress tracking
- **Real-time CSV Export**: Results are written immediately during processing
- **Cost Optimization**: Processes only first/last pages, uses flex pricing for 50% cost savings

## Key Components

### 1. Main Processing Script (`meta_ghpl_gpt5.py`)
- **Two-Stage Approach**: 
  - Stage 1: Health policy relevance assessment with boolean questions
  - Stage 2: Detailed metadata extraction using structured schemas
- Uses GPT-5-mini with flex processing for optimal cost/performance
- Extracts: Document Type, Health Focus, Title, Country, Year, Language, Authority, Governance Level
- Real-time progress tracking and CSV export
- Thread-safe concurrent processing with 80+ workers

### 2. PDF Processing
- Extracts first 10 pages + last 5 pages for efficiency
- Uses pikepdf for reliable PDF handling
- Automatic file cleanup and memory management
- Supports large-scale batch processing

### 3. Structured Data Models (`meta.py`)
- Pydantic schemas for consistent data validation
- Enum-based fields for standardized values
- Confidence scoring and evidence tracking
- GHPL-compliant metadata structure

### 4. Rate Limiting and Optimization (`utils.py`)
- OpenAI API rate limiting (500 RPM, 200K TPM)
- Exponential backoff retry logic with tenacity
- Cost tracking and performance metrics
- Flexible vs standard processing options

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

4. Set up OpenAI API key:
```bash
# Option 1: Environment variable
export OPENAI_API_KEY="your-api-key-here"

# Option 2: Create .env file in project root
echo "OPENAI_API_KEY=your-api-key-here" > .env

# Get API key from: https://platform.openai.com/
```

## Usage

### Single File Processing
```bash
# Process a single PDF with GPT-5-mini
python meta_ghpl_gpt5.py path/to/document.pdf

# Use standard processing (faster but 2x cost)
python meta_ghpl_gpt5.py document.pdf --no-flex
```

### Batch Processing
```bash
# Process all PDFs in a directory with 80 workers
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 80

# Process with limit for testing
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 4 --limit 10

# Resume interrupted batch processing (auto-detects existing CSV)
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 80
```

### Performance Optimization
```bash
# High-throughput processing for production
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 100

# Conservative processing to avoid rate limits
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 20
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

## Command-Line Reference (meta_ghpl_gpt5.py)

### Core Arguments
- `pdf_path`: Path to single PDF file to process (optional if using --docs-dir)
- `--docs-dir`: Directory containing PDF files for batch processing
- `--workers`: Number of concurrent workers (default: 80, optimized for 500 RPM limit)
- `--no-flex`: Disable flex processing (costs 2x more but may be faster)
- `--limit`: Maximum number of files to process (useful for testing)

### Output and Results
- Results are automatically saved to timestamped CSV files: `meta_gpt5_results_YYYYMMDD_HHMMSS.csv`
- CSV includes both relevance assessment and metadata extraction results
- Processing resumes automatically if existing CSV is found
- Real-time progress tracking and cost calculation

### Example Commands
```bash
# Test with small batch
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 4 --limit 5

# Production batch processing
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 80

# Single file with standard processing
python meta_ghpl_gpt5.py sample.pdf --no-flex

# Resume interrupted processing
python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 80
```

## Data Schema and Output Structure

### Two-Stage Assessment
**Stage 1: Relevance Assessment**
- `is_health_policy_related`: Boolean (from authoritative health source?)
- `fits_ghpl_categories`: Boolean (fits into 6 GHPL document types?)
- Confidence scores and explanations for each assessment

**Stage 2: Metadata Extraction** (only if both Stage 1 assessments are TRUE)

### Document Types (Enum)
- Policy
- Law  
- National Health Strategy
- National Control Plan
- Action Plan
- Health Guideline

### Health Focus Areas (Enum)
- Cancer
- Cardiovascular Health
- Non-Communicable Disease

### Issuing Authorities (Enum)
- Parliament
- Ministry
- Agency
- Foundation
- Association
- Society

### Governance Levels (Enum)
- National
- Regional 
- International

### CSV Output Columns
- Relevance assessment (Q1A, Q1B with confidence/explanations)
- Metadata fields (title, doc_type, health_topic, creator, year, country, language, governance_level)
- Quality metrics (overall_confidence, metadata_completeness)
- Processing statistics (processing_time, API cost, error messages)

## Requirements

- Python 3.8+
- OpenAI API key (get from [OpenAI Platform](https://platform.openai.com/))
- 8GB+ RAM recommended for processing large PDFs
- GPT-5-mini access (currently in limited preview)

## Complete Project Structure

```
/home/jay/GHPL/
├── 📁 docs/                        # Downloaded PDFs (2400+ files, may have URL parsing issues)
├── 📁 docs_correct/                # Curated PDFs with verified filenames (2452 files, 92.2% match rate)
├── 🐍 meta_ghpl_gpt5.py            # ⭐ MAIN SCRIPT: GPT-5-mini two-stage processing (1428 lines)
├── 🐍 meta.py                      # Pydantic schemas and data models for structured output
├── 🐍 utils.py                     # Rate limiting and utility functions
├── 🐍 cli.py                       # Legacy CLI with Gemini API (deprecated)
├── 🐍 get_metadata.py              # Legacy metadata extraction (deprecated)
├── 🐍 check_single_folder.py       # Filename matching analysis tool
├── 🐍 find_unmatched_files.py      # Find files not matching Excel entries
├── 🐍 download_with_correct_names.py # Smart downloader with proper URL parsing
├── 🐍 dedupe_and_convert.py        # Document deduplication and format conversion
├── 🐍 url_corrector.py             # URL correction and validation utilities
├── 🐍 examine_excel.py             # Excel structure and content analysis
├── 📊 documents-info.xlsx          # Ground truth metadata (2659 documents)
├── 📊 meta_gpt5_results_*.csv      # Output CSV files with timestamped results
├── 📋 requirements.txt             # Python dependencies
├── 📖 CLAUDE.md                    # Comprehensive development instructions
├── 📖 README.md                   # This file - project overview and usage
└── 🔧 .env                        # API keys (create manually: OPENAI_API_KEY=your-key)
```

## Key Python Scripts Documentation

### Core Processing Scripts

**`meta_ghpl_gpt5.py` (1428 lines) - ⭐ MAIN PROCESSING SCRIPT**
- **Two-Stage Processing Pipeline**: 
  - Stage 1: Health policy relevance assessment (boolean questions A & B)
  - Stage 2: Detailed metadata extraction with structured schemas
- **GPT-5-mini Integration**: Uses OpenAI Responses API with flex processing
- **Concurrent Processing**: Thread-safe batch processing with 80+ workers
- **Real-time CSV Export**: Results written immediately during processing
- **Cost Optimization**: Processes only first 10 + last 5 pages, uses flex pricing
- **Automatic Resume**: Detects existing CSV files and resumes processing
- **Performance Metrics**: Tracks processing time, API costs, and throughput

**`meta.py` - Structured Data Models**
- **Pydantic Schemas**: RelevanceAssessment and GHPLDocumentMetadata classes
- **Enum Validation**: Standardized values for document types, health topics, etc.
- **Confidence Scoring**: Built-in confidence calculation and completeness metrics
- **GHPL Compliance**: Follows Global Health Policy Library standards

**`utils.py` - Rate Limiting and Utilities**
- **OpenAI Rate Limiting**: 500 RPM, 200K TPM limits with intelligent backoff
- **Retry Logic**: Tenacity-based exponential backoff for API failures
- **Performance Tracking**: Token usage monitoring and cost calculation
- **Thread Safety**: Concurrent processing utilities

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

### OpenAI GPT-5-mini Limits
- Model: `gpt-5-mini` (currently in limited preview)
- Rate limiting: 500 requests per minute, 200K tokens per minute
- Built-in retry logic with exponential backoff using tenacity
- Flex processing: 50% cost reduction compared to standard processing

### Cost Optimization
- **Flex Processing**: Default mode for 2x cost savings (slower but much cheaper)
- **PDF Subset**: Only processes first 10 + last 5 pages to reduce token usage
- **Structured Output**: Uses Responses API for reliable JSON parsing
- **Batch Processing**: Concurrent workers optimize throughput

### Performance Recommendations
- Use `docs_correct/` folder for batch processing (92.2% filename matching)
- Start with `--limit 5 --workers 4` for testing
- Production: `--workers 80` for optimal throughput under rate limits
- Monitor CSV output for real-time progress and cost tracking
- Use `--no-flex` only if speed is more important than cost

### Scaling Guidelines
- For 500 RPM limit: Use up to 80-100 workers
- Processing rate: ~1-3 documents per minute per worker
- Cost: ~$0.01-0.05 per document with flex processing
- Throughput: 50-150 documents per minute with 80 workers

## Development

See `CLAUDE.md` for detailed development instructions and `plan.md` for the enhancement roadmap.

## Notice

Copyright (c) 2025 The Virchow Foundation and Contributors.
All rights reserved.

## Contributing

[Add contribution guidelines]

## Citation

If you use this system in your research, please cite:
```
[Add citation format]
```
