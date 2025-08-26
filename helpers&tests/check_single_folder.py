#!/usr/bin/env python3
"""
Check filename matching for a single folder against ground truth Excel.
Simple and focused analysis.
"""

import pandas as pd
import os
from pathlib import Path
from urllib.parse import urlparse, unquote
import json

def get_filename_from_url(url):
    """Extract the expected filename from a URL"""
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    
    # Handle URL encoding
    filename = filename.replace('%20', ' ')
    filename = filename.replace('%28', '(')
    filename = filename.replace('%29', ')')
    
    return filename

def analyze_folder(excel_path='documents-info.xlsx', folder_path='docs_correct'):
    """
    Analyze filename matching for a single folder.
    
    Args:
        excel_path: Path to the ground truth Excel file
        folder_path: Path to folder to analyze
    """
    
    print(f"\n{'='*60}")
    print(f"ANALYZING FOLDER: {folder_path}")
    print(f"{'='*60}\n")
    
    # Load Excel file
    print(f"📊 Loading ground truth: {excel_path}")
    try:
        df = pd.read_excel(excel_path)
        total_rows = len(df)
        print(f"   Total rows: {total_rows}")
    except Exception as e:
        print(f"❌ Error loading Excel: {e}")
        return
    
    # Get rows with valid URLs
    df_with_urls = df[df['public_file_url'].notna()].copy()
    total_urls = len(df_with_urls)
    print(f"   Rows with URLs: {total_urls}")
    
    # Extract expected filenames from URLs
    expected_files = {}
    print(f"\n📋 Extracting expected filenames from URLs...")
    
    for idx, row in df_with_urls.iterrows():
        url = row['public_file_url']
        expected_filename = get_filename_from_url(url)
        doc_id = row.get('id', idx)
        
        expected_files[expected_filename] = {
            'url': url,
            'doc_id': doc_id,
            'row_index': idx
        }
    
    print(f"   Expected unique filenames: {len(expected_files)}")
    
    # Check the folder
    actual_files = set()
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        actual_files = {f for f in os.listdir(folder_path) if f.endswith(('.pdf', '.docx', '.doc'))}
        print(f"\n📁 Files in {folder_path}/: {len(actual_files)}")
    else:
        print(f"\n❌ {folder_path}/ does not exist or is not a directory")
        return
    
    # Analyze matching
    print(f"\n{'='*40}")
    print("MATCHING RESULTS")
    print(f"{'='*40}")
    
    matches = expected_files.keys() & actual_files
    missing = expected_files.keys() - actual_files
    extra = actual_files - expected_files.keys()
    
    match_rate = len(matches) / len(expected_files) * 100 if expected_files else 0
    
    print(f"\n✅ Perfect matches: {len(matches)} / {len(expected_files)} ({match_rate:.1f}%)")
    print(f"❌ Missing expected files: {len(missing)}")
    print(f"⚠️  Extra files (not in Excel): {len(extra)}")
    
    # Now check with STEM-BASED matching (like the actual pipeline)
    print(f"\n{'='*50}")
    print("STEM-BASED MATCHING (Pipeline Logic)")
    print(f"{'='*50}")
    
    # Create stem-based mappings
    expected_stems = {}  # stem -> original_filename
    found_stems = {}     # stem -> found_filename
    
    for filename in expected_files.keys():
        stem = Path(filename).stem
        expected_stems[stem] = filename
    
    for filename in actual_files:
        stem = Path(filename).stem  
        found_stems[stem] = filename
    
    # Check stem matches
    stem_matches = expected_stems.keys() & found_stems.keys()
    stem_missing = expected_stems.keys() - found_stems.keys()
    stem_extra = found_stems.keys() - expected_stems.keys()
    
    stem_match_rate = len(stem_matches) / len(expected_files) * 100 if expected_files else 0
    
    print(f"\n✅ Stem matches: {len(stem_matches)} / {len(expected_files)} ({stem_match_rate:.1f}%)")
    print(f"❌ Stem missing: {len(stem_missing)}")
    print(f"⚠️  Stem extra: {len(stem_extra)}")
    
    # Show format conversions (DOCX → PDF)
    format_conversions = []
    for stem in stem_matches:
        expected_file = expected_stems[stem]
        found_file = found_stems[stem]
        if Path(expected_file).suffix != Path(found_file).suffix:
            format_conversions.append((expected_file, found_file))
    
    if format_conversions:
        print(f"\n🔄 Format conversions detected: {len(format_conversions)}")
        print("   Examples (expected → found):")
        for expected, found in format_conversions[:10]:
            print(f"     {expected} → {found}")
        if len(format_conversions) > 10:
            print(f"     ... and {len(format_conversions) - 10} more")
    
    # Use stem-based results for the main analysis
    matches = stem_matches
    missing = stem_missing 
    extra = stem_extra
    match_rate = stem_match_rate
    
    # File type breakdown
    print(f"\n📋 File type breakdown:")
    
    # Expected files
    expected_extensions = {}
    for filename in expected_files.keys():
        ext = Path(filename).suffix.lower()
        expected_extensions[ext] = expected_extensions.get(ext, 0) + 1
    
    print(f"   Expected:")
    for ext, count in sorted(expected_extensions.items()):
        print(f"     {ext or 'no extension'}: {count}")
    
    # Actual files
    actual_extensions = {}
    for filename in actual_files:
        ext = Path(filename).suffix.lower()
        actual_extensions[ext] = actual_extensions.get(ext, 0) + 1
    
    print(f"   Found:")
    for ext, count in sorted(actual_extensions.items()):
        print(f"     {ext or 'no extension'}: {count}")
    
    # Show missing files (stem-based)
    if missing:
        print(f"\n❌ Missing files - no stem match found (showing first 15):")
        for stem in sorted(list(missing))[:15]:
            expected_filename = expected_stems[stem]
            doc_info = expected_files[expected_filename]
            print(f"   • {expected_filename} (ID: {doc_info['doc_id']})")
        if len(missing) > 15:
            print(f"   ... and {len(missing) - 15} more missing files")
    
    # Show extra files (stem-based)
    if extra:
        print(f"\n⚠️  Extra files - stem not in ground truth (showing first 10):")
        for stem in sorted(list(extra))[:10]:
            found_filename = found_stems[stem]
            print(f"   • {found_filename}")
        if len(extra) > 10:
            print(f"   ... and {len(extra) - 10} more extra files")
    
    # Summary and recommendations
    print(f"\n{'='*30}")
    print("SUMMARY")
    print(f"{'='*30}")
    
    if match_rate >= 95:
        print(f"🎉 Excellent! {match_rate:.1f}% match rate")
        print(f"   This folder is ready for batch processing")
    elif match_rate >= 90:
        print(f"✅ Good! {match_rate:.1f}% match rate") 
        print(f"   This folder should work well for batch processing")
    elif match_rate >= 80:
        print(f"⚠️  Moderate {match_rate:.1f}% match rate")
        print(f"   Some files missing - check download issues")
    else:
        print(f"❌ Low {match_rate:.1f}% match rate")
        print(f"   Consider re-downloading with correct filenames")
    
    # Save report
    report = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'folder_analyzed': folder_path,
        'excel_file': excel_path,
        'total_expected': len(expected_files),
        'total_found': len(actual_files),
        'matches': len(matches),
        'missing': len(missing),
        'extra': len(extra),
        'match_rate': match_rate / 100,
        'missing_files': sorted(list(missing)),
        'extra_files': sorted(list(extra)),
        'file_types_expected': expected_extensions,
        'file_types_found': actual_extensions
    }
    
    report_file = f'folder_analysis_{Path(folder_path).name}.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Detailed report saved to: {report_file}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze filename matching for a single folder")
    parser.add_argument('folder', help='Folder to analyze')
    parser.add_argument('--excel', default='documents-info.xlsx', help='Path to ground truth Excel file')
    
    args = parser.parse_args()
    
    analyze_folder(args.excel, args.folder)

if __name__ == "__main__":
    main()