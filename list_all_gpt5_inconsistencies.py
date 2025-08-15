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
df1 = df1.sort_values('filename').reset_index(drop=True)
df2 = df2.sort_values('filename').reset_index(drop=True)

print('=' * 80)
print('ALL INCONSISTENCIES BETWEEN GPT-5 RUN 1 AND RUN 2')
print('=' * 80)
print()

# 1. Question 1a (Health Policy) Inconsistencies
print('1. QUESTION 1A (HEALTH POLICY) INCONSISTENCIES:')
print('-' * 60)
health_diff = df1['question_1a_health_policy'] != df2['question_1a_health_policy']
health_changed = df1[health_diff]

if len(health_changed) > 0:
    for idx, row in health_changed.iterrows():
        file = row['filename']
        val1 = row['question_1a_health_policy']
        val2 = df2.loc[df2['filename'] == file, 'question_1a_health_policy'].iloc[0]
        conf1 = row['question_1a_confidence']
        conf2 = df2.loc[df2['filename'] == file, 'question_1a_confidence'].iloc[0]
        expl1 = row['question_1a_explanation'][:100] if pd.notna(row['question_1a_explanation']) else 'N/A'
        expl2 = df2.loc[df2['filename'] == file, 'question_1a_explanation'].iloc[0]
        expl2 = expl2[:100] if pd.notna(expl2) else 'N/A'
        
        print(f'\nFile: {file}')
        print(f'  Run 1: {val1} (confidence: {conf1:.2f})')
        print(f'    Explanation: {expl1}...')
        print(f'  Run 2: {val2} (confidence: {conf2:.2f})')
        print(f'    Explanation: {expl2}...')
else:
    print('  No inconsistencies found')

# 2. Question 1b (GHPL Categories) Inconsistencies
print('\n\n2. QUESTION 1B (GHPL CATEGORIES) INCONSISTENCIES:')
print('-' * 60)
ghpl_diff = df1['question_1b_ghpl_categories'] != df2['question_1b_ghpl_categories']
ghpl_changed = df1[ghpl_diff]

if len(ghpl_changed) > 0:
    for idx, row in ghpl_changed.iterrows():
        file = row['filename']
        val1 = row['question_1b_ghpl_categories']
        val2 = df2.loc[df2['filename'] == file, 'question_1b_ghpl_categories'].iloc[0]
        conf1 = row['question_1b_confidence']
        conf2 = df2.loc[df2['filename'] == file, 'question_1b_confidence'].iloc[0]
        
        print(f'\nFile: {file}')
        print(f'  Run 1: {val1} (confidence: {conf1:.2f})')
        print(f'  Run 2: {val2} (confidence: {conf2:.2f})')
else:
    print('  No inconsistencies found')

# 3. Metadata Field Inconsistencies (for files with metadata in both runs)
print('\n\n3. METADATA FIELD INCONSISTENCIES:')
print('-' * 60)

# Filter to files that had metadata extracted in both runs
meta1 = df1[df1['metadata_extracted'] == True]
meta2 = df2[df2['metadata_extracted'] == True]

# Get common files with metadata
meta_files = set(meta1['filename']) & set(meta2['filename'])
meta1_common = meta1[meta1['filename'].isin(meta_files)].sort_values('filename').reset_index(drop=True)
meta2_common = meta2[meta2['filename'].isin(meta_files)].sort_values('filename').reset_index(drop=True)

metadata_fields = ['title', 'doc_type', 'health_topic', 'creator', 'year', 'country', 'language', 'governance_level']

print(f'\nAnalyzing {len(meta1_common)} files with metadata in both runs...\n')

# Track all inconsistencies
all_inconsistencies = {}

for field in metadata_fields:
    if field in meta1_common.columns and field in meta2_common.columns:
        field_inconsistencies = []
        
        for i in range(len(meta1_common)):
            val1 = meta1_common.iloc[i][field]
            val2 = meta2_common.iloc[i][field]
            filename = meta1_common.iloc[i]['filename']
            
            # Check for exact match
            if not ((pd.isna(val1) and pd.isna(val2)) or (val1 == val2)):
                # Not an exact match, check fuzzy match
                if not fuzzy_match(val1, val2):
                    field_inconsistencies.append({
                        'file': filename,
                        'run1': val1,
                        'run2': val2
                    })
        
        if field_inconsistencies:
            all_inconsistencies[field] = field_inconsistencies

# Display all metadata inconsistencies
if all_inconsistencies:
    for field, inconsistencies in all_inconsistencies.items():
        print(f'\n{field.upper()} ({len(inconsistencies)} inconsistencies):')
        print('-' * 40)
        for item in inconsistencies:
            print(f"  File: {item['file']}")
            print(f"    Run 1: {item['run1']}")
            print(f"    Run 2: {item['run2']}")
            print()
else:
    print('  No significant metadata inconsistencies found')

# 4. Confidence Score Changes
print('\n\n4. SIGNIFICANT CONFIDENCE CHANGES (>0.2 difference):')
print('-' * 60)

# Check Q1a confidence changes
print('\nQuestion 1a confidence changes:')
for idx, row in df1.iterrows():
    file = row['filename']
    conf1 = row['question_1a_confidence']
    conf2 = df2.loc[df2['filename'] == file, 'question_1a_confidence'].iloc[0]
    
    if pd.notna(conf1) and pd.notna(conf2) and abs(conf1 - conf2) > 0.2:
        print(f"  {file}: {conf1:.2f} → {conf2:.2f} (Δ={conf2-conf1:+.2f})")

# Check Q1b confidence changes
print('\nQuestion 1b confidence changes:')
for idx, row in df1.iterrows():
    file = row['filename']
    conf1 = row['question_1b_confidence']
    conf2 = df2.loc[df2['filename'] == file, 'question_1b_confidence'].iloc[0]
    
    if pd.notna(conf1) and pd.notna(conf2) and abs(conf1 - conf2) > 0.2:
        print(f"  {file}: {conf1:.2f} → {conf2:.2f} (Δ={conf2-conf1:+.2f})")

# Check overall confidence changes (for files with metadata)
print('\nOverall metadata confidence changes:')
for idx, row in meta1_common.iterrows():
    file = row['filename']
    conf1 = row['overall_confidence'] if 'overall_confidence' in row else None
    conf2_row = meta2_common[meta2_common['filename'] == file]
    if not conf2_row.empty:
        conf2 = conf2_row['overall_confidence'].iloc[0] if 'overall_confidence' in conf2_row.columns else None
        
        if pd.notna(conf1) and pd.notna(conf2) and abs(conf1 - conf2) > 0.2:
            print(f"  {file}: {conf1:.2f} → {conf2:.2f} (Δ={conf2-conf1:+.2f})")

print('\n' + '=' * 80)
print('SUMMARY:')
print(f'  • Health policy inconsistencies: {len(health_changed)} files')
print(f'  • GHPL category inconsistencies: {len(ghpl_changed)} files')
print(f'  • Metadata field inconsistencies: {sum(len(v) for v in all_inconsistencies.values())} total')
print('=' * 80)