#!/usr/bin/env python3
import pandas as pd
import requests
import os
import json
from urllib.parse import urlparse, unquote
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

PROGRESS_FILE = 'download_progress.json'
MAX_WORKERS = 10  # Number of concurrent downloads
progress_lock = threading.Lock()  # Thread-safe progress updates

def load_progress():
    """Load download progress from file"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'downloaded': {},
        'failed': {},
        'last_index': 0
    }

def save_progress(progress):
    """Save download progress to file"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def get_filename_from_url(url):
    """Extract filename from URL or response headers"""
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    if not filename or filename == '':
        filename = f'document_{abs(hash(url)) % 1000000}'
    return filename

def check_if_already_downloaded(url, progress, folder):
    """Check if URL was already downloaded successfully"""
    if url in progress['downloaded']:
        filename = progress['downloaded'][url]['filename']
        filepath = os.path.join(folder, filename)
        if os.path.exists(filepath):
            return True, filename
    return False, None

def fix_azure_url(url):
    """
    Fix Azure Blob Storage URL encoding issue.
    Azure stores '%20' literally in filenames, so we need to encode it as %2520.
    """
    if 'blob.core.windows.net' in url:
        return url.replace('%20', '%2520')
    return url

def download_file(url, folder, progress, thread_id=0):
    """Download a file and update progress (thread-safe)"""
    # Check if already downloaded
    with progress_lock:
        already_downloaded, existing_filename = check_if_already_downloaded(url, progress, folder)
        if already_downloaded:
            print(f"[T{thread_id:02d}] ✓ Already downloaded: {existing_filename}")
            return True, existing_filename
    
    # Apply Azure Blob Storage fix
    fixed_url = fix_azure_url(url)
    azure_fixed = fixed_url != url
    
    try:
        response = requests.get(fixed_url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Try to get filename from Content-Disposition header
        filename = None
        if 'content-disposition' in response.headers:
            content_disp = response.headers['content-disposition']
            if 'filename=' in content_disp:
                filename = content_disp.split('filename=')[-1].strip('"')
        
        # If no filename in header, extract from URL
        if not filename:
            filename = get_filename_from_url(url)
        
        filepath = os.path.join(folder, filename)
        
        # Handle duplicate filenames (thread-safe)
        with progress_lock:
            base, ext = os.path.splitext(filepath)
            counter = 1
            original_filename = filename
            while os.path.exists(filepath):
                filename = f"{os.path.splitext(original_filename)[0]}_{counter}{ext}"
                filepath = os.path.join(folder, filename)
                counter += 1
        
        # Download the file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(filepath)
        
        # Update progress (thread-safe)
        with progress_lock:
            progress['downloaded'][url] = {
                'filename': filename,
                'timestamp': datetime.now().isoformat(),
                'size': file_size
            }
        
        azure_msg = " (Azure fix applied)" if azure_fixed else ""
        print(f"[T{thread_id:02d}] ✓ Downloaded: {filename} ({file_size / 1024:.1f} KB){azure_msg}")
        return True, filename
        
    except Exception as e:
        with progress_lock:
            progress['failed'][url] = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
        print(f"[T{thread_id:02d}] ✗ Failed: {url[:50]}... - {str(e)[:50]}")
        return False, None

def main():
    # Load progress
    progress = load_progress()
    
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
    
    # Get all URLs from column 'public_file_url'
    urls = df['public_file_url'].dropna().tolist()
    total_urls = len(urls)
    print(f"Found {total_urls} URLs in Excel file")
    
    # Count already downloaded
    already_downloaded_count = sum(1 for url in urls if url in progress['downloaded'])
    print(f"Already downloaded: {already_downloaded_count}")
    print(f"Remaining to download: {total_urls - already_downloaded_count}")
    
    # Download files with concurrent processing
    print(f"\n{'='*50}")
    print(f"Starting concurrent downloads with {MAX_WORKERS} workers")
    print(f"{'='*50}\n")
    
    new_downloads = 0
    urls_to_process = []
    
    # Filter out already downloaded URLs
    for url in urls:
        url = str(url).strip()
        if url not in progress['downloaded']:
            urls_to_process.append(url)
    
    if not urls_to_process:
        print("All files already downloaded!")
    else:
        print(f"Processing {len(urls_to_process)} remaining URLs...")
        
        # Process URLs in batches
        batch_size = MAX_WORKERS * 5  # Process 5 rounds of concurrent downloads at a time
        
        for batch_start in range(0, len(urls_to_process), batch_size):
            batch_end = min(batch_start + batch_size, len(urls_to_process))
            batch = urls_to_process[batch_start:batch_end]
            
            print(f"\nBatch {batch_start//batch_size + 1}: Processing URLs {batch_start+1} to {batch_end}")
            
            # Use ThreadPoolExecutor for concurrent downloads
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Submit all download tasks
                future_to_url = {}
                for i, url in enumerate(batch):
                    thread_id = i % MAX_WORKERS
                    future = executor.submit(download_file, url, 'docs', progress, thread_id)
                    future_to_url[future] = url
                
                # Process completed downloads
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        success, filename = future.result()
                        if success:
                            new_downloads += 1
                    except Exception as e:
                        print(f"Exception for {url}: {str(e)}")
            
            # Save progress after each batch
            save_progress(progress)
            print(f"Progress saved. Downloaded {new_downloads} new files so far.")
            
            # Small delay between batches to be nice to the server
            if batch_end < len(urls_to_process):
                time.sleep(2)
    
    # Save final progress
    save_progress(progress)
    
    print(f"\n{'='*50}")
    print(f"Download complete!")
    print(f"Total files: {total_urls}")
    print(f"Successfully downloaded: {len(progress['downloaded'])}")
    print(f"Failed downloads: {len(progress['failed'])}")
    print(f"New downloads this session: {new_downloads}")
    
    if progress['failed']:
        print(f"\nFailed URLs saved in {PROGRESS_FILE} for retry")

if __name__ == "__main__":
    main()