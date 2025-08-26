#!/usr/bin/env python3
"""
Analyze metadata completeness from the GPT-5 results CSV file.
Shows which fields are missing most often and provides detailed statistics.
"""

import pandas as pd
import sys
from pathlib import Path

def analyze_metadata_completeness(csv_file):
    """Analyze metadata completeness from the results CSV."""
    
    # Read the CSV file
    try:
        df = pd.read_csv(csv_file)
        print(f"📊 Analyzing metadata completeness from: {csv_file}")
        print(f"📄 Total documents: {len(df)}")
        print()
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return
    
    # Filter to only documents with metadata extracted
    extracted_df = df[df['metadata_extracted'] == True]
    print(f"🔍 Documents with metadata extracted: {len(extracted_df)}")
    print()
    
    if len(extracted_df) == 0:
        print("No documents with extracted metadata found.")
        return
    
    # Define the metadata fields to analyze
    metadata_fields = [
        'title', 'doc_type', 'health_topic', 'creator', 
        'year', 'country', 'language', 'governance_level'
    ]
    
    print("=" * 80)
    print("📋 METADATA FIELD COMPLETENESS ANALYSIS")
    print("=" * 80)
    
    # Analyze completeness for each field
    field_stats = []
    
    for field in metadata_fields:
        if field in extracted_df.columns:
            # Count non-empty values (not NaN, not empty string, not None)
            non_empty = extracted_df[field].notna() & (extracted_df[field] != '') & (extracted_df[field] != 'None')
            filled_count = non_empty.sum()
            total_count = len(extracted_df)
            completeness = (filled_count / total_count) * 100
            
            field_stats.append({
                'field': field,
                'filled': filled_count,
                'total': total_count,
                'completeness': completeness,
                'missing': total_count - filled_count
            })
            
            print(f"{field:20} | {filled_count:2}/{total_count:2} ({completeness:5.1f}%) | Missing: {total_count - filled_count}")
        else:
            print(f"{field:20} | Field not found in CSV")
    
    print()
    print("=" * 80)
    print("📉 FIELDS RANKED BY MISSING DATA (Most Problematic First)")
    print("=" * 80)
    
    # Sort by missing count (descending) then by completeness (ascending)
    field_stats.sort(key=lambda x: (-x['missing'], x['completeness']))
    
    for i, stats in enumerate(field_stats, 1):
        status = "🔴" if stats['completeness'] < 50 else "🟡" if stats['completeness'] < 90 else "🟢"
        print(f"{i}. {status} {stats['field']:20} | Missing {stats['missing']:2} documents ({100-stats['completeness']:5.1f}% empty)")
    
    print()
    print("=" * 80)
    print("📈 OVERALL COMPLETENESS DISTRIBUTION")
    print("=" * 80)
    
    # Analyze overall completeness scores
    completeness_scores = extracted_df['metadata_completeness'].dropna()
    if len(completeness_scores) > 0:
        print(f"Average completeness: {completeness_scores.mean():.1%}")
        print(f"Median completeness:  {completeness_scores.median():.1%}")
        print(f"Min completeness:     {completeness_scores.min():.1%}")
        print(f"Max completeness:     {completeness_scores.max():.1%}")
        print()
        
        # Distribution breakdown
        completeness_counts = completeness_scores.value_counts().sort_index()
        print("Completeness distribution:")
        for score, count in completeness_counts.items():
            bar = "█" * min(20, int(count * 20 / len(extracted_df)))
            print(f"  {score:5.1%}: {count:2} documents {bar}")
    
    print()
    print("=" * 80)
    print("🔍 SAMPLE DOCUMENTS BY COMPLETENESS LEVEL")
    print("=" * 80)
    
    # Show examples of documents at different completeness levels
    for completeness in sorted(extracted_df['metadata_completeness'].dropna().unique(), reverse=True):
        sample_docs = extracted_df[extracted_df['metadata_completeness'] == completeness]['filename'].head(3).tolist()
        print(f"{completeness:5.1%} complete ({len(extracted_df[extracted_df['metadata_completeness'] == completeness])} docs):")
        for doc in sample_docs:
            print(f"  • {doc}")
        print()
    
    print("=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)
    
    # Provide recommendations based on analysis
    most_missing = field_stats[0] if field_stats else None
    if most_missing and most_missing['completeness'] < 50:
        print(f"🔴 HIGH PRIORITY: Fix '{most_missing['field']}' field mapping")
        print(f"   This field is missing in {most_missing['missing']}/{most_missing['total']} documents ({100-most_missing['completeness']:.1f}%)")
        print()
    
    # Check for systematic issues
    very_empty_fields = [f for f in field_stats if f['completeness'] < 20]
    if very_empty_fields:
        print("🔧 LIKELY FIELD MAPPING ISSUES:")
        for field_info in very_empty_fields:
            print(f"   • '{field_info['field']}' field appears to have a mapping problem")
        print("   → Check if the field names in the CSV extraction match the metadata object structure")
        print()
    
    if extracted_df['metadata_completeness'].mean() < 0.9:
        print("📋 EXTRACTION IMPROVEMENT NEEDED:")
        print("   • Average completeness is below 90%")
        print("   • Review the metadata extraction prompt to ensure all fields are being populated")
        print("   • Consider adding field validation or fallback values")

def main():
    """Main function."""
    # Default to the most recent results file
    default_file = "meta_gpt5_results_20250825_170822.csv"
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = default_file
    
    if not Path(csv_file).exists():
        print(f"❌ File not found: {csv_file}")
        print(f"Usage: {sys.argv[0]} [csv_file]")
        print(f"   or: {sys.argv[0]}  (uses {default_file})")
        sys.exit(1)
    
    analyze_metadata_completeness(csv_file)

if __name__ == "__main__":
    main()