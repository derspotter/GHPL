#!/usr/bin/env python3
"""
Check which files are missing in docs_final/ compared to what should be downloaded
from documents-info.xlsx
"""

import pandas as pd
import os
from urllib.parse import urlparse, unquote
from pathlib import Path

def get_filename_from_url(url):
    """Extract filename from URL."""
    if pd.isna(url) or not url:
        return None
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    return filename if filename else None

def main():
    print("📊 CHECKING MISSING FILES IN docs_final/")
    print("=" * 60)
    
    # Load Excel file
    print("Loading documents-info.xlsx...")
    df = pd.read_excel('documents-info.xlsx')
    
    # Extract expected filenames from URLs
    print("Extracting expected filenames from URLs...")
    df['filename'] = df['public_file_url'].apply(get_filename_from_url)
    valid_files = df.dropna(subset=['filename'])
    
    expected_files = set(valid_files['filename'].tolist())
    print(f"Expected {len(expected_files)} unique files from Excel")
    
    # Get actual files in docs_final/
    docs_final_path = Path('docs_final')
    if not docs_final_path.exists():
        print("❌ docs_final/ directory does not exist!")
        return
        
    actual_files = set()
    for file_path in docs_final_path.iterdir():
        if file_path.is_file():
            actual_files.add(file_path.name)
    
    print(f"Found {len(actual_files)} actual files in docs_final/")
    
    # Find missing files
    missing_files = expected_files - actual_files
    extra_files = actual_files - expected_files
    
    print("\n" + "=" * 60)
    print("📋 RESULTS SUMMARY")
    print("=" * 60)
    print(f"Expected files: {len(expected_files)}")
    print(f"Actual files: {len(actual_files)}")
    print(f"Missing files: {len(missing_files)}")
    print(f"Extra files: {len(extra_files)}")
    print(f"Successfully downloaded: {len(expected_files) - len(missing_files)}")
    
    # Show missing files
    if missing_files:
        print(f"\n🚫 MISSING FILES ({len(missing_files)}):")
        print("-" * 40)
        
        # Get details for missing files
        missing_with_details = []
        for filename in missing_files:
            file_rows = valid_files[valid_files['filename'] == filename]
            for _, row in file_rows.iterrows():
                missing_with_details.append({
                    'filename': filename,
                    'id': row.get('id', 'N/A'),
                    'title': row.get('title', 'N/A')[:50] + '...' if len(str(row.get('title', 'N/A'))) > 50 else row.get('title', 'N/A'),
                    'country': row.get('country', 'N/A'),
                    'url': row.get('public_file_url', 'N/A')
                })
        
        # Sort by filename
        missing_with_details.sort(key=lambda x: x['filename'])
        
        for item in missing_with_details:
            print(f"• {item['filename']}")
            print(f"  - ID: {item['id']}, Country: {item['country']}")
            print(f"  - Title: {item['title']}")
            print(f"  - URL: {item['url'][:80]}...")
            print()
    else:
        print("\n✅ NO MISSING FILES - All expected files are present!")
    
    # Show extra files (shouldn't happen but good to check)
    if extra_files:
        print(f"\n📁 EXTRA FILES ({len(extra_files)}):")
        print("-" * 40)
        for filename in sorted(extra_files):
            print(f"• {filename}")
    
    # Calculate success rate
    success_rate = ((len(expected_files) - len(missing_files)) / len(expected_files)) * 100
    print(f"\n📊 SUCCESS RATE: {success_rate:.1f}%")

if __name__ == "__main__":
    main()