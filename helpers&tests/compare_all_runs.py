import pandas as pd
from datetime import datetime
import numpy as np

# Load all 5 CSV files with 40 rows
files = [
    ('meta_ghpl_results_20250809_235513.csv', 'Run 1: Initial'),
    ('meta_ghpl_results_20250809_235937.csv', 'Run 2: Initial repeat'),
    ('meta_ghpl_results_20250810_002059.csv', 'Run 3: Too restrictive prompt'),
    ('meta_ghpl_results_20250810_002532.csv', 'Run 4: Very restrictive'),
    ('meta_ghpl_results_20250810_003057.csv', 'Run 5: Fixed prompt')
]

dfs = []
for file, label in files:
    df = pd.read_csv(file)
    dfs.append((df, label, file))

print("=" * 70)
print("COMPREHENSIVE COMPARISON OF ALL 5 RUNS")
print("=" * 70)
print()

# Overall statistics
print("OVERALL STATISTICS:")
print("-" * 50)
for df, label, file in dfs:
    extracted = df['metadata_extracted'].sum()
    rejected = (~df['metadata_extracted']).sum()
    acceptance_rate = extracted / len(df) * 100
    timestamp = file.split('_')[-1].replace('.csv', '')
    print(f"{label:30} | Extracted: {extracted:2}/40 ({acceptance_rate:4.1f}%) | Time: {timestamp}")

print()
print("ACCEPTANCE RATE TREND:")
print("-" * 50)
acceptance_rates = []
for df, label, _ in dfs:
    rate = df['metadata_extracted'].sum() / len(df) * 100
    acceptance_rates.append(rate)
    
print(f"Runs 1-2 (before prompt change): {acceptance_rates[0]:.1f}%, {acceptance_rates[1]:.1f}%")
print(f"Runs 3-4 (too restrictive):      {acceptance_rates[2]:.1f}%, {acceptance_rates[3]:.1f}%") 
print(f"Run 5 (balanced prompt):          {acceptance_rates[4]:.1f}%")

# Check consistency across runs
print()
print("CONSISTENCY ANALYSIS:")
print("-" * 50)

# Get common filenames
all_files = set(dfs[0][0]['filename'])

# Track decisions for each file across all runs
file_decisions = {}
for filename in all_files:
    decisions = []
    for df, _, _ in dfs:
        row = df[df['filename'] == filename].iloc[0]
        decision = (
            row.get('question_1a_health_policy', False),
            row.get('question_1b_ghpl_categories', False),
            row.get('metadata_extracted', False)
        )
        decisions.append(decision)
    file_decisions[filename] = decisions

# Find files with inconsistent decisions
inconsistent_files = []
for filename, decisions in file_decisions.items():
    # Check if all decisions are the same
    if len(set(decisions)) > 1:
        inconsistent_files.append(filename)

print(f"Files with consistent decisions across all runs: {40 - len(inconsistent_files)}/40")
print(f"Files with inconsistent decisions: {len(inconsistent_files)}/40")

if inconsistent_files:
    print()
    print("FILES WITH INCONSISTENT DECISIONS:")
    print("-" * 50)
    for filename in inconsistent_files[:10]:  # Show first 10
        decisions = file_decisions[filename]
        print(f"\n{filename[:50]}:")
        for i, (decision, (_, label, _)) in enumerate(zip(decisions, dfs)):
            q1a, q1b, extracted = decision
            status = "✅ Extracted" if extracted else f"❌ Rejected (A={q1a}, B={q1b})"
            print(f"  {label:30}: {status}")

# Analyze specific problem files
print()
print("ANALYSIS OF KEY DOCUMENTS:")
print("-" * 50)

key_files = [
    'Kenya-National-Strategy-for-NCDs-2015-2020.pdf',
    'Heartsine-Samaritan-PAD-350P_Brochure.pdf',
    'Guidelines-adult-adolescent-arv.pdf',
    'Policy_630.00_-_Cardiovascular_Receiving_Center_Criteria_-_07-01-2021.pdf'
]

for key_file in key_files:
    if key_file in file_decisions:
        print(f"\n{key_file}:")
        decisions = file_decisions[key_file]
        for i, (decision, (_, label, _)) in enumerate(zip(decisions, dfs)):
            q1a, q1b, extracted = decision
            if extracted:
                print(f"  {label:30}: ✅ Accepted")
            else:
                print(f"  {label:30}: ❌ Rejected (Q1a={q1a}, Q1b={q1b})")

# Compare specific pairs
print()
print("PAIRWISE IMPROVEMENTS:")
print("-" * 50)

# Compare Run 4 (most restrictive) vs Run 5 (fixed)
df4 = dfs[3][0]
df5 = dfs[4][0]

improved_files = []
for filename in all_files:
    row4 = df4[df4['filename'] == filename].iloc[0]
    row5 = df5[df5['filename'] == filename].iloc[0]
    
    if not row4['metadata_extracted'] and row5['metadata_extracted']:
        improved_files.append(filename)

print(f"Files rejected in Run 4 but accepted in Run 5: {len(improved_files)}")
if improved_files:
    print("Files that improved with prompt fix:")
    for f in improved_files[:5]:
        print(f"  • {f[:60]}")

print()
print("=" * 70)
print("SUMMARY:")
print("-" * 50)
print(f"Best acceptance rate: Run 5 with {acceptance_rates[4]:.1f}%")
print(f"Worst acceptance rate: Run 4 with {acceptance_rates[3]:.1f}%")
print(f"Improvement from worst to best: +{acceptance_rates[4] - acceptance_rates[3]:.1f} percentage points")
print(f"Consistency across all runs: {(40 - len(inconsistent_files))/40*100:.1f}%")