#!/usr/bin/env python3
"""Check governance_level values in the CSV."""

import csv

with open('meta_gpt5_results_20250810_190823_repaired.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    
# Check governance_level column
gov_values = [r.get('governance_level', '') for r in rows if r.get('metadata_extracted') == 'True']
non_empty = [v for v in gov_values if v and v != '']
print(f'Total rows with metadata: {len(gov_values)}')
print(f'Rows with governance_level: {len(non_empty)}')
print(f'Sample values: {non_empty[:10] if non_empty else "No values found"}')