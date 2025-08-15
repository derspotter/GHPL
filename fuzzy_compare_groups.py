import pandas as pd
from difflib import SequenceMatcher
import os
import datetime

def fuzzy_match(str1, str2, threshold=0.85):
    '''Check if two strings are similar above threshold'''
    if pd.isna(str1) or pd.isna(str2):
        return pd.isna(str1) and pd.isna(str2)  # Both None = match
    if str1 == str2:
        return True
    return SequenceMatcher(None, str(str1).lower(), str(str2).lower()).ratio() >= threshold

# Read all 6 results files
print('Loading results files...')
df1 = pd.read_excel('results_40_1.xlsx')  
df2 = pd.read_excel('results_40_2.xlsx')  
df3 = pd.read_excel('results_40_3.xlsx')  
df4 = pd.read_excel('results_40_4.xlsx')  
df5 = pd.read_excel('results_40_5.xlsx')  
df6 = pd.read_excel('results_40_6.xlsx')  

# Sort by filename for consistent comparison
df1_sorted = df1.sort_values('filename').reset_index(drop=True)
df2_sorted = df2.sort_values('filename').reset_index(drop=True)
df3_sorted = df3.sort_values('filename').reset_index(drop=True)
df4_sorted = df4.sort_values('filename').reset_index(drop=True)
df5_sorted = df5.sort_values('filename').reset_index(drop=True)
df6_sorted = df6.sort_values('filename').reset_index(drop=True)

metadata_fields = ['title_extracted', 'doc_type_extracted', 'health_topic_extracted', 
                  'creator_extracted', 'year_extracted', 'country_extracted', 'language_extracted']

print('=' * 70)
print('FUZZY MATCHING COMPARISON: GROUP 1 (1,2,3) vs GROUP 2 (4,5,6)')
print('=' * 70)
print()

# File timestamps
print('File timestamps:')
for f in ['results_40_1.xlsx', 'results_40_2.xlsx', 'results_40_3.xlsx', 
          'results_40_4.xlsx', 'results_40_5.xlsx', 'results_40_6.xlsx']:
    if os.path.exists(f):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        print(f'  {f}: {mtime}')
print()

# GROUP 1 ANALYSIS (1, 2, 3)
print('=' * 70)
print('GROUP 1 ANALYSIS: Comparing Results 1, 2, and 3')
print('=' * 70)

print('\nGROUP 1 - Three-way Exact Match (all identical):')
group1_exact_counts = {}
total_comparisons = 0
total_identical = 0

for field in metadata_fields:
    if field in df1_sorted.columns and field in df2_sorted.columns and field in df3_sorted.columns:
        identical_all = (df1_sorted[field] == df2_sorted[field]) & (df2_sorted[field] == df3_sorted[field])
        identical_count = identical_all.sum()
        total_count = len(df1_sorted)
        
        stability_rate = identical_count / total_count if total_count > 0 else 0
        group1_exact_counts[field] = stability_rate
        
        total_comparisons += total_count  
        total_identical += identical_count
        
        field_name = field.replace('_extracted', '')
        print(f'  {field_name:15}: {identical_count:2}/{total_count} identical ({stability_rate:.1%})')

group1_exact_overall = total_identical / total_comparisons if total_comparisons > 0 else 0
print(f'\nGroup 1 Overall Exact Match: {group1_exact_overall:.1%}')

print('\nGROUP 1 - Three-way Fuzzy Match (85% similarity):')
group1_fuzzy_counts = {}
total_comparisons = 0
total_similar = 0

for field in metadata_fields:
    if field in df1_sorted.columns and field in df2_sorted.columns and field in df3_sorted.columns:
        similar_count = 0
        total_count = len(df1_sorted)
        
        for i in range(total_count):
            val1 = df1_sorted.iloc[i][field]
            val2 = df2_sorted.iloc[i][field]
            val3 = df3_sorted.iloc[i][field]
            
            # All three must be similar to each other
            if fuzzy_match(val1, val2) and fuzzy_match(val2, val3) and fuzzy_match(val1, val3):
                similar_count += 1
        
        similarity_rate = similar_count / total_count if total_count > 0 else 0
        group1_fuzzy_counts[field] = similarity_rate
        
        total_comparisons += total_count  
        total_similar += similar_count
        
        field_name = field.replace('_extracted', '')
        print(f'  {field_name:15}: {similar_count:2}/{total_count} similar ({similarity_rate:.1%})')

