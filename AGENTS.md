# Repository Guidelines

## Project Structure & Module Organization
- `meta_ghpl_gpt5.py`: Main two‑stage processor (relevance + metadata).
- `meta.py`: Pydantic data models and enums.
- `utils.py`: Rate limiting, retries, and shared helpers.
- `docs/`, `docs_correct/`: Source PDFs (use `docs_correct/` for batches).
- `documents-info.xlsx`: Ground‑truth metadata.
- `test_*.py`: Scripted checks/utilities (run directly with Python).

## Build, Test, and Development Commands
- Create env and install deps:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
- Run a single file:
  - `python meta_ghpl_gpt5.py path/to/document.pdf`
- Run a batch (recommended):
  - `python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 80`
  - Testing: `python meta_ghpl_gpt5.py --docs-dir docs_correct --workers 4 --limit 5`
- Utilities (examples):
  - Filename check: `python check_single_folder.py docs_correct`
  - Excel insight: `python examine_excel.py`
  - Smart download: `python download_with_correct_names.py`

## Coding Style & Naming Conventions
- Follow PEP 8; use 4‑space indentation and snake_case for modules/functions.
- Prefer clear docstrings (triple‑quoted) and type hints where practical.
- Keep functions small and side‑effect aware; log rather than print in new code.

## Testing Guidelines
- Tests are Python scripts (not pytest). Run individually, e.g.:
  - `python test_ground_truth_matching.py`
  - `python test_csv_writing.py`
- For changes that affect matching or parsing, first validate with
  `check_single_folder.py` and a small `--limit` batch run.

## Commit & Pull Request Guidelines
- Commits: short, imperative summaries (e.g., "fix: URL parsing consistency").
- PRs must include:
  - Summary of changes and rationale.
  - Repro steps or example commands and expected output paths (e.g., CSV name).
  - Notes on performance impact (workers, rate limits) and any schema changes.
  - Updated docs when CLI/behavior changes (`README.md`, this file if relevant).

## Security & Configuration
- Configure `OPENAI_API_KEY` via environment or `.env` (see `README.md`).
- Do not commit secrets or large artifacts; respect `.gitignore`.
- Prefer `docs_correct/` to avoid filename mismatches and reduce failures.

