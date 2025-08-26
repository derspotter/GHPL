#!/usr/bin/env python3
"""
Dedupe and Convert Script for GHPL Docs Folder
==============================================

This script performs three main operations on the docs folder:
1. Validates PDF files and moves corrupted/invalid ones to 'invalid/' subdirectory
2. Deduplicates files based on content hash (SHA-256)
3. Converts Word documents (.docx) to PDF using LibreOffice

Usage:
    python dedupe_and_convert.py [OPTIONS]

Options:
    --dry-run           Preview changes without making them
    --docs-path PATH    Path to docs folder (default: ./docs)
    --no-validate       Skip PDF validation
    --no-dedup          Skip deduplication
    --no-convert        Skip Word to PDF conversion
    --verbose           Enable verbose logging

PDF Validation:
    - Uses pikepdf library for reliable PDF validation (if available)
    - Falls back to basic header/structure checks if pikepdf is not installed
    - Invalid PDFs are moved to 'invalid/' subdirectory for manual inspection
"""

import os
import sys
import hashlib
import shutil
import subprocess
import argparse
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple

try:
    import pikepdf
    PIKEPDF_AVAILABLE = True
except ImportError:
    PIKEPDF_AVAILABLE = False

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure logging to both file and console
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cleanup.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 hash of file content."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, OSError) as e:
        logging.warning(f"Could not hash {file_path}: {e}")
        return ""

def find_duplicates(docs_path: Path) -> Dict[str, List[Path]]:
    """Find duplicate files based on content hash."""
    logger = logging.getLogger(__name__)
    logger.info("Scanning for duplicate files...")
    
    hash_to_files = defaultdict(list)
    total_files = 0
    
    for file_path in docs_path.rglob('*'):
        if file_path.is_file() and not file_path.name.startswith('.'):
            total_files += 1
            if total_files % 100 == 0:
                logger.info(f"Processed {total_files} files...")
            
            file_hash = calculate_file_hash(file_path)
            if file_hash:
                hash_to_files[file_hash].append(file_path)
    
    # Filter to only duplicates (more than one file per hash)
    duplicates = {h: files for h, files in hash_to_files.items() if len(files) > 1}
    
    logger.info(f"Found {len(duplicates)} sets of duplicate files")
    return duplicates

def deduplicate_files(docs_path: Path, dry_run: bool = False) -> Tuple[int, int]:
    """Remove duplicate files, keeping the first occurrence of each."""
    logger = logging.getLogger(__name__)
    duplicates = find_duplicates(docs_path)
    
    if not duplicates:
        logger.info("No duplicate files found")
        return 0, 0
    
    duplicates_dir = docs_path / 'duplicates'
    removed_count = 0
    duplicate_sets = 0
    
    for file_hash, files in duplicates.items():
        duplicate_sets += 1
        files.sort()  # Sort for consistent ordering
        keeper = files[0]
        to_remove = files[1:]
        
        logger.info(f"Duplicate set {duplicate_sets}: Keeping {keeper}")
        
        for duplicate in to_remove:
            removed_count += 1
            logger.info(f"  Moving duplicate to duplicates/: {duplicate}")
            
            if not dry_run:
                # Create duplicates directory if needed
                duplicates_dir.mkdir(exist_ok=True)
                
                # Move duplicate to duplicates folder
                relative_path = duplicate.relative_to(docs_path)
                target_path = duplicates_dir / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    shutil.move(str(duplicate), str(target_path))
                    logger.debug(f"  Successfully moved to: {target_path}")
                except (IOError, OSError) as e:
                    logger.error(f"Failed to move {duplicate}: {e}")
    
    return duplicate_sets, removed_count

def find_word_documents(docs_path: Path) -> List[Path]:
    """Find all Word documents (.docx) in the docs folder."""
    logger = logging.getLogger(__name__)
    word_docs = list(docs_path.rglob('*.docx'))
    logger.info(f"Found {len(word_docs)} Word documents")
    return word_docs

