import pandas as pd
from difflib import SequenceMatcher

def fuzzy_match(str1, str2, threshold=0.85):
    '''Check if two strings are similar above threshold'''
    if pd.isna(str1) or pd.isna(str2):
        return pd.isna(str1) and pd.isna(str2)  # Both None = match
    if str1 == str2:
        return True
    return SequenceMatcher(None, str(str1).lower(), str(str2).lower()).ratio() >= threshold

# Read the two CSV files
df1 = pd.read_csv('meta_gpt5_results_20250810_181027.csv')  # GPT-5 Run 1
df2 = pd.read_csv('meta_gpt5_results_20250810_182401.csv')  # GPT-5 Run 2

# Sort by filename for consistent comparison
df1_sorted = df1.sort_values('filename').reset_index(drop=True)
df2_sorted = df2.sort_values('filename').reset_index(drop=True)

print('=== COMPARING GPT-5 RESULTS (Run 1 vs Run 2) ===')
print()

# File info
import os, datetime
print('File info:')
for f in ['meta_gpt5_results_20250810_181027.csv', 'meta_gpt5_results_20250810_182401.csv']:
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%H:%M:%S')
    print(f'{f}: modified at {mtime}')
print()

# Basic statistics
print(f'Run 1: {len(df1)} files processed')
print(f'Run 2: {len(df2)} files processed')
print()

# Check which files are common
files1 = set(df1['filename'])
files2 = set(df2['filename'])
common_files = files1 & files2
print(f'Common files: {len(common_files)}')

# Filter to common files only
df1_common = df1[df1['filename'].isin(common_files)].sort_values('filename').reset_index(drop=True)
df2_common = df2[df2['filename'].isin(common_files)].sort_values('filename').reset_index(drop=True)

# Check key binary decisions
print()
print('BINARY DECISION COMPARISON:')
print('-' * 60)

# Question 1a: Health policy related
q1a_match = (df1_common['question_1a_health_policy'] == df2_common['question_1a_health_policy']).sum()
print(f'Question 1a (health policy): {q1a_match}/{len(df1_common)} identical ({q1a_match/len(df1_common):.1%})')

# Question 1b: GHPL categories
q1b_match = (df1_common['question_1b_ghpl_categories'] == df2_common['question_1b_ghpl_categories']).sum()
print(f'Question 1b (GHPL categories): {q1b_match}/{len(df1_common)} identical ({q1b_match/len(df1_common):.1%})')

# Metadata extracted
meta_match = (df1_common['metadata_extracted'] == df2_common['metadata_extracted']).sum()
print(f'Metadata extracted: {meta_match}/{len(df1_common)} identical ({meta_match/len(df1_common):.1%})')

# Compare metadata fields for files that had metadata extracted
metadata_fields = ['title', 'doc_type', 'health_topic', 'creator', 'year', 'country', 'language', 'governance_level']

# Filter to files that had metadata extracted in both runs
meta1 = df1_common[df1_common['metadata_extracted'] == True]
meta2 = df2_common[df2_common['metadata_extracted'] == True]

# Get common files with metadata
meta_files = set(meta1['filename']) & set(meta2['filename'])
meta1_common = meta1[meta1['filename'].isin(meta_files)].sort_values('filename').reset_index(drop=True)
meta2_common = meta2[meta2['filename'].isin(meta_files)].sort_values('filename').reset_index(drop=True)

if len(meta1_common) > 0:
    print()
    print(f'METADATA FIELD COMPARISON ({len(meta1_common)} files with metadata in both runs):')
    print('-' * 60)
    
    # Exact comparison
    print('Exact matches:')
    for field in metadata_fields:
        if field in meta1_common.columns and field in meta2_common.columns:
            identical = (meta1_common[field] == meta2_common[field]).sum()
            print(f'  {field:15}: {identical}/{len(meta1_common)} ({identical/len(meta1_common):.1%})')
    
    # Fuzzy comparison
    print()
    print('Fuzzy matches (85% similarity):')
    for field in metadata_fields:
        if field in meta1_common.columns and field in meta2_common.columns:
            similar_count = 0
            for i in range(len(meta1_common)):
                if fuzzy_match(meta1_common.iloc[i][field], meta2_common.iloc[i][field]):
                    similar_count += 1
            print(f'  {field:15}: {similar_count}/{len(meta1_common)} ({similar_count/len(meta1_common):.1%})')

# Show discrepancies in rejection decisions
print()
print('DISCREPANCIES IN DECISIONS:')
print('-' * 60)

# Create boolean masks for comparison
health_policy_diff = df1_common['question_1a_health_policy'] != df2_common['question_1a_health_policy']
ghpl_diff = df1_common['question_1b_ghpl_categories'] != df2_common['question_1b_ghpl_categories']  
metadata_diff = df1_common['metadata_extracted'] != df2_common['metadata_extracted']

# Files where health policy decision changed
health_policy_changed = df1_common[health_policy_diff]
if len(health_policy_changed) > 0:
    print(f'Health policy decision changed for {len(health_policy_changed)} files:')
    for _, row in health_policy_changed.head(3).iterrows():
        file = row['filename']
        val1 = row['question_1a_health_policy']
        val2 = df2_common[df2_common['filename'] == file]['question_1a_health_policy'].iloc[0]
        print(f'  • {file[:40]}: {val1} → {val2}')

# Files where GHPL categories decision changed  
ghpl_changed = df1_common[ghpl_diff]
if len(ghpl_changed) > 0:
    print(f'\nGHPL categories decision changed for {len(ghpl_changed)} files:')
    for _, row in ghpl_changed.head(3).iterrows():
        file = row['filename']
        val1 = row['question_1b_ghpl_categories']
        val2 = df2_common[df2_common['filename'] == file]['question_1b_ghpl_categories'].iloc[0]
        print(f'  • {file[:40]}: {val1} → {val2}')

# Files where metadata extraction decision changed
metadata_changed = df1_common[metadata_diff]
if len(metadata_changed) > 0:
    print(f'\nMetadata extraction decision changed for {len(metadata_changed)} files:')
    for _, row in metadata_changed.head(3).iterrows():
        file = row['filename']
        val1 = row['metadata_extracted']
        val2 = df2_common[df2_common['filename'] == file]['metadata_extracted'].iloc[0]
        print(f'  • {file[:40]}: {val1} → {val2}')

print()
print('=== SUMMARY ===')
print(f'Overall consistency for binary decisions:')
print(f'  • Health policy: {q1a_match/len(df1_common):.1%}')
print(f'  • GHPL categories: {q1b_match/len(df1_common):.1%}')
print(f'  • Metadata extraction: {meta_match/len(df1_common):.1%}')
print(f'Average binary decision consistency: {(q1a_match + q1b_match + meta_match)/(3*len(df1_common)):.1%}')