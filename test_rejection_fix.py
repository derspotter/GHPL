#!/usr/bin/env python3
"""Test script to verify rejection reason reporting is fixed."""

import pandas as pd

# Load the CSV
df = pd.read_csv('meta_ghpl_results_20250810_140130.csv')

# Filter for rejected documents
rejected = df[(df['metadata_extracted'] == False) & (df['processed'] == True)]

print("Rejection Reasons Analysis:")
print("="*60)

for _, row in rejected.iterrows():
    filename = row['filename'][:50]
    q1a = row['question_1a_health_policy']
    q1b = row['question_1b_ghpl_categories']
    
    # Determine rejection reason
    if not q1a and not q1b:
        reason = "Both A & B false"
    elif not q1a:
        reason = "Question A false (not from health authority)"
    else:  # not q1b
        reason = "Question B false (doesn't fit GHPL categories)"
    
    print(f"{filename:<50} {reason}")

print("\nSummary:")
print("-"*60)
both_false = rejected[(rejected['question_1a_health_policy'] == False) & 
                      (rejected['question_1b_ghpl_categories'] == False)]
only_a_false = rejected[(rejected['question_1a_health_policy'] == False) & 
                        (rejected['question_1b_ghpl_categories'] == True)]
only_b_false = rejected[(rejected['question_1a_health_policy'] == True) & 
                        (rejected['question_1b_ghpl_categories'] == False)]

print(f"Both A & B false: {len(both_false)} documents")
print(f"Only A false: {len(only_a_false)} documents")
print(f"Only B false: {len(only_b_false)} documents")
print(f"Total rejected: {len(rejected)} documents")