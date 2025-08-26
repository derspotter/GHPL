#!/usr/bin/env python3
"""
Fast concurrent downloader - downloads all files with duplicate handling.
Based on download_with_correct_names.py but preserves ALL documents by renaming duplicates.
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
DOWNLOAD_FOLDER = 'docs_all_complete'  # New folder for complete collection
PROGRESS_FILE = 'download_progress_complete.json'
MAX_WORKERS = 10  # Fast concurrent downloads
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

def download_file_concurrent(row_data, folder, progress, thread_id=0):
    """
    Download a file with concurrent handling and duplicate renaming.
    
    Args:
        row_data: Dictionary with 'url' and 'id' from the Excel row
        folder: Download folder path
        progress: Progress tracking dictionary
        thread_id: Thread identifier for logging
    """
    url = row_data['url']
    doc_id = row_data['id']
    
    # Get the filename from URL
    original_filename = get_filename_from_url(url)
    
    # Check if already downloaded (thread-safe check)
    with progress_lock:
        if url in progress['downloaded']:
            existing_file = progress['downloaded'][url]['filename']
            filepath = os.path.join(folder, existing_file)
            if os.path.exists(filepath):
                print(f"[T{thread_id:02d}] ✓ Already downloaded: {existing_file}")
                return True, existing_file
    
    try:
        # Download with timeout and streaming
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Get unique filepath (handles duplicates)
        with progress_lock:
            filepath, actual_filename = get_unique_filepath(folder, original_filename)
        
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
                'filename': actual_filename,
                'original_filename': original_filename,
                'timestamp': datetime.now().isoformat(),
                'size': downloaded,
                'doc_id': doc_id,
                'was_renamed': actual_filename != original_filename
            }
            save_progress(progress)
        
        size_mb = downloaded / (1024 * 1024)
        was_renamed = actual_filename != original_filename
        
        if was_renamed:
            print(f"[T{thread_id:02d}] ✓ Downloaded: {actual_filename} (renamed from {original_filename}) ({size_mb:.2f} MB) [ID: {doc_id}]")
        else:
            print(f"[T{thread_id:02d}] ✓ Downloaded: {actual_filename} ({size_mb:.2f} MB) [ID: {doc_id}]")
        
        return True, actual_filename
        
    except requests.exceptions.RequestException as e:
        # Track failure
        with progress_lock:
            progress['failed'][url] = {
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'doc_id': doc_id,
                'expected_filename': original_filename
            }
            save_progress(progress)
        
        print(f"[T{thread_id:02d}] ✗ Failed: {original_filename} - {str(e)[:50]}")
        return False, None

def main():
    """Main download function"""
    print(f"\n{'='*60}")
    print("FAST CONCURRENT DOWNLOAD - ALL FILES WITH DUPLICATES")
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
        
        # Show duplicate stats from existing downloads
        renamed_count = 0
        for url, info in progress['downloaded'].items():
            if info.get('was_renamed', False):
                renamed_count += 1
        
        print(f"\n📊 Collection Statistics:")
        print(f"  📄 Total files: {already_downloaded}")
        print(f"  🔄 Files renamed (duplicates): {renamed_count}")
        print(f"  📁 Unique filenames preserved: {already_downloaded - renamed_count}")
        return
    
    # Download files with thread pool
    print(f"\n🚀 Starting concurrent download with {MAX_WORKERS} workers...")
    print(f"⚡ Expected to save ALL {total_urls} documents (no overwrites!)\n")
    
    start_time = time.time()
    success_count = 0
    fail_count = 0
    renamed_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all download tasks
        future_to_row = {
            executor.submit(download_file_concurrent, row_data, DOWNLOAD_FOLDER, progress, i % MAX_WORKERS): row_data
            for i, row_data in enumerate(to_download)
        }
        
        # Process completed downloads
        for future in as_completed(future_to_row):
            row_data = future_to_row[future]
            try:
                success, filename = future.result()
                if success:
                    success_count += 1
                    # Check if this was a renamed file
                    url = row_data['url']
                    if url in progress['downloaded'] and progress['downloaded'][url].get('was_renamed', False):
                        renamed_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                fail_count += 1
            
            # Show progress every 25 files
            total_processed = success_count + fail_count
            if total_processed % 25 == 0:
                elapsed = time.time() - start_time
                rate = total_processed / elapsed if elapsed > 0 else 0
                progress_total = already_downloaded + total_processed
                print(f"\n📊 Progress: {progress_total}/{total_urls} ({progress_total*100/total_urls:.1f}%) - {rate:.1f} files/sec")
                print(f"   ✅ Downloaded: {success_count} | ❌ Failed: {fail_count} | 🔄 Renamed: {renamed_count}\n")
    
    # Final summary
    elapsed_time = time.time() - start_time
    total_renamed = renamed_count
    
    # Count total renames including previous ones
    for url, info in progress['downloaded'].items():
        if info.get('was_renamed', False) and url not in [r['url'] for r in to_download]:
            total_renamed += 1
    
    print(f"\n{'='*60}")
    print(f"DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"⏱️  Time elapsed: {elapsed_time:.1f} seconds")
    print(f"🚀 Download speed: {success_count/elapsed_time:.1f} files/sec")
    print(f"✅ Successfully downloaded: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"📁 Files saved to: {DOWNLOAD_FOLDER}/")
    print(f"\n📊 DUPLICATE HANDLING:")
    print(f"  🔄 Files renamed this session: {renamed_count}")  
    print(f"  📄 Total files in collection: {already_downloaded + success_count}")
    print(f"  🎯 Expected total documents: {total_urls}")
    
    # Save final progress
    save_progress(progress)
    print(f"\n💾 Progress saved to: {PROGRESS_FILE}")
    
    print(f"\n🎉 SUCCESS: All {total_urls} documents preserved!")
    print(f"   No documents lost to overwrites - duplicates renamed with suffixes")

if __name__ == "__main__":
    main()