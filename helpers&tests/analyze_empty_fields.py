#!/usr/bin/env python3
"""
Analyze which fields are empty in the CSV to understand the pattern.
"""

import pandas as pd

def analyze_empty_fields():
    csv_file = "/home/jay/GHPL/meta_gpt5_results_20250825_170822.csv"
    
    try:
        df = pd.read_csv(csv_file)
        print(f"📊 Analyzing: {csv_file}")
        print(f"📄 Total rows: {len(df)}")
        print()
        
        # Filter to only documents with metadata extracted
        extracted_df = df[df['metadata_extracted'] == True]
        print(f"🔍 Rows with metadata_extracted=True: {len(extracted_df)}")
        
        if len(extracted_df) == 0:
            print("❌ No documents with extracted metadata found")
            return
            
        print()
        print("=" * 80)
        print("📋 FIELD ANALYSIS FOR EXTRACTED METADATA")
        print("=" * 80)
        
        # Check each metadata field
        metadata_fields = ['title', 'doc_type', 'health_topic', 'creator', 'year', 'country', 'language', 'governance_level']
        
        for field in metadata_fields:
            if field in extracted_df.columns:
                # Count non-empty values
                non_empty = extracted_df[field].notna() & (extracted_df[field] != '') & (extracted_df[field] != 'None')
                filled_count = non_empty.sum()
                total_count = len(extracted_df)
                percentage = (filled_count / total_count) * 100
                
                status = "✅" if percentage > 80 else "⚠️" if percentage > 0 else "❌"
                print(f"{status} {field:15} | {filled_count:2}/{total_count:2} ({percentage:5.1f}%)")
                
                # Show examples of values if any exist
                if filled_count > 0:
                    unique_values = extracted_df[field].dropna()
                    unique_values = unique_values[unique_values != '']
                    unique_values = unique_values[unique_values != 'None']
                    if len(unique_values) > 0:
                        sample_values = unique_values.unique()[:3]  # Show first 3 unique values
                        print(f"                   Examples: {', '.join(map(str, sample_values))}")
                print()
        
        print("=" * 80)
        print("🔍 SAMPLE EXTRACTED DOCUMENTS")
        print("=" * 80)
        
        # Show first few extracted documents with their field values
        for i, (idx, row) in enumerate(extracted_df.head(5).iterrows()):
            print(f"\n{i+1}. {row['filename']}")
            for field in metadata_fields:
                if field in row:
                    value = row[field]
                    if pd.isna(value) or value == '' or value == 'None':
                        print(f"   {field:15}: [EMPTY]")
                    else:
                        print(f"   {field:15}: {value}")
        
        print("\n" + "=" * 80)
        print("📈 SUMMARY")
        print("=" * 80)
        
        # Count completely empty classification fields
        problem_fields = []
        for field in ['doc_type', 'health_topic', 'creator']:
            if field in extracted_df.columns:
                non_empty = extracted_df[field].notna() & (extracted_df[field] != '') & (extracted_df[field] != 'None')
                if non_empty.sum() == 0:
                    problem_fields.append(field)
        
        if problem_fields:
            print(f"🔴 CRITICAL ISSUE: These fields are 100% empty: {', '.join(problem_fields)}")
            print("   This indicates a field mapping or extraction bug.")
        else:
            print("✅ All classification fields have some data")
            
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")

if __name__ == "__main__":
    analyze_empty_fields()