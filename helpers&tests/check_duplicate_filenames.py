#!/usr/bin/env python3
"""
Check for duplicate filenames in documents-info.xlsx
"""

import pandas as pd
from urllib.parse import urlparse, unquote
import os
from collections import Counter

def get_filename_from_url(url):
    """Extract filename from URL."""
    if pd.isna(url) or not url:
        return None
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    return filename if filename else None

def main():
    # Load Excel file
    print("Loading documents-info.xlsx...")
    df = pd.read_excel('documents-info.xlsx')
    
    # Extract filenames from URLs
    print("Extracting filenames from URLs...")
    df['filename'] = df['public_file_url'].apply(get_filename_from_url)
    
    # Remove rows where filename couldn't be extracted
    valid_files = df.dropna(subset=['filename'])
    print(f"Found {len(valid_files)} valid filenames out of {len(df)} total rows")
    
    # Count filename occurrences
    filename_counts = Counter(valid_files['filename'])
    
    # Find duplicates
    duplicates = {filename: count for filename, count in filename_counts.items() if count > 1}
    
    if duplicates:
        print(f"\n🔍 FOUND {len(duplicates)} DUPLICATE FILENAMES:")
        print("=" * 60)
        
        total_duplicate_files = 0
        for filename, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True):
            print(f"{filename}: {count} copies")
            total_duplicate_files += count
            
            # Show the rows with this duplicate filename
            duplicate_rows = valid_files[valid_files['filename'] == filename]
            for idx, row in duplicate_rows.iterrows():
                print(f"  - Row {idx+2}: ID={row['id']}, Title='{row.get('title', 'N/A')[:50]}...', Country={row.get('country', 'N/A')}")
            print()
        
        print("=" * 60)
        print(f"Summary:")
        print(f"  • {len(duplicates)} unique filenames have duplicates")
        print(f"  • {total_duplicate_files} total files are duplicates") 
        print(f"  • {total_duplicate_files - len(duplicates)} extra files would be overwritten")
        print(f"  • {len(filename_counts)} unique filenames total")
        
    else:
        print("\n✅ NO DUPLICATE FILENAMES FOUND")
        print(f"All {len(filename_counts)} filenames are unique")

if __name__ == "__main__":
    main()