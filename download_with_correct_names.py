#!/usr/bin/env python3
"""
Download documents from Excel file with CORRECT FILENAMES that match ground truth.
This preserves the linkage between downloaded files and ground truth data.
"""

import pandas as pd
import requests
import os
import json
from pathlib import Path
from urllib.parse import urlparse, unquote
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

EXCEL_FILE = 'documents-info.xlsx'
DOWNLOAD_FOLDER = 'docs_correct'  # New folder to avoid conflicts
PROGRESS_FILE = 'download_progress_correct.json'
MAX_WORKERS = 10
progress_lock = threading.Lock()

def load_progress():
    """Load download progress from file"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'downloaded': {},
        'failed': {},
        'last_index': 0,
        'total': 0
    }

def save_progress(progress):
    """Save download progress to file"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def get_correct_filename_from_url(url):
    """
    Extract the EXACT filename from URL to maintain ground truth linkage.
    This preserves the filename that documents-info.xlsx expects.
    """
    # Parse the URL and get the last part of the path
    parsed_url = urlparse(url)
    # Get the filename from the path
    filename = os.path.basename(unquote(parsed_url.path))
    
    # Handle URL encoding properly
    # Decode percent-encoded characters
    filename = unquote(filename)
    
    # Replace any remaining problematic characters for filesystem
    # But preserve the name as much as possible for matching
    filename = filename.replace('%20', ' ')
    filename = filename.replace('%28', '(')
    filename = filename.replace('%29', ')')
    
    # Ensure we have a valid filename
    if not filename or filename == '':
        # Fallback - this should rarely happen
        filename = f'document_{abs(hash(url)) % 1000000}.pdf'
    
    return filename

def fix_azure_url(url):
    """
    Azure URL handling - URLs appear to be already properly encoded.
    No additional encoding transformations needed.
    """
    return url

def download_file_with_correct_name(row_data, folder, progress, thread_id=0):
    """
    Download a file using the correct filename from the URL.
    
    Args:
        row_data: Dictionary with 'url' and 'id' from the Excel row
        folder: Download folder path
        progress: Progress tracking dictionary
        thread_id: Thread identifier for logging
    """
    url = row_data['url']
    doc_id = row_data['id']
    
    # Get the correct filename from URL
    correct_filename = get_correct_filename_from_url(url)
    
    # Check if already downloaded
    with progress_lock:
        if url in progress['downloaded']:
            existing_file = progress['downloaded'][url]['filename']
            filepath = os.path.join(folder, existing_file)
            if os.path.exists(filepath):
                print(f"[T{thread_id:02d}] ✓ Already downloaded: {existing_file}")
                return True, existing_file
    
    # Apply Azure fix if needed
    download_url = fix_azure_url(url)
    
    try:
        # Download with timeout and streaming
        response = requests.get(download_url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Use the correct filename from URL
        filepath = os.path.join(folder, correct_filename)
        
        # Create parent directory if needed
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Download the file
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        
        # Update progress (thread-safe)
        with progress_lock:
            progress['downloaded'][url] = {
                'filename': correct_filename,
                'timestamp': datetime.now().isoformat(),
                'size': downloaded,
                'doc_id': doc_id
            }
            save_progress(progress)
        
        size_mb = downloaded / (1024 * 1024)
        print(f"[T{thread_id:02d}] ✓ Downloaded: {correct_filename} ({size_mb:.2f} MB) [ID: {doc_id}]")
        return True, correct_filename
        
    except requests.exceptions.RequestException as e:
        # Track failure
        with progress_lock:
            progress['failed'][url] = {
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'doc_id': doc_id,
                'expected_filename': correct_filename
            }
            save_progress(progress)
        
        print(f"[T{thread_id:02d}] ✗ Failed: {correct_filename} - {str(e)[:50]}")
        return False, None

def main():
    """Main download function"""
    print(f"\n{'='*60}")
    print("DOCUMENT DOWNLOAD WITH CORRECT GROUND TRUTH NAMES")
    print(f"{'='*60}\n")
    
    # Create download folder
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    print(f"📁 Download folder: {DOWNLOAD_FOLDER}")
    
    # Load Excel file
    print(f"📊 Loading Excel file: {EXCEL_FILE}")
    df = pd.read_excel(EXCEL_FILE)
    
    # Filter for rows with valid URLs
    df_with_urls = df[df['public_file_url'].notna()].copy()
    total_urls = len(df_with_urls)
    print(f"📋 Found {total_urls} documents with URLs")
    
    # Load progress
    progress = load_progress()
    progress['total'] = total_urls
    
    # Calculate what needs to be downloaded
    already_downloaded = len(progress['downloaded'])
    already_failed = len(progress['failed'])
    to_download = []
    
    for idx, row in df_with_urls.iterrows():
        url = row['public_file_url']
        if url not in progress['downloaded'] and url not in progress['failed']:
            to_download.append({
                'url': url,
                'id': row.get('id', idx),
                'index': idx
            })
    
    print(f"\n📈 Progress Status:")
    print(f"  ✓ Already downloaded: {already_downloaded}")
    print(f"  ✗ Previously failed: {already_failed}")
    print(f"  ⏳ To download: {len(to_download)}")
    
    if len(to_download) == 0:
        print("\n✅ All files already processed!")
        
        # Offer to retry failed downloads
        if already_failed > 0:
            retry = input(f"\nRetry {already_failed} failed downloads? (y/n): ")
            if retry.lower() == 'y':
                to_download = []
                for url, fail_info in progress['failed'].items():
                    # Find the row for this URL
                    row = df_with_urls[df_with_urls['public_file_url'] == url].iloc[0]
                    to_download.append({
                        'url': url,
                        'id': fail_info.get('doc_id', row.get('id', 0)),
                        'index': row.name
                    })
                # Clear failed list for retry
                progress['failed'] = {}
            else:
                return
        else:
            return
    
    # Download files with thread pool
    print(f"\n🚀 Starting download with {MAX_WORKERS} workers...\n")
    
    start_time = time.time()
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all download tasks
        future_to_row = {
            executor.submit(download_file_with_correct_name, row_data, DOWNLOAD_FOLDER, progress, i % MAX_WORKERS): row_data
            for i, row_data in enumerate(to_download)
        }
        
        # Process completed downloads
        for future in as_completed(future_to_row):
            row_data = future_to_row[future]
            try:
                success, filename = future.result()
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                fail_count += 1
            
            # Show progress
            total_processed = already_downloaded + success_count + fail_count
            if total_processed % 10 == 0:
                elapsed = time.time() - start_time
                rate = (success_count + fail_count) / elapsed if elapsed > 0 else 0
                print(f"\n📊 Progress: {total_processed}/{total_urls} ({total_processed*100/total_urls:.1f}%) - {rate:.1f} files/sec\n")
    
    # Final summary
    elapsed_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"⏱️  Time elapsed: {elapsed_time:.1f} seconds")
    print(f"✅ Successfully downloaded: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"📁 Files saved to: {DOWNLOAD_FOLDER}/")
    
    # Save final progress
    save_progress(progress)
    print(f"💾 Progress saved to: {PROGRESS_FILE}")
    
    # Show warning about filename preservation
    print(f"\n⚠️  IMPORTANT: Files are saved with their EXACT names from URLs")
    print(f"   This preserves the linkage with ground truth data in {EXCEL_FILE}")

if __name__ == "__main__":
    main()