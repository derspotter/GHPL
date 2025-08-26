#!/usr/bin/env python3
"""
Simple downloader - downloads all files from Excel to docs_final folder.
URLs are already fixed upstream in the Excel file.
"""

import pandas as pd
import requests
import os
from urllib.parse import urlparse, unquote
import time

def get_filename_from_url(url):
    """Extract filename from URL."""
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    return filename if filename else f'document_{abs(hash(url)) % 1000000}.pdf'

def get_unique_filepath(folder, filename):
    """Get a unique filepath by adding _1, _2, etc. if file exists."""
    base_path = os.path.join(folder, filename)
    
    # If file doesn't exist, use original name
    if not os.path.exists(base_path):
        return base_path, filename
    
    # Split filename into name and extension
    name, ext = os.path.splitext(filename)
    
    # Find next available number
    counter = 1
    while True:
        new_filename = f"{name}_{counter}{ext}"
        new_path = os.path.join(folder, new_filename)
        if not os.path.exists(new_path):
            return new_path, new_filename
        counter += 1

def download_file(url, folder):
    """Download a file from URL to folder, handling duplicates with suffixes."""
    try:
        original_filename = get_filename_from_url(url)
        filepath, actual_filename = get_unique_filepath(folder, original_filename)
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
            
        size_kb = len(response.content) / 1024
        
        was_renamed = actual_filename != original_filename
        
        if was_renamed:
            print(f"✓ Downloaded: {actual_filename} (renamed from {original_filename}) ({size_kb:.1f} KB)")
        else:
            print(f"✓ Downloaded: {actual_filename} ({size_kb:.1f} KB)")
        
        return True, actual_filename, was_renamed
        
    except Exception as e:
        print(f"✗ Failed: {original_filename} - {e}")
        return False, original_filename, False

def main():
    # Create docs_final folder
    os.makedirs('docs_final', exist_ok=True)
    print("Created 'docs_final' folder")
    
    # Load Excel file
    df = pd.read_excel('documents-info.xlsx')
    urls = df['public_file_url'].dropna().tolist()
    
    print(f"Found {len(urls)} URLs to download")
    
    downloaded = 0
    failed = 0
    duplicates_renamed = 0
    
    for i, url in enumerate(urls, 1):
        print(f"Processing {i}/{len(urls)}: {url}")
        success, actual_filename, was_duplicate = download_file(url, 'docs_final')
        
        if success:
            downloaded += 1
            if was_duplicate:
                duplicates_renamed += 1
        else:
            failed += 1
            
        # Brief pause to be nice to server
        time.sleep(0.1)
    
    print(f"\n=== DOWNLOAD COMPLETE ===")
    print(f"Downloaded: {downloaded}")
    print(f"Duplicates renamed: {duplicates_renamed}")
    print(f"Failed: {failed}")
    print(f"Total files saved: {downloaded}")

if __name__ == "__main__":
    main()