group1_fuzzy_overall = total_similar / total_comparisons if total_comparisons > 0 else 0
print(f'\nGroup 1 Overall Fuzzy Match: {group1_fuzzy_overall:.1%}')
print(f'Group 1 Improvement with Fuzzy: +{(group1_fuzzy_overall - group1_exact_overall)*100:.1f} percentage points')

# GROUP 2 ANALYSIS (4, 5, 6)
print('\n' + '=' * 70)
print('GROUP 2 ANALYSIS: Comparing Results 4, 5, and 6')
print('=' * 70)

print('\nGROUP 2 - Three-way Exact Match (all identical):')
group2_exact_counts = {}
total_comparisons = 0
total_identical = 0

for field in metadata_fields:
    if field in df4_sorted.columns and field in df5_sorted.columns and field in df6_sorted.columns:
        identical_all = (df4_sorted[field] == df5_sorted[field]) & (df5_sorted[field] == df6_sorted[field])
        identical_count = identical_all.sum()
        total_count = len(df4_sorted)
        
        stability_rate = identical_count / total_count if total_count > 0 else 0
        group2_exact_counts[field] = stability_rate
        
        total_comparisons += total_count  
        total_identical += identical_count
        
        field_name = field.replace('_extracted', '')
        print(f'  {field_name:15}: {identical_count:2}/{total_count} identical ({stability_rate:.1%})')

group2_exact_overall = total_identical / total_comparisons if total_comparisons > 0 else 0
print(f'\nGroup 2 Overall Exact Match: {group2_exact_overall:.1%}')

print('\nGROUP 2 - Three-way Fuzzy Match (85% similarity):')
group2_fuzzy_counts = {}
total_comparisons = 0
total_similar = 0

for field in metadata_fields:
    if field in df4_sorted.columns and field in df5_sorted.columns and field in df6_sorted.columns:
        similar_count = 0
        total_count = len(df4_sorted)
        
        for i in range(total_count):
            val4 = df4_sorted.iloc[i][field]
            val5 = df5_sorted.iloc[i][field]
            val6 = df6_sorted.iloc[i][field]
            
            # All three must be similar to each other
            if fuzzy_match(val4, val5) and fuzzy_match(val5, val6) and fuzzy_match(val4, val6):
                similar_count += 1
        
        similarity_rate = similar_count / total_count if total_count > 0 else 0
        group2_fuzzy_counts[field] = similarity_rate
        
        total_comparisons += total_count  
        total_similar += similar_count
        
        field_name = field.replace('_extracted', '')
        print(f'  {field_name:15}: {similar_count:2}/{total_count} similar ({similarity_rate:.1%})')

group2_fuzzy_overall = total_similar / total_comparisons if total_comparisons > 0 else 0
print(f'\nGroup 2 Overall Fuzzy Match: {group2_fuzzy_overall:.1%}')
print(f'Group 2 Improvement with Fuzzy: +{(group2_fuzzy_overall - group2_exact_overall)*100:.1f} percentage points')

# COMPARISON BETWEEN GROUPS
print('\n' + '=' * 70)
print('COMPARING THE GROUPS: Group 1 (1,2,3) vs Group 2 (4,5,6)')
print('=' * 70)

print('\nConsistency Comparison (Higher is Better):')
print(f'  Group 1 Exact Match:  {group1_exact_overall:.1%}')
print(f'  Group 2 Exact Match:  {group2_exact_overall:.1%}')
print(f'  Difference: {"Group 2" if group2_exact_overall > group1_exact_overall else "Group 1"} is {abs(group2_exact_overall - group1_exact_overall)*100:.1f} pp more consistent')

print(f'\n  Group 1 Fuzzy Match:  {group1_fuzzy_overall:.1%}')
print(f'  Group 2 Fuzzy Match:  {group2_fuzzy_overall:.1%}')
print(f'  Difference: {"Group 2" if group2_fuzzy_overall > group1_fuzzy_overall else "Group 1"} is {abs(group2_fuzzy_overall - group1_fuzzy_overall)*100:.1f} pp more consistent')

