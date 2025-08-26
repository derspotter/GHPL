#!/usr/bin/env python3
"""
Test script to download failed URLs from Azure Blob Storage
with the fix for %20 encoding issue.

The issue: Azure Blob Storage treats file names literally, so files
with "%20" in their actual filename need "%2520" in the URL
(since %25 is the encoding for %).
"""

import requests
import os
from pathlib import Path
import time

def fix_azure_url(url):
    """
    Fix Azure Blob Storage URL encoding issue.
    Replace %20 with %2520 to match literal "%20" in filenames.
    """
    # Only apply fix to Azure blob storage URLs
    if 'blob.core.windows.net' in url:
        fixed_url = url.replace('%20', '%2520')
        return fixed_url
    return url

def download_with_fix(url, output_dir='test_downloads'):
    """
    Try to download a file with the Azure encoding fix.
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract filename from URL (before fixing)
    filename = url.split('/')[-1]
    # Decode the filename for local storage
    filename = requests.utils.unquote(filename)
    output_path = os.path.join(output_dir, filename)
    
    print(f"\n{'='*60}")
    print(f"Original URL: {url[:100]}...")
    
    # Try original URL first
    try:
        print("Trying original URL...")
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            file_size = len(response.content) / 1024  # KB
            print(f"✅ SUCCESS with original URL!")
            print(f"   Downloaded: {filename}")
            print(f"   Size: {file_size:.1f} KB")
            return True
        else:
            print(f"❌ Failed with original URL: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error with original URL: {str(e)[:100]}")
    
    # Try fixed URL
    fixed_url = fix_azure_url(url)
    if fixed_url != url:
        try:
            print(f"\nFixed URL: {fixed_url[:100]}...")
            print("Trying fixed URL...")
            response = requests.get(fixed_url, timeout=30)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                file_size = len(response.content) / 1024  # KB
                print(f"✅ SUCCESS with fixed URL!")
                print(f"   Downloaded: {filename}")
                print(f"   Size: {file_size:.1f} KB")
                return True
            else:
                print(f"❌ Failed with fixed URL: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Error with fixed URL: {str(e)[:100]}")
    
    print(f"❌ FAILED to download: {filename}")
    return False

def main():
    """
    Test downloading 5 URLs from failed_downloads.txt with the Azure fix.
    """
    print("Azure Blob Storage URL Fix Test")
    print("="*60)
    
    # Read failed URLs
    failed_urls_file = 'failed_downloads.txt'
    if not os.path.exists(failed_urls_file):
        print(f"Error: {failed_urls_file} not found!")
        return
    
    with open(failed_urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(urls)} failed URLs")
    print(f"Testing first 5 URLs with the %20 -> %2520 fix...")
    
    # Test first 5 URLs
    test_urls = urls[:5]
    results = {'success': 0, 'failed': 0}
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n[{i}/5] Processing...")
        success = download_with_fix(url)
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
        
        # Small delay to be nice to the server
        time.sleep(1)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successful downloads: {results['success']}/5")
    print(f"❌ Failed downloads: {results['failed']}/5")
    
    if results['success'] > 0:
        print(f"\n🎉 The Azure fix worked for {results['success']} file(s)!")
        print("The issue was confirmed: Azure stores '%20' literally in filenames")
        print("Fix: Replace %20 with %2520 in URLs")

if __name__ == "__main__":
    main()