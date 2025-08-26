#!/usr/bin/env python3
import pandas as pd
import requests
import os
from urllib.parse import urlparse, unquote
import time
import re

def get_existing_files(folder):
    """Get a set of existing filenames in the folder"""
    existing = set()
    if os.path.exists(folder):
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                existing.add(filename)
                # Also add the base name without number suffixes
                match = re.match(r'^(.+?)(_\d+)?(\.[^.]+)$', filename)
                if match:
                    base_name = match.group(1) + (match.group(3) or '')
                    existing.add(base_name)
    return existing

def get_expected_filename_from_url(url):
    """Extract expected filename from URL"""
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    if not filename or filename == '':
        # Use URL hash for nameless files
        filename = f'document_{abs(hash(url)) % 1000000}.pdf'
    return filename

def is_file_already_downloaded(url, existing_files):
    """Check if a file from this URL likely already exists"""
    expected_filename = get_expected_filename_from_url(url)
    
    # Check exact match
    if expected_filename in existing_files:
        return True, expected_filename
    
    # Check without extension and with common suffixes
    base_without_ext = os.path.splitext(expected_filename)[0]
    ext = os.path.splitext(expected_filename)[1]
    
    # Check for numbered versions
    for i in range(1, 10):
        if f"{base_without_ext}_{i}{ext}" in existing_files:
            return True, f"{base_without_ext}_{i}{ext}"
    
    # Check if base name matches any existing file
    for existing_file in existing_files:
        if existing_file.startswith(base_without_ext) and existing_file.endswith(ext):
            return True, existing_file
    
    return False, None

def download_file(url, folder, existing_files):
    """Download a file if not already present"""
    # Check if already downloaded
    already_exists, existing_filename = is_file_already_downloaded(url, existing_files)
    if already_exists:
        print(f"✓ Already exists: {existing_filename}")
        return True, existing_filename, True  # success, filename, was_skipped
    
    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Try to get filename from Content-Disposition header
        filename = None
        if 'content-disposition' in response.headers:
            content_disp = response.headers['content-disposition']
            if 'filename=' in content_disp:
                filename = content_disp.split('filename=')[-1].strip('"')
        
        # If no filename in header, extract from URL
        if not filename:
            filename = get_expected_filename_from_url(url)
        
        filepath = os.path.join(folder, filename)
        
        # If file already exists (shouldn't happen but just in case), find a new name
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filepath)
            counter = 1
            while os.path.exists(filepath):
                filepath = f"{base}_{counter}{ext}"
                counter += 1
            filename = os.path.basename(filepath)
        
        # Download the file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Add to existing files set
        existing_files.add(filename)
        file_size = os.path.getsize(filepath)
        
        print(f"✓ Downloaded: {filename} ({file_size / 1024:.1f} KB)")
        return True, filename, False  # success, filename, was_skipped
        
    except Exception as e:
        print(f"✗ Failed to download {url}: {str(e)}")
        return False, None, False

def main():
    # Read the Excel file
    try:
        df = pd.read_excel('documents-info.xlsx')
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return
    
    # Check if column 'public_file_url' exists
    if 'public_file_url' not in df.columns:
        print("Column 'public_file_url' not found in the Excel file")
        print(f"Available columns: {list(df.columns)}")
        return
    
    # Create docs folder if it doesn't exist
    if not os.path.exists('docs'):
        os.makedirs('docs')
        print("Created 'docs' folder")
    
    # Get existing files
    print("Scanning existing files...")
    existing_files = get_existing_files('docs')
    existing_count = len([f for f in os.listdir('docs') if os.path.isfile(os.path.join('docs', f))])
    print(f"Found {existing_count} files in docs folder")
    
    # Get all URLs from column 'public_file_url'
    urls = df['public_file_url'].dropna().tolist()
    total_urls = len(urls)
    print(f"Found {total_urls} URLs in Excel file")
    
    # Count how many are likely already downloaded
    already_downloaded_count = 0
    for url in urls:
        if is_file_already_downloaded(str(url).strip(), existing_files)[0]:
            already_downloaded_count += 1
    
    print(f"Estimated already downloaded: {already_downloaded_count}")
    print(f"Estimated remaining: {total_urls - already_downloaded_count}")
    
    # Download each file
    success_count = 0
    skipped_count = 0
    new_downloads = 0
    failed_urls = []
    
    print(f"\n{'='*50}")
    
    for i, url in enumerate(urls, 1):
        url = str(url).strip()
        
        print(f"\nProcessing {i}/{total_urls}: {url}")
        
        success, filename, was_skipped = download_file(url, 'docs', existing_files)
        
        if success:
            success_count += 1
            if was_skipped:
                skipped_count += 1
            else:
                new_downloads += 1
                # Be polite to servers for new downloads
                time.sleep(1)
        else:
            failed_urls.append(url)
    
    print(f"\n{'='*50}")
    print(f"Download complete!")
    print(f"Total URLs: {total_urls}")
    print(f"Successfully processed: {success_count}")
    print(f"  - Already existed: {skipped_count}")
    print(f"  - Newly downloaded: {new_downloads}")
    print(f"Failed downloads: {len(failed_urls)}")
    
    if failed_urls:
        # Save failed URLs for retry
        with open('failed_downloads.txt', 'w') as f:
            for url in failed_urls:
                f.write(url + '\n')
        print(f"\nFailed URLs saved to 'failed_downloads.txt' for retry")

if __name__ == "__main__":
    main()