def convert_docx_to_pdf(docx_path: Path, dry_run: bool = False) -> bool:
    """Convert a single Word document to PDF using LibreOffice."""
    logger = logging.getLogger(__name__)
    
    # Generate PDF path
    pdf_path = docx_path.with_suffix('.pdf')
    
    # Skip if PDF already exists
    if pdf_path.exists():
        logger.debug(f"PDF already exists for {docx_path.name}")
        return True
    
    if dry_run:
        logger.info(f"Would convert: {docx_path} -> {pdf_path}")
        return True
    
    try:
        # Use LibreOffice headless mode to convert docx to pdf
        result = subprocess.run([
            'libreoffice', 
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(docx_path.parent),
            str(docx_path)
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and pdf_path.exists():
            logger.info(f"Converted: {docx_path.name} -> {pdf_path.name}")
            return True
        else:
            logger.error(f"LibreOffice failed for {docx_path}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout converting {docx_path}")
        return False
    except FileNotFoundError:
        logger.error("LibreOffice not found. Please install libreoffice.")
        return False
    except Exception as e:
        logger.error(f"Error converting {docx_path}: {e}")
        return False

def convert_word_documents(docs_path: Path, dry_run: bool = False) -> Tuple[int, int]:
    """Convert all Word documents to PDF and move originals."""
    logger = logging.getLogger(__name__)
    word_docs = find_word_documents(docs_path)
    
    if not word_docs:
        logger.info("No Word documents found to convert")
        return 0, 0
    
    converted_dir = docs_path / 'converted_originals'
    converted_count = 0
    failed_count = 0
    
    for docx_path in word_docs:
        logger.debug(f"Processing: {docx_path}")
        
        if convert_docx_to_pdf(docx_path, dry_run):
            converted_count += 1
            
            if not dry_run:
                # Move original .docx to converted_originals folder
                converted_dir.mkdir(exist_ok=True)
                relative_path = docx_path.relative_to(docs_path)
                target_path = converted_dir / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    shutil.move(str(docx_path), str(target_path))
                    logger.debug(f"Moved original to: {target_path}")
                except (IOError, OSError) as e:
                    logger.error(f"Failed to move {docx_path}: {e}")
        else:
            failed_count += 1
    
    return converted_count, failed_count

def check_dependencies() -> bool:
    """Check if required dependencies are available."""
    logger = logging.getLogger(__name__)
    
    try:
        # Check LibreOffice
        result = subprocess.run(['libreoffice', '--version'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("LibreOffice is not available")
            return False
        version_line = result.stdout.strip().split('\n')[0]
        logger.info(f"LibreOffice found: {version_line}")
        return True
        
    except FileNotFoundError:
        logger.error("LibreOffice not found. Please install libreoffice.")
        return False

def is_valid_pdf(file_path: Path) -> bool:
    """Check if a file is a valid PDF document."""
    if not file_path.suffix.lower() == '.pdf':
        return True  # Not a PDF, so it's "valid" for our purposes
    
    try:
        # Method 1: Try with pikepdf (most reliable)
        if PIKEPDF_AVAILABLE:
            try:
                with pikepdf.open(file_path):
                    return True
            except (pikepdf.PdfError, pikepdf.PasswordError):
                return False
        
        # Method 2: Fallback - check PDF header and basic structure
        with open(file_path, 'rb') as f:
            # Check PDF header
            header = f.read(8)
            if not header.startswith(b'%PDF-'):
                return False
            
            # Try to find trailer (basic structural check)
            f.seek(-1024, 2)  # Go to last 1KB
            footer = f.read()
            if b'trailer' not in footer and b'%%EOF' not in footer:
                return False
                
        return True
        
    except (IOError, OSError) as e:
        logging.warning(f"Could not validate PDF {file_path}: {e}")
        return False

def validate_pdfs(docs_path: Path, dry_run: bool = False) -> Tuple[int, int, int]:
    """Validate all PDF files and move invalid ones to 'invalid' subdirectory."""
    logger = logging.getLogger(__name__)
    logger.info("Validating PDF files...")
    
    pdf_files = list(docs_path.rglob('*.pdf'))
    if not pdf_files:
        logger.info("No PDF files found to validate")
        return 0, 0, 0
    
    logger.info(f"Found {len(pdf_files)} PDF files to validate")
    
    invalid_dir = docs_path / 'invalid'
    valid_count = 0
    invalid_count = 0
    error_count = 0
    
    for pdf_path in pdf_files:
        logger.debug(f"Validating: {pdf_path}")
        
        try:
            if is_valid_pdf(pdf_path):
                valid_count += 1
                logger.debug(f"✓ Valid PDF: {pdf_path.name}")
            else:
                invalid_count += 1
                logger.warning(f"✗ Invalid PDF: {pdf_path}")
                
                if not dry_run:
                    # Move invalid PDF to invalid subdirectory
                    invalid_dir.mkdir(exist_ok=True)
                    relative_path = pdf_path.relative_to(docs_path)
                    target_path = invalid_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        shutil.move(str(pdf_path), str(target_path))
                        logger.info(f"Moved invalid PDF to invalid/: {relative_path}")
                    except (IOError, OSError) as e:
                        logger.error(f"Failed to move invalid PDF {pdf_path}: {e}")
                        error_count += 1
                else:
                    logger.info(f"Would move invalid PDF to invalid/: {pdf_path}")
                    
        except Exception as e:
            error_count += 1
            logger.error(f"Error validating PDF {pdf_path}: {e}")
    
    return valid_count, invalid_count, error_count

def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate docs folder, convert Word documents to PDF, and validate PDFs"
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview changes without making them'
    )
    parser.add_argument(
        '--docs-path', type=Path, default=Path('./docs'),
        help='Path to docs folder (default: ./docs)'
    )
    parser.add_argument(
        '--no-dedup', action='store_true',
        help='Skip deduplication'
    )
    parser.add_argument(
        '--no-convert', action='store_true',
        help='Skip Word to PDF conversion'
    )
    parser.add_argument(
        '--no-validate', action='store_true',
        help='Skip PDF validation'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    # Validate docs path
    if not args.docs_path.exists():
        logger.error(f"Docs path does not exist: {args.docs_path}")
        sys.exit(1)
    
    if not args.docs_path.is_dir():
        logger.error(f"Docs path is not a directory: {args.docs_path}")
        sys.exit(1)
    
    logger.info(f"Starting cleanup of: {args.docs_path}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    # Check dependencies for conversion
    if not args.no_convert:
        if not check_dependencies():
            logger.error("Missing required dependencies for conversion")
            sys.exit(1)
    
    try:
        # PDF validation (run first to catch corrupted files early)
        valid_pdfs = invalid_pdfs = pdf_errors = 0
        if not args.no_validate:
            logger.info("=== PDF VALIDATION PHASE ===")
            if not PIKEPDF_AVAILABLE:
                logger.warning("pikepdf not available - using basic PDF validation")
            valid_pdfs, invalid_pdfs, pdf_errors = validate_pdfs(args.docs_path, args.dry_run)
        
        # Deduplication
        duplicate_sets = removed_files = 0
        if not args.no_dedup:
            logger.info("=== DEDUPLICATION PHASE ===")
            duplicate_sets, removed_files = deduplicate_files(args.docs_path, args.dry_run)
        
        # Word to PDF conversion
        converted_files = failed_conversions = 0
        if not args.no_convert:
            logger.info("=== CONVERSION PHASE ===")
            converted_files, failed_conversions = convert_word_documents(args.docs_path, args.dry_run)
        
        # Summary
        logger.info("=== SUMMARY ===")
        logger.info(f"Valid PDFs: {valid_pdfs}")
        logger.info(f"Invalid PDFs moved to invalid/: {invalid_pdfs}")
        logger.info(f"PDF validation errors: {pdf_errors}")
        logger.info(f"Duplicate sets found: {duplicate_sets}")
        logger.info(f"Duplicate files moved to duplicates/: {removed_files}")
        logger.info(f"Word documents converted: {converted_files}")
        logger.info(f"Conversion failures: {failed_conversions}")
        
        if args.dry_run:
            logger.info("Run without --dry-run to apply changes")
        else:
            if invalid_pdfs > 0:
                logger.info(f"Invalid PDFs safely preserved in: {args.docs_path}/invalid/")
            if removed_files > 0:
                logger.info(f"Duplicate files safely preserved in: {args.docs_path}/duplicates/")
            if converted_files > 0:
                logger.info(f"Original Word documents preserved in: {args.docs_path}/converted_originals/")
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()