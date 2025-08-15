#!/usr/bin/env python3
"""Analyze confidence scores for documents with inconsistent decisions across runs."""

import pandas as pd

# Load both CSV files
df1 = pd.read_csv('meta_ghpl_results_20250810_003057.csv')
df2 = pd.read_csv('meta_ghpl_results_20250810_140130.csv')

# Files that changed decisions
inconsistent_files = [
    '22_0347.pdf',
    'Bulk-up-your-meals-cook-islands.pdf',
    'Delta-8-THC-FAQ.pdf',
    'ASGM_Ghana_ICA_21052020_web.pdf'
]

print("="*80)
print("CONFIDENCE ANALYSIS FOR INCONSISTENT DECISIONS")
print("="*80)

confidence_data = []

for filename in inconsistent_files:
    row1 = df1[df1['filename'] == filename].iloc[0]
    row2 = df2[df2['filename'] == filename].iloc[0]
    
    print(f"\n{filename}")
    print("-"*60)
    
    # Q1A Analysis
    q1a_changed = row1['question_1a_health_policy'] != row2['question_1a_health_policy']
    print(f"Q1A (Health Policy): {'✅' if row1['question_1a_health_policy'] else '❌'} → {'✅' if row2['question_1a_health_policy'] else '❌'}")
    print(f"  Confidence: {row1['question_1a_confidence']:.2f} → {row2['question_1a_confidence']:.2f}")
    if q1a_changed:
        print(f"  ⚠️ DECISION CHANGED despite confidence: {row1['question_1a_confidence']:.2f} → {row2['question_1a_confidence']:.2f}")
    
    # Q1B Analysis  
    q1b_changed = row1['question_1b_ghpl_categories'] != row2['question_1b_ghpl_categories']
    print(f"\nQ1B (GHPL Categories): {'✅' if row1['question_1b_ghpl_categories'] else '❌'} → {'✅' if row2['question_1b_ghpl_categories'] else '❌'}")
    print(f"  Confidence: {row1['question_1b_confidence']:.2f} → {row2['question_1b_confidence']:.2f}")
    if q1b_changed:
        print(f"  ⚠️ DECISION CHANGED despite confidence: {row1['question_1b_confidence']:.2f} → {row2['question_1b_confidence']:.2f}")
    
    confidence_data.append({
        'filename': filename,
        'q1a_conf_run1': row1['question_1a_confidence'],
        'q1a_conf_run2': row2['question_1a_confidence'],
        'q1b_conf_run1': row1['question_1b_confidence'],
        'q1b_conf_run2': row2['question_1b_confidence'],
        'q1a_changed': q1a_changed,
        'q1b_changed': q1b_changed
    })

print("\n" + "="*80)
print("CONFIDENCE PATTERNS IN INCONSISTENT DECISIONS")
print("-"*60)

conf_df = pd.DataFrame(confidence_data)

# Analyze confidence levels for changed decisions
q1a_changes = conf_df[conf_df['q1a_changed']]
q1b_changes = conf_df[conf_df['q1b_changed']]

if len(q1a_changes) > 0:
    print("\nQ1A Changes - Confidence Analysis:")
    print(f"  Average confidence in Run 1: {q1a_changes['q1a_conf_run1'].mean():.2f}")
    print(f"  Average confidence in Run 2: {q1a_changes['q1a_conf_run2'].mean():.2f}")
    print(f"  Min confidence when changed: {min(q1a_changes['q1a_conf_run1'].min(), q1a_changes['q1a_conf_run2'].min()):.2f}")
    print(f"  Max confidence when changed: {max(q1a_changes['q1a_conf_run1'].max(), q1a_changes['q1a_conf_run2'].max()):.2f}")

if len(q1b_changes) > 0:
    print("\nQ1B Changes - Confidence Analysis:")
    print(f"  Average confidence in Run 1: {q1b_changes['q1b_conf_run1'].mean():.2f}")
    print(f"  Average confidence in Run 2: {q1b_changes['q1b_conf_run2'].mean():.2f}")
    print(f"  Min confidence when changed: {min(q1b_changes['q1b_conf_run1'].min(), q1b_changes['q1b_conf_run2'].min()):.2f}")
    print(f"  Max confidence when changed: {max(q1b_changes['q1b_conf_run1'].max(), q1b_changes['q1b_conf_run2'].max()):.2f}")

