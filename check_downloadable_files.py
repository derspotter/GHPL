#!/usr/bin/env python3
"""
Dry run check for downloadable files - tests URLs without actually downloading.
Logs all files that cannot be downloaded for analysis.
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
CHECK_RESULTS_FILE = 'download_check_results.json'
MAX_WORKERS = 10
results_lock = threading.Lock()

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

def check_file_downloadable(row_data, results, thread_id=0):
    """
    Check if a file can be downloaded without actually downloading it.
    
    Args:
        row_data: Dictionary with 'url' and 'id' from the Excel row
        results: Results tracking dictionary
        thread_id: Thread identifier for logging
    """
    url = row_data['url']
    doc_id = row_data['id']
    
    # Get the correct filename from URL
    correct_filename = get_correct_filename_from_url(url)
    
    # Apply Azure fix if needed
    download_url = fix_azure_url(url)
    
    try:
        # Send HEAD request first (faster, no content download)
        response = requests.head(download_url, timeout=15, allow_redirects=True)
        
        # If HEAD fails, try GET with minimal range
        if response.status_code not in [200, 206]:
            # Try GET request with just first byte to test accessibility
            headers = {'Range': 'bytes=0-0'}
            response = requests.get(download_url, timeout=15, headers=headers, stream=True)
        
        if response.status_code in [200, 206, 416]:  # 416 = Range Not Satisfiable (but file exists)
            # File is accessible
            content_length = response.headers.get('content-length', 'unknown')
            content_type = response.headers.get('content-type', 'unknown')
            
            with results_lock:
                results['downloadable'][url] = {
                    'filename': correct_filename,
                    'doc_id': doc_id,
                    'status_code': response.status_code,
                    'content_length': content_length,
                    'content_type': content_type,
                    'timestamp': datetime.now().isoformat()
                }
            
            print(f"[T{thread_id:02d}] ✓ OK: {correct_filename} ({content_length} bytes) [ID: {doc_id}]")
            return True, correct_filename
            
        else:
            # File not accessible
            with results_lock:
                results['failed'][url] = {
                    'filename': correct_filename,
                    'doc_id': doc_id,
                    'status_code': response.status_code,
                    'error': f'HTTP {response.status_code}',
                    'timestamp': datetime.now().isoformat()
                }
            
            print(f"[T{thread_id:02d}] ✗ FAIL: {correct_filename} - HTTP {response.status_code} [ID: {doc_id}]")
            return False, correct_filename
        
    except requests.exceptions.RequestException as e:
        # Network or request error
        with results_lock:
            results['failed'][url] = {
                'filename': correct_filename,
                'doc_id': doc_id,
                'status_code': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
        
        print(f"[T{thread_id:02d}] ✗ ERROR: {correct_filename} - {str(e)[:60]} [ID: {doc_id}]")
        return False, correct_filename

def save_results(results):
    """Save check results to file"""
    with open(CHECK_RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

def main():
    """Main check function"""
    print(f"\n{'='*70}")
    print("DRY RUN: CHECKING FILE DOWNLOADABILITY")
    print(f"{'='*70}\n")
    
    # Load Excel file
    print(f"📊 Loading Excel file: {EXCEL_FILE}")
    df = pd.read_excel(EXCEL_FILE)
    
    # Filter for rows with valid URLs
    df_with_urls = df[df['public_file_url'].notna()].copy()
    total_urls = len(df_with_urls)
    print(f"📋 Found {total_urls} documents with URLs")
    
    # Initialize results tracking
    results = {
        'downloadable': {},
        'failed': {},
        'summary': {
            'total_checked': 0,
            'downloadable_count': 0,
            'failed_count': 0,
            'start_time': datetime.now().isoformat()
        }
    }
    
    # Prepare URLs to check
    to_check = []
    for idx, row in df_with_urls.iterrows():
        url = row['public_file_url']
        to_check.append({
            'url': url,
            'id': row.get('id', idx),
            'index': idx
        })
    
    print(f"\n🚀 Starting download check with {MAX_WORKERS} workers...")
    print(f"⚠️  This is a DRY RUN - no files will be downloaded\n")
    
    start_time = time.time()
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all check tasks
        future_to_row = {
            executor.submit(check_file_downloadable, row_data, results, i % MAX_WORKERS): row_data
            for i, row_data in enumerate(to_check)
        }
        
        # Process completed checks
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
            
            # Show progress every 50 files
            total_processed = success_count + fail_count
            if total_processed % 50 == 0:
                elapsed = time.time() - start_time
                rate = total_processed / elapsed if elapsed > 0 else 0
                print(f"\n📊 Progress: {total_processed}/{total_urls} ({total_processed*100/total_urls:.1f}%) - {rate:.1f} checks/sec")
                print(f"   ✓ Downloadable: {success_count} | ✗ Failed: {fail_count}\n")
    
    # Final results
    elapsed_time = time.time() - start_time
    
    # Update summary
    results['summary'].update({
        'total_checked': total_urls,
        'downloadable_count': success_count,
        'failed_count': fail_count,
        'end_time': datetime.now().isoformat(),
        'elapsed_seconds': elapsed_time
    })
    
    # Save results
    save_results(results)
    
    # Print final summary
    print(f"\n{'='*70}")
    print(f"DOWNLOAD CHECK COMPLETE")
    print(f"{'='*70}")
    print(f"⏱️  Time elapsed: {elapsed_time:.1f} seconds")
    print(f"📊 Total URLs checked: {total_urls}")
    print(f"✅ Downloadable files: {success_count} ({success_count*100/total_urls:.1f}%)")
    print(f"❌ Failed/inaccessible: {fail_count} ({fail_count*100/total_urls:.1f}%)")
    print(f"💾 Results saved to: {CHECK_RESULTS_FILE}")
    
    if fail_count > 0:
        print(f"\n🔍 FAILED FILES ANALYSIS:")
        
        # Analyze failure types
        error_types = {}
        for url, fail_info in results['failed'].items():
            error = fail_info.get('error', 'unknown')
            if error.startswith('HTTP'):
                error_type = error
            else:
                error_type = error.split(':')[0] if ':' in error else error[:30]
            
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        print(f"   Error breakdown:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {error_type}: {count} files")
        
        # Show some example failed files
        print(f"\n   Sample failed files:")
        sample_failed = list(results['failed'].items())[:5]
        for url, fail_info in sample_failed:
            filename = fail_info.get('filename', 'unknown')
            error = fail_info.get('error', 'unknown')
            print(f"   - {filename}: {error}")
        
        if len(results['failed']) > 5:
            print(f"   ... and {len(results['failed']) - 5} more (see {CHECK_RESULTS_FILE})")

if __name__ == "__main__":
    main()