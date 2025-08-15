#!/usr/bin/env python3
"""Analyze specific discrepancies between the two runs."""

import pandas as pd

# Load both CSV files
df1 = pd.read_csv('meta_ghpl_results_20250810_003057.csv')
df2 = pd.read_csv('meta_ghpl_results_20250810_140130.csv')

# Find files with decision changes
discrepant_files = [
    '22_0347.pdf',
    'Bulk-up-your-meals-cook-islands.pdf', 
    'Delta-8-THC-FAQ.pdf',
    'ASGM_Ghana_ICA_21052020_web.pdf'
]

print("="*80)
print("DETAILED ANALYSIS OF DISCREPANT FILES")
print("="*80)

for filename in discrepant_files:
    row1 = df1[df1['filename'] == filename].iloc[0]
    row2 = df2[df2['filename'] == filename].iloc[0]
    
    print(f"\n{filename}")
    print("-"*60)
    
    # Question 1A comparison
    print("Question 1A (Health Policy Related):")
    print(f"  Run 1: {row1['question_1a_health_policy']} (conf: {row1['question_1a_confidence']:.2f})")
    print(f"  Run 2: {row2['question_1a_health_policy']} (conf: {row2['question_1a_confidence']:.2f})")
    if row1['question_1a_health_policy'] != row2['question_1a_health_policy']:
        print("  ⚠️ CHANGED")
    
    # Question 1B comparison
    print("\nQuestion 1B (Fits GHPL Categories):")
    print(f"  Run 1: {row1['question_1b_ghpl_categories']} (conf: {row1['question_1b_confidence']:.2f})")
    print(f"  Run 2: {row2['question_1b_ghpl_categories']} (conf: {row2['question_1b_confidence']:.2f})")
    if row1['question_1b_ghpl_categories'] != row2['question_1b_ghpl_categories']:
        print("  ⚠️ CHANGED")
    
    # Metadata extraction
    print("\nMetadata Extracted:")
    print(f"  Run 1: {row1['metadata_extracted']}")
    print(f"  Run 2: {row2['metadata_extracted']}")
    if row1['metadata_extracted'] != row2['metadata_extracted']:
        print("  ⚠️ CHANGED")
    
    # Show explanations for changes
    if row1['question_1a_explanation'] != row2['question_1a_explanation']:
        print("\nQ1A Explanation Changed:")
        print(f"  Run 1: {row1['question_1a_explanation'][:100]}...")
        print(f"  Run 2: {row2['question_1a_explanation'][:100]}...")
    
    if row1['question_1b_explanation'] != row2['question_1b_explanation']:
        print("\nQ1B Explanation Changed:")
        print(f"  Run 1: {row1['question_1b_explanation'][:100]}...")
        print(f"  Run 2: {row2['question_1b_explanation'][:100]}...")

print("\n" + "="*80)
print("OVERALL IMPACT OF CHANGES")
print("-"*60)

# Calculate overall stats
run1_extracted = df1['metadata_extracted'].sum()
run2_extracted = df2['metadata_extracted'].sum()

run1_rejected_both = ((df1['question_1a_health_policy'] == False) & 
                     (df1['question_1b_ghpl_categories'] == False)).sum()
run1_rejected_a_only = ((df1['question_1a_health_policy'] == False) & 
                        (df1['question_1b_ghpl_categories'] == True)).sum()
run1_rejected_b_only = ((df1['question_1a_health_policy'] == True) & 
                        (df1['question_1b_ghpl_categories'] == False)).sum()

run2_rejected_both = ((df2['question_1a_health_policy'] == False) & 
                     (df2['question_1b_ghpl_categories'] == False)).sum()
run2_rejected_a_only = ((df2['question_1a_health_policy'] == False) & 
                        (df2['question_1b_ghpl_categories'] == True)).sum()
run2_rejected_b_only = ((df2['question_1a_health_policy'] == True) & 
                        (df2['question_1b_ghpl_categories'] == False)).sum()

print("\nRun 1 (00:30:58):")
print(f"  Metadata extracted: {run1_extracted}")
print(f"  Rejected (both false): {run1_rejected_both}")
print(f"  Rejected (only A false): {run1_rejected_a_only}")
print(f"  Rejected (only B false): {run1_rejected_b_only}")

print("\nRun 2 (14:01:30):")
print(f"  Metadata extracted: {run2_extracted}")
print(f"  Rejected (both false): {run2_rejected_both}")
print(f"  Rejected (only A false): {run2_rejected_a_only}")
print(f"  Rejected (only B false): {run2_rejected_b_only}")

print("\nChanges:")
print(f"  Metadata extracted: {run2_extracted - run1_extracted:+d}")
print(f"  Rejected (both false): {run2_rejected_both - run1_rejected_both:+d}")
print(f"  Rejected (only A false): {run2_rejected_a_only - run1_rejected_a_only:+d}")
print(f"  Rejected (only B false): {run2_rejected_b_only - run1_rejected_b_only:+d}")