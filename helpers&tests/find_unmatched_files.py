#!/usr/bin/env python3
"""
Find files in docs_correct that don't actually match any Excel entry.
This accounts for the URL parsing logic used in the system.
"""

import pandas as pd
import os
from pathlib import Path
from urllib.parse import urlparse, unquote

def get_filename_from_url(url):
    """Extract the expected filename from a URL - same logic as check_single_folder.py"""
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    
    # Handle URL encoding
    filename = filename.replace('%20', ' ')
    filename = filename.replace('%28', '(')
    filename = filename.replace('%29', ')')
    
    return filename

def find_unmatched_files(excel_path='documents-info.xlsx', folder_path='docs_correct'):
    """
    Find files in folder that don't match any Excel entry.
    """
    
    print(f"🔍 Finding unmatched files in {folder_path}")
    print(f"📊 Loading Excel: {excel_path}")
    
    # Load Excel file
    try:
        df = pd.read_excel(excel_path)
        df_with_urls = df[df['public_file_url'].notna()].copy()
        print(f"   Rows with URLs: {len(df_with_urls)}")
    except Exception as e:
        print(f"❌ Error loading Excel: {e}")
        return
    
    # Build set of expected stems from URLs
    expected_stems = set()
    url_to_stem = {}  # For debugging
    
    for idx, row in df_with_urls.iterrows():
        url = row['public_file_url']
        expected_filename = get_filename_from_url(url)
        stem = Path(expected_filename).stem
        expected_stems.add(stem)
        url_to_stem[url] = stem
    
    print(f"   Expected unique stems: {len(expected_stems)}")
    
    # Get actual files in folder
    if not os.path.exists(folder_path):
        print(f"❌ {folder_path} does not exist")
        return
    
    actual_files = [f for f in os.listdir(folder_path) if f.endswith(('.pdf', '.docx', '.doc'))]
    actual_stems = {Path(f).stem for f in actual_files}
    
    print(f"📁 Files in {folder_path}: {len(actual_files)}")
    print(f"   Unique stems: {len(actual_stems)}")
    
    # Find unmatched files
    unmatched_stems = actual_stems - expected_stems
    
    print(f"\n{'='*50}")
    print(f"UNMATCHED FILES: {len(unmatched_stems)}")
    print(f"{'='*50}")
    
    if unmatched_stems:
        print(f"\n❌ Files in {folder_path} that don't match any Excel entry:")
        
        unmatched_files = []
        for filename in actual_files:
            stem = Path(filename).stem
            if stem in unmatched_stems:
                unmatched_files.append(filename)
        
        for i, filename in enumerate(sorted(unmatched_files), 1):
            print(f"   {i:2d}. {filename}")
            
        return unmatched_files
    else:
        print("✅ All files match Excel entries!")
        return []

def search_for_similar_stems(problem_stem, expected_stems, min_similarity=0.6):
    """Find similar stems in the expected set"""
    from difflib import SequenceMatcher
    
    matches = []
    for stem in expected_stems:
        similarity = SequenceMatcher(None, problem_stem.lower(), stem.lower()).ratio()
        if similarity >= min_similarity:
            matches.append((stem, similarity))
    
    return sorted(matches, key=lambda x: x[1], reverse=True)

def main():
    unmatched = find_unmatched_files()
    
    if unmatched:
        print(f"\n{'='*50}")
        print("SUGGESTED ACTIONS")
        print(f"{'='*50}")
        print("These files should be:")
        print("1. Removed if they're incorrect downloads")
        print("2. Renamed if they correspond to Excel entries with different names")
        print("3. Investigated to understand why they don't match")
        
        # For each unmatched file, try to find potential matches
        print(f"\n🔍 Looking for potential matches...")
        
        # Load expected stems for similarity matching
        df = pd.read_excel('documents-info.xlsx')
        df_with_urls = df[df['public_file_url'].notna()].copy()
        expected_stems = set()
        
        for idx, row in df_with_urls.iterrows():
            url = row['public_file_url']
            expected_filename = get_filename_from_url(url)
            stem = Path(expected_filename).stem
            expected_stems.add(stem)
        
        for filename in unmatched[:5]:  # Check first 5 unmatched files
            stem = Path(filename).stem
            similar = search_for_similar_stems(stem, expected_stems)
            
            print(f"\n📄 {filename}")
            print(f"   Stem: '{stem}'")
            if similar:
                print("   Similar stems found:")
                for similar_stem, score in similar[:3]:
                    print(f"     • {similar_stem} (similarity: {score:.3f})")
            else:
                print("   No similar stems found")

if __name__ == "__main__":
    main()