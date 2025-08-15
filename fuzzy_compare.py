import pandas as pd
from difflib import SequenceMatcher

def fuzzy_match(str1, str2, threshold=0.85):
    '''Check if two strings are similar above threshold'''
    if pd.isna(str1) or pd.isna(str2):
        return pd.isna(str1) and pd.isna(str2)  # Both None = match
    if str1 == str2:
        return True
    return SequenceMatcher(None, str(str1).lower(), str(str2).lower()).ratio() >= threshold

# Read results 3, 4, and 5 to compare impact of PDF content in search
df3 = pd.read_excel('results_40_3.xlsx')  
df4 = pd.read_excel('results_40_4.xlsx')  
df5 = pd.read_excel('results_40_5.xlsx')  

# Sort by filename
df3_sorted = df3.sort_values('filename').reset_index(drop=True)
df4_sorted = df4.sort_values('filename').reset_index(drop=True)
df5_sorted = df5.sort_values('filename').reset_index(drop=True)

print('=== COMPARING RESULTS 3, 4, and 5 (PDF Content Impact) ===')
print('Results 3: Without PDF content in search grounding')
print('Results 4: With PDF content in search grounding')
print('Results 5: With PDF content in search grounding')
print()

# File timestamps
import os, datetime
print('File info:')
for f in ['results_40_3.xlsx', 'results_40_4.xlsx', 'results_40_5.xlsx']:
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%H:%M:%S')
    print(f'{f}: modified at {mtime}')
print()

metadata_fields = ['title_extracted', 'doc_type_extracted', 'health_topic_extracted', 
                  'creator_extracted', 'year_extracted', 'country_extracted', 'language_extracted']

# Three-way exact comparison (3, 4, 5)
print('THREE-WAY EXACT COMPARISON (all identical):')
total_comparisons = 0
total_identical = 0

for field in metadata_fields:
    if field in df3_sorted.columns and field in df4_sorted.columns and field in df5_sorted.columns:
        identical_all = (df3_sorted[field] == df4_sorted[field]) & (df4_sorted[field] == df5_sorted[field])
        identical_count = identical_all.sum()
        total_count = len(df3_sorted)
        
        stability_rate = identical_count / total_count if total_count > 0 else 0
        
        total_comparisons += total_count  
        total_identical += identical_count
        
        field_name = field.replace('_extracted', '')
        print(f'  {field_name:15}: {identical_count:2}/{total_count} identical ({stability_rate:.1%})')

overall_exact_3way = total_identical / total_comparisons if total_comparisons > 0 else 0
print()
print(f'Overall exact match (3-way): {overall_exact_3way:.1%}')

# Three-way fuzzy comparison
print()
print('THREE-WAY FUZZY COMPARISON (85% similarity threshold):')
total_comparisons = 0
total_similar = 0

for field in metadata_fields:
    if field in df3_sorted.columns and field in df4_sorted.columns and field in df5_sorted.columns:
        similar_count = 0
        total_count = len(df3_sorted)
        
        for i in range(total_count):
            val3 = df3_sorted.iloc[i][field]
            val4 = df4_sorted.iloc[i][field]
            val5 = df5_sorted.iloc[i][field]
            
            # All three must be similar to each other
            if fuzzy_match(val3, val4) and fuzzy_match(val4, val5) and fuzzy_match(val3, val5):
                similar_count += 1
        
        similarity_rate = similar_count / total_count if total_count > 0 else 0
        
        total_comparisons += total_count  
        total_similar += similar_count
        
        field_name = field.replace('_extracted', '')
        print(f'  {field_name:15}: {similar_count:2}/{total_count} similar ({similarity_rate:.1%})')

overall_similarity_3way = total_similar / total_comparisons if total_comparisons > 0 else 0
print()
print(f'Overall fuzzy similarity (3-way): {overall_similarity_3way:.1%}')
print()

