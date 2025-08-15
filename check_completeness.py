#!/usr/bin/env python3
"""Check metadata_completeness values in the CSV."""

import csv

# Read the repaired CSV
with open('meta_gpt5_results_20250810_190823_repaired.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Extract metadata_completeness values for documents with metadata
completeness_values = []
for i, row in enumerate(rows):
    if row.get('metadata_extracted') == 'True':
        comp_val = row.get('metadata_completeness', '')
        if comp_val and comp_val != '':
            try:
                val = float(comp_val)
                completeness_values.append((i+1, val))
                if val > 1.0:
                    print(f"Row {i+1}: {row['filename']} has completeness = {val}")
            except ValueError:
                print(f"Row {i+1}: Invalid completeness value: '{comp_val}'")

# Analyze values
if completeness_values:
    values_only = [v for _, v in completeness_values]
    print(f"\nTotal rows with metadata: {len(completeness_values)}")
    print(f"Completeness range: {min(values_only):.3f} to {max(values_only):.3f}")
    print(f"Unique values: {sorted(set(values_only))[:20]}")
    
    # Check for values > 1.0
    over_one = [(r, v) for r, v in completeness_values if v > 1.0]
    if over_one:
        print(f"\n⚠️ Found {len(over_one)} rows with completeness > 1.0:")
        for row, val in over_one[:10]:
            print(f"  Row {row}: {val}")
    else:
        print("\n✅ All completeness values are <= 1.0")