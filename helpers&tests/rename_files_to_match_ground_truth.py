#!/usr/bin/env python3
"""
Rename files in docs_correct folder to match ground truth Excel entries.
Uses the existing check_single_folder.py logic but adds renaming functionality.
"""

import pandas as pd
import os
from pathlib import Path
from urllib.parse import urlparse, unquote
import json
import shutil
from difflib import SequenceMatcher
import re

def get_filename_from_url(url):
    """Extract the expected filename from a URL"""
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    
    # Handle URL encoding
    filename = filename.replace('%20', ' ')
    filename = filename.replace('%28', '(')
    filename = filename.replace('%29', ')')
    
    return filename

def similarity(a, b):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(target_stem, available_stems, min_similarity=0.6):
    """Find the best matching stem from available stems"""
    best_match = None
    best_score = 0
    
    for stem in available_stems:
        score = similarity(target_stem, stem)
        if score > best_score and score >= min_similarity:
            best_score = score
            best_match = stem
    
    return best_match, best_score

def rename_files_to_match_ground_truth(excel_path='documents-info.xlsx', folder_path='docs_correct', dry_run=True):
    """
    Rename files in folder to match ground truth Excel entries.
    
    Args:
        excel_path: Path to the ground truth Excel file
        folder_path: Path to folder containing files to rename
        dry_run: If True, only show what would be renamed without actually doing it
    """
    
    print(f"\n{'='*60}")
    print(f"RENAMING FILES TO MATCH GROUND TRUTH")
    print(f"{'='*60}")
    print(f"Mode: {'DRY RUN' if dry_run else 'ACTUAL RENAMING'}")
    print(f"\n")
    
    # Load Excel file
    print(f"📊 Loading ground truth: {excel_path}")
    try:
        df = pd.read_excel(excel_path)
        print(f"   Total rows: {len(df)}")
    except Exception as e:
        print(f"❌ Error loading Excel: {e}")
        return
    
    # Get rows with valid URLs
    df_with_urls = df[df['public_file_url'].notna()].copy()
    print(f"   Rows with URLs: {len(df_with_urls)}")
    
    # Extract expected filenames from URLs
    expected_files = {}
    for idx, row in df_with_urls.iterrows():
        url = row['public_file_url']
        expected_filename = get_filename_from_url(url)
        doc_id = row.get('id', idx)
        
        expected_files[expected_filename] = {
            'url': url,
            'doc_id': doc_id,
            'row_index': idx,
            'title': row.get('title', 'Unknown Title')
        }
    
    # Check the folder
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        print(f"❌ {folder_path}/ does not exist or is not a directory")
        return
    
    actual_files = {f for f in os.listdir(folder_path) if f.endswith(('.pdf', '.docx', '.doc'))}
    print(f"📁 Files in {folder_path}/: {len(actual_files)}")
    
    # Create stem-based mappings
    expected_stems = {}  # stem -> expected_filename
    found_stems = {}     # stem -> found_filename
    
    for filename in expected_files.keys():
        stem = Path(filename).stem
        expected_stems[stem] = filename
    
    for filename in actual_files:
        stem = Path(filename).stem
        found_stems[stem] = filename
    
    # Find missing stems (files that should exist but don't match)
    missing_stems = expected_stems.keys() - found_stems.keys()
    extra_stems = found_stems.keys() - expected_stems.keys()
    
    print(f"\n📋 Analysis:")
    print(f"   Expected stems: {len(expected_stems)}")
    print(f"   Found stems: {len(found_stems)}")
    print(f"   Missing stems: {len(missing_stems)}")
    print(f"   Extra stems: {len(extra_stems)}")
    
    # Try to find potential matches using similarity
    rename_operations = []
    
    print(f"\n🔍 Looking for potential matches...")
    for missing_stem in missing_stems:
        expected_filename = expected_stems[missing_stem]
        
        # Try to find a similar stem in the extra stems
        best_match, score = find_best_match(missing_stem, extra_stems)
        
        if best_match and score > 0.7:  # High similarity threshold
            found_filename = found_stems[best_match]
            expected_info = expected_files[expected_filename]
            
            # Determine the correct extension (prefer .pdf for conversions)
            expected_ext = Path(expected_filename).suffix
            found_ext = Path(found_filename).suffix
            
            # Use PDF extension if it's available, otherwise keep the expected extension
            if found_ext == '.pdf':
                new_filename = missing_stem + '.pdf'
            else:
                new_filename = expected_filename
            
            rename_operations.append({
                'old_name': found_filename,
                'new_name': new_filename,
                'old_path': os.path.join(folder_path, found_filename),
                'new_path': os.path.join(folder_path, new_filename),
                'similarity': score,
                'doc_id': expected_info['doc_id'],
                'title': expected_info['title']
            })
    
    # Sort by similarity score (highest first)
    rename_operations.sort(key=lambda x: x['similarity'], reverse=True)
    
    print(f"\n{'='*50}")
    print(f"PROPOSED RENAME OPERATIONS ({len(rename_operations)})")
    print(f"{'='*50}")
    
    if not rename_operations:
        print("No potential matches found for renaming.")
        return
    
    # Show proposed operations
    for i, op in enumerate(rename_operations, 1):
        print(f"\n{i}. Similarity: {op['similarity']:.3f}")
        print(f"   Old: {op['old_name']}")
        print(f"   New: {op['new_name']}")
        print(f"   Doc ID: {op['doc_id']}")
        print(f"   Title: {op['title'][:80]}{'...' if len(op['title']) > 80 else ''}")
    
    if dry_run:
        print(f"\n⚠️  DRY RUN MODE - No files were actually renamed")
        print(f"   To perform actual renaming, run with dry_run=False")
        
        # Save the proposed operations
        operations_file = f'proposed_rename_operations_{Path(folder_path).name}.json'
        with open(operations_file, 'w') as f:
            json.dump(rename_operations, f, indent=2)
        print(f"   Proposed operations saved to: {operations_file}")
        return rename_operations
    
    # Perform actual renaming
    print(f"\n{'='*30}")
    print("PERFORMING RENAMES")
    print(f"{'='*30}")
    
    successful_renames = 0
    failed_renames = []
    
    for i, op in enumerate(rename_operations, 1):
        old_path = op['old_path']
        new_path = op['new_path']
        
        try:
            # Check if source file exists
            if not os.path.exists(old_path):
                failed_renames.append({**op, 'error': 'Source file not found'})
                continue
            
            # Check if destination already exists
            if os.path.exists(new_path):
                failed_renames.append({**op, 'error': 'Destination file already exists'})
                continue
            
            # Perform the rename
            shutil.move(old_path, new_path)
            print(f"✅ {i}/{len(rename_operations)}: {op['old_name']} → {op['new_name']}")
            successful_renames += 1
            
        except Exception as e:
            failed_renames.append({**op, 'error': str(e)})
            print(f"❌ {i}/{len(rename_operations)}: Failed - {e}")
    
    # Summary
    print(f"\n{'='*30}")
    print("RENAME SUMMARY")
    print(f"{'='*30}")
    print(f"✅ Successful renames: {successful_renames}")
    print(f"❌ Failed renames: {len(failed_renames)}")
    
    if failed_renames:
        print(f"\nFailed operations:")
        for fail in failed_renames:
            print(f"   • {fail['old_name']} → {fail['new_name']}: {fail['error']}")
    
    # Save results
    results = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'folder_path': folder_path,
        'total_operations': len(rename_operations),
        'successful_renames': successful_renames,
        'failed_renames': len(failed_renames),
        'operations': rename_operations,
        'failures': failed_renames
    }
    
    results_file = f'rename_results_{Path(folder_path).name}.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: {results_file}")
    
    return results

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Rename files to match ground truth Excel entries")
    parser.add_argument('folder', help='Folder containing files to rename')
    parser.add_argument('--excel', default='documents-info.xlsx', help='Path to ground truth Excel file')
    parser.add_argument('--execute', action='store_true', help='Actually perform renames (default is dry run)')
    
    args = parser.parse_args()
    
    # Run in dry run mode by default
    dry_run = not args.execute
    
    if dry_run:
        print("🔍 Running in DRY RUN mode - no files will be actually renamed")
        print("   Use --execute flag to perform actual renames")
    else:
        print("⚠️  EXECUTING mode - files WILL be renamed!")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            return
    
    rename_files_to_match_ground_truth(args.excel, args.folder, dry_run=dry_run)

if __name__ == "__main__":
    main()