print("\n" + "="*80)
print("KEY INSIGHTS")
print("-"*60)

# Check for pattern: do changes happen more with lower confidence?
print("\nConfidence levels when decisions changed:")
all_changed_confidences = []
if len(q1a_changes) > 0:
    all_changed_confidences.extend(q1a_changes['q1a_conf_run1'].tolist())
    all_changed_confidences.extend(q1a_changes['q1a_conf_run2'].tolist())
if len(q1b_changes) > 0:
    all_changed_confidences.extend(q1b_changes['q1b_conf_run1'].tolist())
    all_changed_confidences.extend(q1b_changes['q1b_conf_run2'].tolist())

if all_changed_confidences:
    print(f"  Range: {min(all_changed_confidences):.2f} - {max(all_changed_confidences):.2f}")
    print(f"  Average: {sum(all_changed_confidences)/len(all_changed_confidences):.2f}")
    
    # Count by confidence tier
    very_high = sum(1 for c in all_changed_confidences if c >= 0.95)
    high = sum(1 for c in all_changed_confidences if 0.85 <= c < 0.95)
    medium = sum(1 for c in all_changed_confidences if 0.70 <= c < 0.85)
    low = sum(1 for c in all_changed_confidences if c < 0.70)
    
    print(f"\nConfidence distribution for changed decisions:")
    print(f"  Very High (≥0.95): {very_high} ({very_high/len(all_changed_confidences)*100:.1f}%)")
    print(f"  High (0.85-0.94): {high} ({high/len(all_changed_confidences)*100:.1f}%)")
    print(f"  Medium (0.70-0.84): {medium} ({medium/len(all_changed_confidences)*100:.1f}%)")
    print(f"  Low (<0.70): {low} ({low/len(all_changed_confidences)*100:.1f}%)")

# Analyze consistent vs inconsistent files
print("\n" + "="*80)
print("COMPARING CONSISTENT VS INCONSISTENT FILES")
print("-"*60)

# Get consistent files (all others)
all_files = set(df1['filename']) & set(df2['filename'])
consistent_files = all_files - set(inconsistent_files)

# Calculate average confidences
consistent_conf = []
for f in consistent_files:
    r1 = df1[df1['filename'] == f].iloc[0]
    r2 = df2[df2['filename'] == f].iloc[0]
    consistent_conf.extend([
        r1['question_1a_confidence'],
        r2['question_1a_confidence'],
        r1['question_1b_confidence'],
        r2['question_1b_confidence']
    ])

inconsistent_conf = []
for f in inconsistent_files:
    r1 = df1[df1['filename'] == f].iloc[0]
    r2 = df2[df2['filename'] == f].iloc[0]
    inconsistent_conf.extend([
        r1['question_1a_confidence'],
        r2['question_1a_confidence'],
        r1['question_1b_confidence'],
        r2['question_1b_confidence']
    ])

print(f"Consistent files (n={len(consistent_files)}):")
print(f"  Average confidence: {sum(consistent_conf)/len(consistent_conf):.3f}")
print(f"  Min confidence: {min(consistent_conf):.2f}")
print(f"  Max confidence: {max(consistent_conf):.2f}")

print(f"\nInconsistent files (n={len(inconsistent_files)}):")
print(f"  Average confidence: {sum(inconsistent_conf)/len(inconsistent_conf):.3f}")
print(f"  Min confidence: {min(inconsistent_conf):.2f}")
print(f"  Max confidence: {max(inconsistent_conf):.2f}")

print(f"\nDifference in average confidence: {abs(sum(consistent_conf)/len(consistent_conf) - sum(inconsistent_conf)/len(inconsistent_conf)):.3f}")

if sum(consistent_conf)/len(consistent_conf) > sum(inconsistent_conf)/len(inconsistent_conf):
    print("✅ Consistent files have HIGHER average confidence")
else:
    print("⚠️ Inconsistent files have HIGHER average confidence")