print('\nField-by-Field Consistency Comparison (Fuzzy):')
for field in metadata_fields:
    field_name = field.replace('_extracted', '')
    if field in group1_fuzzy_counts and field in group2_fuzzy_counts:
        g1_rate = group1_fuzzy_counts[field]
        g2_rate = group2_fuzzy_counts[field]
        diff = g2_rate - g1_rate
        better = "G2" if diff > 0 else "G1" if diff < 0 else "="
        print(f'  {field_name:15}: G1={g1_rate:.1%}, G2={g2_rate:.1%}, {better} ({abs(diff)*100:+.1f}pp)')

# CROSS-GROUP COMPARISON (Representative samples)
print('\n' + '=' * 70)
print('CROSS-GROUP COMPARISON: Comparing representatives from each group')
print('=' * 70)

# Compare first result from each group (1 vs 4)
print('\nComparing Result 1 (Group 1) vs Result 4 (Group 2):')
cross_similar = 0
cross_total = 0

for field in metadata_fields:
    if field in df1_sorted.columns and field in df4_sorted.columns:
        similar_count = 0
        for i in range(len(df1_sorted)):
            if fuzzy_match(df1_sorted.iloc[i][field], df4_sorted.iloc[i][field]):
                similar_count += 1
        
        total_count = len(df1_sorted)
        similarity_rate = similar_count / total_count if total_count > 0 else 0
        field_name = field.replace('_extracted', '')
        print(f'  {field_name:15}: {similar_count:2}/{total_count} ({similarity_rate:.1%})')
        
        cross_similar += similar_count
        cross_total += total_count

cross_similarity = cross_similar / cross_total if cross_total > 0 else 0
print(f'  Overall Cross-Group Similarity: {cross_similarity:.1%}')

# Show specific examples of differences between groups
print('\n' + '=' * 70)
print('EXAMPLES OF DIFFERENCES BETWEEN GROUPS')
print('=' * 70)

for field in ['title_extracted', 'doc_type_extracted']:
    if field in df1_sorted.columns:
        field_name = field.replace('_extracted', '')
        print(f'\n{field_name.upper()} field differences:')
        
        differences_found = 0
        for i in range(min(len(df1_sorted), 5)):  # Show up to 5 examples
            val1 = df1_sorted.iloc[i][field]
            val4 = df4_sorted.iloc[i][field]
            
            # Show cases where groups differ
            if not fuzzy_match(val1, val4):
                filename = df1_sorted.iloc[i]['filename'][:40]
                print(f'  File: {filename}')
                print(f'    Group 1 (Run 1): {val1}')
                print(f'    Group 2 (Run 4): {val4}')
                differences_found += 1
                if differences_found >= 2:  # Limit examples
                    break

# SUMMARY
print('\n' + '=' * 70)
print('SUMMARY')
print('=' * 70)

print('\nWithin-Group Consistency:')
print(f'  Group 1 (Runs 1,2,3): {group1_fuzzy_overall:.1%} fuzzy match')
print(f'  Group 2 (Runs 4,5,6): {group2_fuzzy_overall:.1%} fuzzy match')

consistency_winner = "Group 2" if group2_fuzzy_overall > group1_fuzzy_overall else "Group 1"
print(f'\n  → {consistency_winner} is more internally consistent')

print('\nBetween-Group Similarity:')
print(f'  Cross-group similarity (1 vs 4): {cross_similarity:.1%}')

if cross_similarity < 0.8:
    print(f'\n  → Groups show significant differences ({(1-cross_similarity)*100:.1f}% divergence)')
else:
    print(f'\n  → Groups are largely similar despite different runs')

print('\nKey Insights:')
if group2_fuzzy_overall > group1_fuzzy_overall:
    improvement = (group2_fuzzy_overall - group1_fuzzy_overall) * 100
    print(f'  • Group 2 shows {improvement:.1f}pp better consistency than Group 1')
elif group1_fuzzy_overall > group2_fuzzy_overall:
    improvement = (group1_fuzzy_overall - group2_fuzzy_overall) * 100
    print(f'  • Group 1 shows {improvement:.1f}pp better consistency than Group 2')
else:
    print(f'  • Both groups show equal consistency')

print(f'  • Fuzzy matching improves Group 1 by {(group1_fuzzy_overall - group1_exact_overall)*100:.1f}pp')
print(f'  • Fuzzy matching improves Group 2 by {(group2_fuzzy_overall - group2_exact_overall)*100:.1f}pp')