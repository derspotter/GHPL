#!/usr/bin/env python3
"""
Script to match filenames from meta_gpt5_results.csv to URLs in documents-info.xlsx
"""

import pandas as pd
import os
from urllib.parse import unquote, urlparse

def extract_filename_from_url(url):
    """Extract filename from URL, handling URL encoding"""
    if pd.isna(url) or url == '':
        return None
    
    # Parse the URL and get the path
    parsed = urlparse(str(url))
    path = parsed.path
    
    # Get the last part of the path
    filename = os.path.basename(path)
    
    # Decode URL encoding
    filename = unquote(filename)
    
    # Clean up any query parameters
    if '?' in filename:
        filename = filename.split('?')[0]
    
    return filename if filename else None

def get_filename_without_extension(filename):
    """Get filename without extension"""
    if not filename:
        return None
    # Remove extension
    name = os.path.splitext(filename)[0]
    return name

def normalize_filename(filename):
    """Normalize filename for matching - returns base name without extension"""
    if not filename:
        return None
    
    # Get base name without extension
    base_name = get_filename_without_extension(filename)
    
    # Convert to lowercase for case-insensitive matching
    base_name = base_name.lower()
    
    # Replace spaces and underscores with hyphens for consistency
    base_name = base_name.replace(' ', '-')
    base_name = base_name.replace('_', '-')
    
    # Remove %20 and other common URL encodings that might remain
    base_name = base_name.replace('%20', '-')
    
    return base_name

def main():
    # Load the data
    print("Loading data files...")
    csv_df = pd.read_csv('meta_gpt5_results.csv')
    excel_df = pd.read_excel('documents-info.xlsx')
    
    print(f"Loaded {len(csv_df)} rows from CSV")
    print(f"Loaded {len(excel_df)} rows from Excel")
    
    # Extract filenames from Excel URLs
    print("\nExtracting filenames from Excel URLs...")
    excel_df['extracted_filename'] = excel_df['public_file_url'].apply(extract_filename_from_url)
    excel_df['normalized_filename'] = excel_df['extracted_filename'].apply(normalize_filename)
    
    # Normalize CSV filenames
    print("Normalizing CSV filenames...")
    csv_df['normalized_filename'] = csv_df['filename'].apply(normalize_filename)
    
    # Create a mapping dictionary from normalized filename to Excel row
    print("\nCreating filename mapping...")
    excel_mapping = {}
    for idx, row in excel_df.iterrows():
        if row['normalized_filename']:
            if row['normalized_filename'] not in excel_mapping:
                excel_mapping[row['normalized_filename']] = []
            excel_mapping[row['normalized_filename']].append(idx)
    
    # Match CSV files to Excel entries
    print("\nMatching files...")
    matches = []
    unmatched = []
    
    for idx, csv_row in csv_df.iterrows():
        csv_filename = csv_row['filename']
        normalized = csv_row['normalized_filename']
        
        if normalized and normalized in excel_mapping:
            # Found match(es)
            for excel_idx in excel_mapping[normalized]:
                excel_row = excel_df.iloc[excel_idx]
                matches.append({
                    'csv_filename': csv_filename,
                    'excel_id': excel_row['id'],
                    'excel_title': excel_row['title'],
                    'excel_url': excel_row['public_file_url'],
                    'excel_country': excel_row['country'],
                    'excel_year': excel_row['year'],
                    'excel_doc_type': excel_row['doc_type'],
                    'csv_doc_type': csv_row['doc_type'],
                    'csv_title': csv_row['title'],
                    'csv_country': csv_row['country'],
                    'csv_year': csv_row['year']
                })
        else:
            unmatched.append({
                'filename': csv_filename,
                'title': csv_row['title'],
                'doc_type': csv_row['doc_type']
            })
    
    # Create results DataFrames
    matches_df = pd.DataFrame(matches)
    unmatched_df = pd.DataFrame(unmatched)
    
    # Save results
    print(f"\nFound {len(matches_df)} matches")
    print(f"Found {len(unmatched_df)} unmatched files")
    
    # Save to Excel with multiple sheets
    with pd.ExcelWriter('matched_results.xlsx', engine='openpyxl') as writer:
        matches_df.to_excel(writer, sheet_name='Matched Files', index=False)
        unmatched_df.to_excel(writer, sheet_name='Unmatched Files', index=False)
        
        # Add summary sheet
        summary_data = {
            'Metric': ['Total CSV Files', 'Matched Files', 'Unmatched Files', 'Match Rate'],
            'Value': [
                len(csv_df),
                len(matches_df),
                len(unmatched_df),
                f"{(len(matches_df) / len(csv_df) * 100):.1f}%" if len(csv_df) > 0 else "0%"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print("\nResults saved to 'matched_results.xlsx'")
    
    # Show sample matches
    if len(matches_df) > 0:
        print("\nSample matches:")
        for i in range(min(5, len(matches_df))):
            row = matches_df.iloc[i]
            print(f"  {row['csv_filename']} -> {row['excel_url']}")
    
    # Show sample unmatched
    if len(unmatched_df) > 0:
        print("\nSample unmatched files:")
        for i in range(min(5, len(unmatched_df))):
            row = unmatched_df.iloc[i]
            print(f"  {row['filename']}")

if __name__ == "__main__":
    main()