#!/usr/bin/env python3
import pandas as pd
import requests
import os
from urllib.parse import urlparse, unquote
import time

def download_file(url, folder):
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
            parsed_url = urlparse(url)
            filename = os.path.basename(unquote(parsed_url.path))
            if not filename or filename == '':
                filename = f'document_{hash(url)}'
        
        filepath = os.path.join(folder, filename)
        
        # Handle duplicate filenames
        base, ext = os.path.splitext(filepath)
        counter = 1
        while os.path.exists(filepath):
            filepath = f"{base}_{counter}{ext}"
            counter += 1
        
        # Download the file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"✓ Downloaded: {filename}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to download {url}: {str(e)}")
        return False

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
    
    # Get all URLs from column 'public_file_url'
    urls = df['public_file_url'].dropna().tolist()
    print(f"Found {len(urls)} URLs to download")
    
    # Download each file
    success_count = 0
    for i, url in enumerate(urls, 1):
        print(f"\nDownloading {i}/{len(urls)}: {url}")
        if download_file(str(url).strip(), 'docs'):
            success_count += 1
        time.sleep(1)  # Be polite to servers
    
    print(f"\n{'='*50}")
    print(f"Download complete: {success_count}/{len(urls)} files downloaded successfully")

if __name__ == "__main__":
    main()