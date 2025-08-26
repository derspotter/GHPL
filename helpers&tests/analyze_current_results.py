#!/usr/bin/env python3
"""
Quick analysis of the current meta_gpt5_results CSV file to check extraction quality.
"""

import pandas as pd
import json
from pathlib import Path

def analyze_current_results(csv_file):
    """Analyze the current results from the running GPT-5 extraction."""
    print(f"📊 Analyzing current results from: {csv_file}")
    
    # Load the CSV
    df = pd.read_csv(csv_file)
    total_files = len(df)
    
    print(f"\n📈 PROCESSING PROGRESS:")
    print(f"  ├─ Files processed: {total_files}")
    print(f"  ├─ All successfully processed: {df['processed'].all()}")
    print(f"  └─ Average processing time: {df['processing_time_seconds'].mean():.1f} seconds")
    
    # Question 1A Analysis (Health Policy Related)
    q1a_true = df['question_1a_health_policy'].sum()
    q1a_false = len(df) - q1a_true
    q1a_avg_conf = df['question_1a_confidence'].mean()
    
    print(f"\n❓ QUESTION 1A: Health Policy Related")
    print(f"  ├─ YES (from authoritative health source): {q1a_true} ({q1a_true/total_files*100:.1f}%)")
    print(f"  ├─ NO (not authoritative): {q1a_false} ({q1a_false/total_files*100:.1f}%)")
    print(f"  └─ Average confidence: {q1a_avg_conf:.3f}")
    
    # Question 1B Analysis (GHPL Categories)
    q1b_true = df['question_1b_ghpl_categories'].sum()
    q1b_false = len(df) - q1b_true
    q1b_avg_conf = df['question_1b_confidence'].mean()
    
    print(f"\n❓ QUESTION 1B: Fits GHPL Categories")
    print(f"  ├─ YES (fits GHPL categories): {q1b_true} ({q1b_true/total_files*100:.1f}%)")
    print(f"  ├─ NO (doesn't fit categories): {q1b_false} ({q1b_false/total_files*100:.1f}%)")
    print(f"  └─ Average confidence: {q1b_avg_conf:.3f}")
    
    # Overall Acceptance Rate
    both_true = df['question_1a_health_policy'] & df['question_1b_ghpl_categories']
    accepted_for_metadata = both_true.sum()
    metadata_extracted = df['metadata_extracted'].sum()
    
    print(f"\n✅ ACCEPTANCE ANALYSIS:")
    print(f"  ├─ Both Q1A & Q1B passed: {accepted_for_metadata} ({accepted_for_metadata/total_files*100:.1f}%)")
    print(f"  ├─ Metadata actually extracted: {metadata_extracted} ({metadata_extracted/total_files*100:.1f}%)")
    print(f"  └─ Rejection rate: {(total_files-accepted_for_metadata)/total_files*100:.1f}%")
    
    # Metadata Quality Analysis
    if metadata_extracted > 0:
        extracted_df = df[df['metadata_extracted'] == True]
        
        print(f"\n📋 METADATA EXTRACTION QUALITY ({metadata_extracted} files):")
        
        # Field completion rates
        fields = ['title', 'doc_type', 'health_topic', 'creator', 'year', 'country', 'language', 'governance_level']
        for field in fields:
            if field in extracted_df.columns:
                non_empty = extracted_df[field].notna() & (extracted_df[field] != '')
                completion_rate = non_empty.sum() / len(extracted_df) * 100
                print(f"  ├─ {field}: {completion_rate:.1f}% completion")
        
        # Document types found
        doc_types = extracted_df['doc_type'].value_counts()
        print(f"\n📊 DOCUMENT TYPES EXTRACTED:")
        for doc_type, count in doc_types.items():
            if pd.notna(doc_type):
                print(f"  ├─ {doc_type}: {count}")
        
        # Health topics found
        health_topics = extracted_df['health_topic'].value_counts()
        print(f"\n🏥 HEALTH TOPICS EXTRACTED:")
        for topic, count in health_topics.items():
            if pd.notna(topic):
                print(f"  ├─ {topic}: {count}")
        
        # Creators found
        creators = extracted_df['creator'].value_counts()
        print(f"\n🏛️ CREATORS EXTRACTED:")
        for creator, count in creators.items():
            if pd.notna(creator):
                print(f"  ├─ {creator}: {count}")
        
        # Confidence analysis
        if 'overall_confidence' in extracted_df.columns:
            avg_confidence = extracted_df['overall_confidence'].mean()
            print(f"\n🎯 CONFIDENCE ANALYSIS:")
            print(f"  ├─ Average overall confidence: {avg_confidence:.3f}")
            print(f"  ├─ High confidence (>0.8): {(extracted_df['overall_confidence'] > 0.8).sum()}")
            print(f"  └─ Low confidence (<0.6): {(extracted_df['overall_confidence'] < 0.6).sum()}")
    
    # Rejection Analysis (handle null values from failed files)
    valid_assessments = df[df['question_1a_health_policy'].notna() & df['question_1b_ghpl_categories'].notna()]
    valid_both_true = valid_assessments['question_1a_health_policy'] & valid_assessments['question_1b_ghpl_categories']
    rejected_valid = valid_assessments[~valid_both_true]
    
    if len(rejected_valid) > 0:
        print(f"\n🚫 REJECTION REASONS ({len(rejected_valid)} files with valid assessments):")
        
        # Breakdown by rejection type
        q1a_only_fail = (~valid_assessments['question_1a_health_policy']) & valid_assessments['question_1b_ghpl_categories']
        q1b_only_fail = valid_assessments['question_1a_health_policy'] & (~valid_assessments['question_1b_ghpl_categories'])
        both_fail = (~valid_assessments['question_1a_health_policy']) & (~valid_assessments['question_1b_ghpl_categories'])
        
        print(f"  ├─ Not authoritative health source only: {q1a_only_fail.sum()}")
        print(f"  ├─ Doesn't fit GHPL categories only: {q1b_only_fail.sum()}")
        print(f"  └─ Both reasons: {both_fail.sum()}")
    
    # Check for processing failures
    failed_files = df[df['question_1a_health_policy'].isna()]
    if len(failed_files) > 0:
        print(f"\n⚠️ PROCESSING FAILURES ({len(failed_files)} files):")
        for idx, row in failed_files.iterrows():
            print(f"  ├─ {row['filename']}: No assessment (likely oversized PDF or API error)")
    
    # Performance Analysis
    processing_times = df['processing_time_seconds']
    print(f"\n⏱️ PERFORMANCE ANALYSIS:")
    print(f"  ├─ Fastest processing: {processing_times.min():.1f} seconds")
    print(f"  ├─ Slowest processing: {processing_times.max():.1f} seconds")
    print(f"  ├─ Median processing: {processing_times.median():.1f} seconds")
    print(f"  └─ Estimated docs/hour: {3600/processing_times.mean():.1f}")
    
    return df

def main():
    csv_file = "meta_gpt5_results_20250827_003357.csv"
    
    if not Path(csv_file).exists():
        print(f"❌ CSV file not found: {csv_file}")
        return
    
    results_df = analyze_current_results(csv_file)
    print(f"\n✅ Analysis complete! The results look very promising so far.")

if __name__ == "__main__":
    main()