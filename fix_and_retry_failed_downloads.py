#!/usr/bin/env python3
"""
Attempt to fix and retry failed downloads with various URL transformation strategies.
"""

import json
import requests
import time
from datetime import datetime
from urllib.parse import urlparse, unquote, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

FAILED_DOWNLOADS_FILE = 'failed_downloads.json'
RETRY_RESULTS_FILE = 'retry_download_results.json'
MAX_WORKERS = 5  # Lower to be gentler on servers

results_lock = threading.Lock()

def load_failed_downloads():
    """Load failed downloads from file"""
    with open(FAILED_DOWNLOADS_FILE, 'r') as f:
        return json.load(f)

def save_retry_results(results):
    """Save retry results to file"""
    with open(RETRY_RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

def url_fix_strategies(original_url):
    """
    Generate various URL fix strategies for a failed URL.
    Returns list of (strategy_name, fixed_url) tuples.
    """
    strategies = []
    parsed = urlparse(original_url)
    
    # Strategy 1: Original URL (baseline)
    strategies.append(("original", original_url))
    
    # Strategy 2: Double URL decode (in case of double encoding)
    try:
        double_decoded = unquote(unquote(original_url))
        if double_decoded != original_url:
            strategies.append(("double_decode", double_decoded))
    except:
        pass
    
    # Strategy 3: Re-encode the path part properly
    try:
        path_parts = parsed.path.split('/')
        re_encoded_parts = []
        for part in path_parts:
            if part:
                # Decode then re-encode to normalize
                decoded_part = unquote(part)
                encoded_part = quote(decoded_part, safe='')
                re_encoded_parts.append(encoded_part)
            else:
                re_encoded_parts.append(part)
        
        new_path = '/'.join(re_encoded_parts)
        new_url = f"{parsed.scheme}://{parsed.netloc}{new_path}"
        if new_url != original_url:
            strategies.append(("re_encode", new_url))
    except:
        pass
    
    # Strategy 4: Try with different encoding of spaces and special chars
    try:
        # Replace %20 with + (some servers prefer this)
        plus_encoded = original_url.replace('%20', '+')
        if plus_encoded != original_url:
            strategies.append(("plus_spaces", plus_encoded))
    except:
        pass
    
    # Strategy 5: Try completely decoded URL (no percent encoding)
    try:
        fully_decoded = unquote(original_url)
        if fully_decoded != original_url:
            strategies.append(("fully_decoded", fully_decoded))
    except:
        pass
    
    # Strategy 6: Replace common problem characters
    try:
        cleaned_url = original_url
        # Replace problematic sequences
        replacements = {
            '%2C': ',',
            '%28': '(',
            '%29': ')',
            '%5F': '_',
            '%2E': '.',
            '%2D': '-'
        }
        
        for old, new in replacements.items():
            cleaned_url = cleaned_url.replace(old, new)
        
        if cleaned_url != original_url:
            strategies.append(("char_replace", cleaned_url))
    except:
        pass
    
    # Strategy 7: Try with different path structure (remove middle path components)
    try:
        # Extract just the filename and try direct access
        filename = parsed.path.split('/')[-1]
        if filename:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            # Try direct access to doc-files container
            direct_url = f"{base_url}/doc-files/{filename}"
            strategies.append(("direct_access", direct_url))
            
            # Try different container path
            alt_container_url = f"{base_url}/documents/{filename}"
            strategies.append(("alt_container", alt_container_url))
    except:
        pass
    
    return strategies

def test_url_accessibility(url, timeout=10):
    """
    Test if a URL is accessible using HEAD request.
    Returns (accessible, status_code, content_length, error)
    """
    try:
        # Try HEAD request first
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code in [200, 206]:
            content_length = response.headers.get('content-length', 'unknown')
            return True, response.status_code, content_length, None
        
        # If HEAD fails, try GET with minimal range
        if response.status_code == 405:  # Method not allowed
            headers = {'Range': 'bytes=0-0'}
            response = requests.get(url, timeout=timeout, headers=headers, stream=True)
            if response.status_code in [200, 206, 416]:  # 416 = Range Not Satisfiable but file exists
                content_length = response.headers.get('content-length', 'unknown')
                return True, response.status_code, content_length, None
        
        return False, response.status_code, None, f"HTTP {response.status_code}"
        
    except requests.exceptions.RequestException as e:
        return False, 'error', None, str(e)

def retry_failed_download(original_url, file_info, results, thread_id=0):
    """
    Try multiple strategies to fix and retry a failed download.
    
    Args:
        original_url: The original failed URL
        file_info: File information from failed downloads
        results: Results tracking dictionary
        thread_id: Thread identifier for logging
    """
    filename = file_info.get('filename', 'unknown')
    doc_id = file_info.get('doc_id', 'unknown')
    
    print(f"[T{thread_id:02d}] Retrying: {filename} [ID: {doc_id}]")
    
    # Generate fix strategies
    strategies = url_fix_strategies(original_url)
    
    success_found = False
    strategy_results = []
    
    for strategy_name, test_url in strategies:
        if success_found:
            break
            
        print(f"[T{thread_id:02d}]   Testing {strategy_name}: {test_url[:80]}...")
        
        accessible, status_code, content_length, error = test_url_accessibility(test_url)
        
        strategy_result = {
            'strategy': strategy_name,
            'url': test_url,
            'accessible': accessible,
            'status_code': status_code,
            'content_length': content_length,
            'error': error
        }
        strategy_results.append(strategy_result)
        
        if accessible:
            print(f"[T{thread_id:02d}]   ✓ SUCCESS with {strategy_name}! ({content_length} bytes)")
            success_found = True
            break
        else:
            print(f"[T{thread_id:02d}]   ✗ Failed: {error}")
        
        # Small delay between attempts
        time.sleep(0.1)
    
    # Store results
    with results_lock:
        results['retry_attempts'][original_url] = {
            'filename': filename,
            'doc_id': doc_id,
            'original_url': original_url,
            'strategies_tested': strategy_results,
            'fixed': success_found,
            'working_url': test_url if success_found else None,
            'working_strategy': strategy_name if success_found else None,
            'timestamp': datetime.now().isoformat()
        }
        
        if success_found:
            results['summary']['fixed_count'] += 1
        else:
            results['summary']['still_failed_count'] += 1
    
    return success_found, test_url if success_found else None

def main():
    """Main retry function"""
    print(f"\n{'='*70}")
    print("FIXING AND RETRYING FAILED DOWNLOADS")
    print(f"{'='*70}\n")
    
    # Load failed downloads
    print(f"📊 Loading failed downloads from: {FAILED_DOWNLOADS_FILE}")
    failed_data = load_failed_downloads()
    failed_urls = failed_data['failed_urls']
    
    print(f"🔄 Found {len(failed_urls)} failed URLs to retry")
    
    # Initialize results tracking
    results = {
        'retry_attempts': {},
        'summary': {
            'total_retried': len(failed_urls),
            'fixed_count': 0,
            'still_failed_count': 0,
            'start_time': datetime.now().isoformat()
        }
    }
    
    # Retry downloads with thread pool
    print(f"\n🚀 Starting retry with {MAX_WORKERS} workers...\n")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all retry tasks
        future_to_url = {
            executor.submit(retry_failed_download, url, file_info, results, i % MAX_WORKERS): url
            for i, (url, file_info) in enumerate(failed_urls.items())
        }
        
        # Process completed retries
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                success, working_url = future.result()
                # Progress is printed by the worker function
            except Exception as e:
                print(f"❌ Unexpected error for {url}: {e}")
                with results_lock:
                    results['summary']['still_failed_count'] += 1
    
    # Final results
    elapsed_time = time.time() - start_time
    results['summary']['end_time'] = datetime.now().isoformat()
    results['summary']['elapsed_seconds'] = elapsed_time
    
    # Save results
    save_retry_results(results)
    
    # Print summary
    fixed_count = results['summary']['fixed_count']
    still_failed_count = results['summary']['still_failed_count']
    total_retried = results['summary']['total_retried']
    
    print(f"\n{'='*70}")
    print(f"RETRY COMPLETE")
    print(f"{'='*70}")
    print(f"⏱️  Time elapsed: {elapsed_time:.1f} seconds")
    print(f"📊 Total URLs retried: {total_retried}")
    print(f"✅ Successfully fixed: {fixed_count} ({fixed_count*100/total_retried:.1f}%)")
    print(f"❌ Still failed: {still_failed_count} ({still_failed_count*100/total_retried:.1f}%)")
    print(f"💾 Results saved to: {RETRY_RESULTS_FILE}")
    
    if fixed_count > 0:
        print(f"\n🎉 RECOVERED FILES:")
        for url, attempt in results['retry_attempts'].items():
            if attempt['fixed']:
                filename = attempt['filename']
                strategy = attempt['working_strategy']
                working_url = attempt['working_url']
                print(f"   ✓ {filename}")
                print(f"     Strategy: {strategy}")
                print(f"     Working URL: {working_url}")
                print()

if __name__ == "__main__":
    main()