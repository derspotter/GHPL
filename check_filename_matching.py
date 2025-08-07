#!/usr/bin/env python3
"""
Check and validate filename matching between downloaded files and ground truth Excel.
This ensures proper linkage for batch processing and exports.
"""

import pandas as pd
import os
from pathlib import Path
from urllib.parse import urlparse, unquote
import json
from collections import defaultdict

def get_filename_from_url(url):
    """Extract the expected filename from a URL"""
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    
    # Handle URL encoding
    filename = filename.replace('%20', ' ')
    filename = filename.replace('%28', '(')
    filename = filename.replace('%29', ')')
    
    return filename

def check_filename_matching(excel_path='documents-info.xlsx', docs_folder='docs', correct_docs_folder='docs_correct'):
    """
    Check filename matching between Excel ground truth and downloaded files.
    
    Args:
        excel_path: Path to the ground truth Excel file
        docs_folder: Path to existing downloaded files
        correct_docs_folder: Path to correctly named downloaded files
    """
    
    print(f"\n{'='*70}")
    print("FILENAME MATCHING VALIDATION")
    print(f"{'='*70}\n")
    
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
    url_to_id = {}
    
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
        url_to_id[url] = doc_id
    
    print(f"   Expected unique filenames: {len(expected_files)}")
    
    # Check existing docs folder
    existing_files = set()
    if os.path.exists(docs_folder) and os.path.isdir(docs_folder):
        existing_files = {f for f in os.listdir(docs_folder) if f.endswith(('.pdf', '.docx', '.doc'))}
        print(f"\n📁 Files in {docs_folder}/: {len(existing_files)}")
    else:
        print(f"\n📁 {docs_folder}/ does not exist or is not a directory")
    
    # Check correct docs folder
    correct_files = set()
    if os.path.exists(correct_docs_folder) and os.path.isdir(correct_docs_folder):
        correct_files = {f for f in os.listdir(correct_docs_folder) if f.endswith(('.pdf', '.docx', '.doc'))}
        print(f"📁 Files in {correct_docs_folder}/: {len(correct_files)}")
    else:
        print(f"📁 {correct_docs_folder}/ does not exist or is not a directory")
    
    # Analyze matching
    print(f"\n{'='*50}")
    print("MATCHING ANALYSIS")
    print(f"{'='*50}")
    
    # Check how many expected files are in existing folder
    existing_matches = expected_files.keys() & existing_files
    existing_missing = expected_files.keys() - existing_files
    existing_extra = existing_files - expected_files.keys()
    
    print(f"\n📊 {docs_folder}/ Analysis:")
    print(f"   ✅ Perfect matches: {len(existing_matches)} / {len(expected_files)} ({len(existing_matches)*100/len(expected_files):.1f}%)")
    print(f"   ❌ Missing expected files: {len(existing_missing)}")
    print(f"   ⚠️  Extra files (not in Excel): {len(existing_extra)}")
    
    # Check how many expected files are in correct folder
    if correct_files:
        correct_matches = expected_files.keys() & correct_files
        correct_missing = expected_files.keys() - correct_files
        correct_extra = correct_files - expected_files.keys()
        
        print(f"\n📊 {correct_docs_folder}/ Analysis:")
        print(f"   ✅ Perfect matches: {len(correct_matches)} / {len(expected_files)} ({len(correct_matches)*100/len(expected_files):.1f}%)")
        print(f"   ❌ Missing expected files: {len(correct_missing)}")
        print(f"   ⚠️  Extra files (not in Excel): {len(correct_extra)}")
    
    # Show detailed mismatch examples
    if existing_missing:
        print(f"\n❌ Sample missing files from {docs_folder}/:")
        for filename in sorted(list(existing_missing))[:10]:
            doc_info = expected_files[filename]
            print(f"   • {filename} (ID: {doc_info['doc_id']})")
        if len(existing_missing) > 10:
            print(f"   ... and {len(existing_missing) - 10} more")
    
    if existing_extra:
        print(f"\n⚠️  Sample extra files in {docs_folder}/:")
        for filename in sorted(list(existing_extra))[:10]:
            print(f"   • {filename}")
        if len(existing_extra) > 10:
            print(f"   ... and {len(existing_extra) - 10} more")
    
    # Check for potential fuzzy matches
    print(f"\n🔍 FUZZY MATCHING ANALYSIS")
    print(f"{'='*40}")
    
    potential_matches = []
    for missing_file in existing_missing:
        # Look for similar names in existing files
        missing_stem = Path(missing_file).stem.lower()
        for existing_file in existing_extra:
            existing_stem = Path(existing_file).stem.lower()
            
            # Simple similarity check
            if len(missing_stem) > 10 and len(existing_stem) > 10:
                # Check if one contains the other
                if missing_stem in existing_stem or existing_stem in missing_stem:
                    potential_matches.append((missing_file, existing_file))
                # Check for common words (basic)
                elif len(set(missing_stem.split()) & set(existing_stem.split())) >= 3:
                    potential_matches.append((missing_file, existing_file))
    
    if potential_matches:
        print(f"\n🤔 Potential fuzzy matches found ({len(potential_matches)}):")
        for expected, actual in potential_matches[:5]:
            print(f"   Expected: {expected}")
            print(f"   Actual:   {actual}")
            print()
        if len(potential_matches) > 5:
            print(f"   ... and {len(potential_matches) - 5} more potential matches")
    else:
        print("   No obvious fuzzy matches found")
    
    # Generate recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print(f"{'='*30}")
    
    if len(existing_matches) < len(expected_files) * 0.9:
        print(f"❗ Low match rate ({len(existing_matches)*100/len(expected_files):.1f}%)")
        print(f"   Consider using download_with_correct_names.py to re-download with proper filenames")
    
    if correct_files and len(correct_matches) > len(existing_matches):
        improvement = len(correct_matches) - len(existing_matches)
        print(f"✅ {correct_docs_folder}/ has {improvement} more correct matches")
        print(f"   Consider using {correct_docs_folder}/ for batch processing")
    
    # Export detailed report
    report_file = 'filename_matching_report.json'
    report = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'excel_file': excel_path,
        'total_expected': len(expected_files),
        'existing_folder': {
            'path': docs_folder,
            'total_files': len(existing_files),
            'matches': len(existing_matches),
            'missing': len(existing_missing),
            'extra': len(existing_extra),
            'match_rate': len(existing_matches) / len(expected_files) if expected_files else 0
        },
        'missing_files': list(existing_missing),
        'extra_files': list(existing_extra),
        'fuzzy_matches': potential_matches
    }
    
    if correct_files:
        report['correct_folder'] = {
            'path': correct_docs_folder,
            'total_files': len(correct_files),
            'matches': len(correct_matches),
            'missing': len(correct_missing),
            'extra': len(correct_extra),
            'match_rate': len(correct_matches) / len(expected_files) if expected_files else 0
        }
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Detailed report saved to: {report_file}")
    
    return report

def main():
    """Main function to run the filename matching check"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check filename matching between Excel and downloaded files")
    parser.add_argument('--excel', default='documents-info.xlsx', help='Path to ground truth Excel file')
    parser.add_argument('--docs', default='docs', help='Path to existing docs folder')
    parser.add_argument('--correct-docs', default='docs_correct', help='Path to correctly named docs folder')
    
    args = parser.parse_args()
    
    report = check_filename_matching(args.excel, args.docs, args.correct_docs)
    
    # Summary
    existing_rate = report['existing_folder']['match_rate'] * 100
    print(f"\n📈 SUMMARY:")
    print(f"   Match rate in {args.docs}/: {existing_rate:.1f}%")
    
    if 'correct_folder' in report:
        correct_rate = report['correct_folder']['match_rate'] * 100
        print(f"   Match rate in {args.correct_docs}/: {correct_rate:.1f}%")
        
        if correct_rate > existing_rate:
            print(f"   🎯 Use {args.correct_docs}/ for better processing results!")

if __name__ == "__main__":
    main()