# Show examples of fuzzy matches
print('EXAMPLES OF FUZZY MATCHES (not exact but similar):')
print('-' * 60)

for field in ['title_extracted', 'doc_type_extracted']:
    if field in df3_sorted.columns:
        field_name = field.replace('_extracted', '')
        print(f'\n{field_name.upper()} field:')
        
        fuzzy_found = False
        for i in range(len(df3_sorted)):
            val3 = df3_sorted.iloc[i][field]
            val4 = df4_sorted.iloc[i][field]
            val5 = df5_sorted.iloc[i][field]
            
            # Find cases where they're similar but not identical
            is_fuzzy_34 = fuzzy_match(val3, val4) and (str(val3) != str(val4))
            is_fuzzy_35 = fuzzy_match(val3, val5) and (str(val3) != str(val5))
            is_fuzzy_45 = fuzzy_match(val4, val5) and (str(val4) != str(val5))
            
            if is_fuzzy_34 or is_fuzzy_35 or is_fuzzy_45:
                if not fuzzy_found:  # Only show first example per field
                    filename = df3_sorted.iloc[i]['filename'][:40]
                    print(f'  File: {filename}')
                    print(f'    Run 3: {val3}')
                    print(f'    Run 4: {val4}')
                    print(f'    Run 5: {val5}')
                    
                    # Calculate similarity scores
                    if not pd.isna(val3) and not pd.isna(val4):
                        sim_34 = SequenceMatcher(None, str(val3).lower(), str(val4).lower()).ratio()
                        print(f'    Similarity 3-4: {sim_34:.1%}')
                    if not pd.isna(val3) and not pd.isna(val5):
                        sim_35 = SequenceMatcher(None, str(val3).lower(), str(val5).lower()).ratio()
                        print(f'    Similarity 3-5: {sim_35:.1%}')
                    if not pd.isna(val4) and not pd.isna(val5):
                        sim_45 = SequenceMatcher(None, str(val4).lower(), str(val5).lower()).ratio()
                        print(f'    Similarity 4-5: {sim_45:.1%}')
                    
                    fuzzy_found = True
                    break

print()
print('PAIRWISE COMPARISONS:')
print('-' * 60)

pairs = [
    ('Run 3 vs 4 (before vs after PDF)', df3_sorted, df4_sorted),
    ('Run 3 vs 5 (before vs after PDF)', df3_sorted, df5_sorted),
    ('Run 4 vs 5 (both with PDF)', df4_sorted, df5_sorted)
]

for pair_name, dfa, dfb in pairs:
    print(f'\n{pair_name}:')
    pair_similar = 0
    pair_total = 0
    
    for field in metadata_fields:
        if field in dfa.columns and field in dfb.columns:
            similar_count = 0
            for i in range(len(dfa)):
                if fuzzy_match(dfa.iloc[i][field], dfb.iloc[i][field]):
                    similar_count += 1
            
            total_count = len(dfa)
            similarity_rate = similar_count / total_count if total_count > 0 else 0
            field_name = field.replace('_extracted', '')
            print(f'  {field_name:15}: {similar_count:2}/{total_count} ({similarity_rate:.1%})')
            
            pair_similar += similar_count
            pair_total += total_count
    
    pair_similarity = pair_similar / pair_total if pair_total > 0 else 0
    print(f'  Overall: {pair_similarity:.1%}')

print()
print('=== SUMMARY: PDF CONTENT IMPACT ===')
print(f'Three-way exact match (3,4,5): {overall_exact_3way:.1%}')
print(f'Three-way fuzzy match (3,4,5): {overall_similarity_3way:.1%}')
print(f'Improvement with fuzzy: +{(overall_similarity_3way - overall_exact_3way)*100:.1f} percentage points')
print()
print('Key finding: Results 3 (without PDF) vs Results 4&5 (with PDF content)')
print('This shows the consistency impact of providing PDF content to search grounding.')