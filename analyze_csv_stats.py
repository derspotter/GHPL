#!/usr/bin/env python3
"""
Comprehensive statistics analysis for the GHPL CSV results.
"""

import pandas as pd
import numpy as np

def analyze_csv_statistics(csv_file):
    """Analyze comprehensive statistics from the CSV file."""
    
    print("=" * 80)
    print(f"📊 ANALYZING: {csv_file}")
    print("=" * 80)
    
    # Load the CSV
    df = pd.read_csv(csv_file)
    
    # Basic statistics
    print(f"\n📈 OVERALL STATISTICS")
    print("-" * 40)
    print(f"Total rows in CSV: {len(df)}")
    
    # Processing status
    processed = df['processed'].value_counts()
    print(f"\n🔄 PROCESSING STATUS:")
    print(f"  ✅ Successfully processed: {processed.get(True, 0)}")
    print(f"  ❌ Failed to process: {processed.get(False, 0)}")
    
    # Relevance assessment (Question 1a and 1b)
    q1a = df['question_1a_health_policy'].value_counts()
    q1b = df['question_1b_ghpl_categories'].value_counts()
    
    print(f"\n📋 RELEVANCE ASSESSMENT:")
    print(f"  Question 1a (Health Policy Related):")
    print(f"    ✅ True: {q1a.get(True, 0)}")
    print(f"    ❌ False: {q1a.get(False, 0)}")
    print(f"    ❓ Unknown/None: {df['question_1a_health_policy'].isna().sum()}")
    
    print(f"  Question 1b (Fits GHPL Categories):")
    print(f"    ✅ True: {q1b.get(True, 0)}")
    print(f"    ❌ False: {q1b.get(False, 0)}")
    print(f"    ❓ Unknown/None: {df['question_1b_ghpl_categories'].isna().sum()}")
    
    # Metadata extraction
    metadata_extracted = df['metadata_extracted'].value_counts()
    print(f"\n🎯 METADATA EXTRACTION:")
    print(f"  ✅ Metadata extracted: {metadata_extracted.get(True, 0)}")
    print(f"  ❌ No metadata: {metadata_extracted.get(False, 0)}")
    
    # Filter for rows with extracted metadata
    df_with_metadata = df[df['metadata_extracted'] == True]
    
    if len(df_with_metadata) > 0:
        print(f"\n📊 METADATA QUALITY METRICS (n={len(df_with_metadata)}):")
        print("-" * 40)
        
        # Overall confidence statistics
        confidence = df_with_metadata['overall_confidence'].dropna()
        if len(confidence) > 0:
            print(f"\n  Overall Confidence:")
            print(f"    Mean: {confidence.mean():.3f}")
            print(f"    Median: {confidence.median():.3f}")
            print(f"    Min: {confidence.min():.3f}")
            print(f"    Max: {confidence.max():.3f}")
            print(f"    Std Dev: {confidence.std():.3f}")
            
            # Confidence distribution
            print(f"    Distribution:")
            print(f"      >= 0.9: {(confidence >= 0.9).sum()} ({(confidence >= 0.9).sum()/len(confidence)*100:.1f}%)")
            print(f"      0.8-0.9: {((confidence >= 0.8) & (confidence < 0.9)).sum()} ({((confidence >= 0.8) & (confidence < 0.9)).sum()/len(confidence)*100:.1f}%)")
            print(f"      0.7-0.8: {((confidence >= 0.7) & (confidence < 0.8)).sum()} ({((confidence >= 0.7) & (confidence < 0.8)).sum()/len(confidence)*100:.1f}%)")
            print(f"      < 0.7: {(confidence < 0.7).sum()} ({(confidence < 0.7).sum()/len(confidence)*100:.1f}%)")
        
        # Metadata completeness statistics
        completeness = df_with_metadata['metadata_completeness'].dropna()
        if len(completeness) > 0:
            print(f"\n  Metadata Completeness:")
            print(f"    Mean: {completeness.mean():.3f} ({completeness.mean()*100:.1f}%)")
            print(f"    Median: {completeness.median():.3f} ({completeness.median()*100:.1f}%)")
            print(f"    Min: {completeness.min():.3f} ({completeness.min()*100:.1f}%)")
            print(f"    Max: {completeness.max():.3f} ({completeness.max()*100:.1f}%)")
            print(f"    Std Dev: {completeness.std():.3f}")
            
            # Completeness distribution
            print(f"    Distribution:")
            print(f"      100% complete: {(completeness == 1.0).sum()} ({(completeness == 1.0).sum()/len(completeness)*100:.1f}%)")
            print(f"      >= 75% complete: {(completeness >= 0.75).sum()} ({(completeness >= 0.75).sum()/len(completeness)*100:.1f}%)")
            print(f"      50-75% complete: {((completeness >= 0.5) & (completeness < 0.75)).sum()} ({((completeness >= 0.5) & (completeness < 0.75)).sum()/len(completeness)*100:.1f}%)")
            print(f"      < 50% complete: {(completeness < 0.5).sum()} ({(completeness < 0.5).sum()/len(completeness)*100:.1f}%)")
        
        # Field completeness analysis
        print(f"\n  Field-by-Field Completeness:")
        metadata_fields = ['title', 'doc_type', 'health_topic', 'creator', 
                          'year', 'country', 'language', 'governance_level']
        
        for field in metadata_fields:
            if field in df_with_metadata.columns:
                non_empty = df_with_metadata[field].notna() & (df_with_metadata[field] != '')
                count = non_empty.sum()
                pct = count / len(df_with_metadata) * 100
                print(f"    {field:20s}: {count:4d} / {len(df_with_metadata)} ({pct:5.1f}%)")
        
        # Document type distribution (if available)
        if 'doc_type' in df_with_metadata.columns:
            doc_types = df_with_metadata['doc_type'].value_counts()
            if len(doc_types) > 0:
                print(f"\n  Document Type Distribution:")
                for doc_type, count in doc_types.head(10).items():
                    if doc_type and str(doc_type) != 'nan' and str(doc_type) != '':
                        print(f"    {str(doc_type):30s}: {count:4d} ({count/len(df_with_metadata)*100:5.1f}%)")
        
        # Health topic distribution
        if 'health_topic' in df_with_metadata.columns:
            topics = df_with_metadata['health_topic'].value_counts()
            if len(topics) > 0:
                print(f"\n  Health Topic Distribution:")
                for topic, count in topics.head(10).items():
                    if topic and str(topic) != 'nan' and str(topic) != '':
                        print(f"    {str(topic):30s}: {count:4d} ({count/len(df_with_metadata)*100:5.1f}%)")
    
    # Processing time statistics
    proc_times = df['processing_time_seconds'].dropna()
    if len(proc_times) > 0:
        print(f"\n⏱️ PROCESSING TIME:")
        print(f"  Mean: {proc_times.mean():.1f} seconds")
        print(f"  Median: {proc_times.median():.1f} seconds")
        print(f"  Total: {proc_times.sum()/60:.1f} minutes")
    
    # Summary
    print(f"\n" + "=" * 80)
    print(f"📌 SUMMARY:")
    print(f"  Total documents processed: {len(df)}")
    print(f"  Documents passing Q1a (health policy): {q1a.get(True, 0)} ({q1a.get(True, 0)/len(df)*100:.1f}%)")
    print(f"  Documents passing Q1b (GHPL category): {q1b.get(True, 0)} ({q1b.get(True, 0)/len(df)*100:.1f}%)")
    print(f"  Documents with metadata extracted: {metadata_extracted.get(True, 0)} ({metadata_extracted.get(True, 0)/len(df)*100:.1f}%)")
    
    if len(df_with_metadata) > 0:
        high_quality = df_with_metadata[
            (df_with_metadata['overall_confidence'] >= 0.8) & 
            (df_with_metadata['metadata_completeness'] >= 0.75)
        ]
        print(f"  High-quality extractions (>80% conf, >75% complete): {len(high_quality)} ({len(high_quality)/len(df)*100:.1f}%)")
    
    print("=" * 80)

if __name__ == "__main__":
    import sys
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'meta_gpt5_results_20250810_190823_repaired.csv'
    analyze_csv_statistics(csv_file)