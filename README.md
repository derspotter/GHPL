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
export GEMINI_API_KEY="your-api-key-here"
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

### Download Documents
```bash
# Download health policy documents from URLs in Excel
python download_docs.py

# Smart download with resume capability
python download_docs_smart.py
```

### Examine Reference Data
```bash
python examine_excel.py
```

## Command-Line Options

- `--api-key`: Gemini API key (defaults to GEMINI_API_KEY env var)
- `--excel`: Path to reference Excel file (default: documents-info.xlsx)
- `--auto-resolve`: Enable automatic search resolution of conflicts
- `--interactive`: Enable interactive resolution mode
- `--search-threshold`: Minimum confidence for auto-resolution (default: 0.8)
- `--export-deviations`: Export deviations to Excel file
- `--stats-only`: Only show ground truth statistics

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

## Project Structure

```
ghpl/
├── cli.py                    # Main CLI with search grounding
├── get_metadata.py           # Core metadata extraction
├── ground_truth_validation.py # Validation functions
├── download_docs.py          # Document downloader
├── examine_excel.py          # Excel analysis utility
├── test_validation.py        # Testing functions
├── requirements.txt          # Python dependencies
├── documents-info.xlsx       # Reference metadata (2659 docs)
├── CLAUDE.md                # Development instructions
├── plan.md                  # Enhancement roadmap
└── docs/                    # Downloaded PDFs (gitignored)
```

## API Rate Limits

- Gemini API: Follow Google's rate limits
- Search Grounding: Limited to 1.5k searches/day on tier 1
- Optimized to use ONE search per document

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