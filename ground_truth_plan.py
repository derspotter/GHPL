"""
Ground Truth Validation Implementation Plan

Based on analysis of documents-info.xlsx:
- 2,725 documents with 22 columns
- Core metadata fields match our extraction fields
- Multiple title sources available for validation
- Missing 'level' field (governance level) - will be ignored in comparison
"""

import pandas as pd
from pathlib import Path
from urllib.parse import urlparse

def load_ground_truth_metadata(excel_path: str) -> dict:
    """Load reference metadata from Excel file."""
    df = pd.read_excel(excel_path)
    
    # Create lookup dictionary keyed by filename extracted from public_file_url
    ground_truth = {}
    
    for _, row in df.iterrows():
        # Extract filename from public_file_url
        if pd.notna(row['public_file_url']):
            url_path = urlparse(row['public_file_url']).path
            filename = Path(url_path).stem  # Remove .pdf extension
            
            # Create ground truth entry
            ground_truth[filename] = {
                'id': row.get('id'),
                'doc_type': row.get('doc_type'),
                'health_topic': row.get('health_topic'), 
                'country': row.get('country'),
                'language': row.get('language'),
                'creator': row.get('creator'),
                'year': int(row.get('year')) if pd.notna(row.get('year')) else None,
                'title': row.get('title'),
                # Alternative titles for validation
                'alternative_titles': [
                    row.get('article_title'),
                    row.get('pdf_title'),
                    row.get('ocr_title')
                ],
                'public_file_url': row.get('public_file_url')
            }
    
    print(f"Loaded ground truth data for {len(ground_truth)} documents")
    return ground_truth

# Field mapping between our extraction and Excel columns
FIELD_MAPPING = {
    'doc_type': 'doc_type',      # Direct match
    'health_topic': 'health_topic',  # Direct match  
    'country': 'country',        # Direct match
    'language': 'language',      # Direct match
    'creator': 'creator',        # Direct match
    'year': 'year',             # Direct match
    'title': 'title',           # Direct match
    # 'level': None              # Not available in Excel - skip comparison
}

# Expected enum values for validation
EXPECTED_VALUES = {
    'doc_type': ['Policy', 'Law', 'Health Strategy', 'Control Plan', 'Action Plan', 'Health Guideline'],
    'health_topic': ['Cancer', 'Non-Communicable Disease', 'Cardiovascular Health'],
    'creator': ['Parliament', 'Ministry', 'Agency', 'Foundation', 'Association', 'Society'],
    'country': None,  # Free text
    'language': None, # Free text  
    'year': None,     # Numeric
    'title': None     # Free text
}

def analyze_excel_values():
    """Analyze actual values in Excel to compare with our enums."""
    df = pd.read_excel("/home/justus/Nextcloud/GHPL/documents-info.xlsx")
    
    print("=== Excel Values vs Our Enums ===")
    
    for field, expected in EXPECTED_VALUES.items():
        if expected and field in df.columns:
            actual_values = df[field].dropna().unique()
            print(f"\n{field.upper()}:")
            print(f"  Expected: {expected}")
            print(f"  Actual in Excel: {sorted(actual_values)}")
            
            # Check for mismatches
            unexpected = set(actual_values) - set(expected)
            if unexpected:
                print(f"  ⚠️  Unexpected values: {sorted(unexpected)}")
            
            missing = set(expected) - set(actual_values) 
            if missing:
                print(f"  ℹ️  Missing from Excel: {sorted(missing)}")

if __name__ == "__main__":
    analyze_excel_values()