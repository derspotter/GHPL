# AGENT.md

## Commands
- **Test/Lint**: No pytest or lint commands found - validate manually with `python test_validation.py` or `python test_metadata.py`
- **Single file**: `python cli.py docs_correct/sample.pdf [--auto-resolve] [--interactive] [--with-search]`
- **Batch processing**: `python cli.py --batch --docs-dir docs_correct --workers 4 [--limit 100] [--with-search]`
- **Resume batch**: `python cli.py --batch --resume --workers 4`
- **Environment**: `source venv/bin/activate && pip install -r requirements.txt`

## Architecture
- **Main entry**: `cli.py` - CLI with batch processing, validation, search grounding
- **Core extraction**: `get_metadata.py` - Gemini API integration with Pydantic schemas  
- **Validation**: `ground_truth_validation.py` - compares against documents-info.xlsx (2659 docs)
- **Threading**: ThreadPoolExecutor for batch processing with atomic progress saves
- **Data**: PDFs in docs_correct/, ground truth in documents-info.xlsx, progress in batch_progress.json

## Code Style
- **Python 3.x** with type hints (`typing` module: Dict, List, Optional, etc.)
- **Imports**: Standard library first, third-party (pandas, google.genai, pydantic), then local
- **Error handling**: Comprehensive try/catch with logging, thread-safe operations with threading.Lock
- **Naming**: snake_case functions/variables, PascalCase classes, UPPER_CASE constants
- **Pydantic models**: Use Enum classes for constrained fields (DocType, Creator, HealthTopic, etc.)
- **Logging**: Use module-level logger, log to both file and console
- **API**: GOOGLE_API_KEY environment variable required for Gemini API access
