#!/usr/bin/env python3
"""
Repair corrupted CSV file by extracting values from malformed metadata fields.
"""

import csv
import re
import ast

def extract_value_from_field(field_str):
    """Extract the actual value from a malformed metadata field string."""
    if not field_str or field_str == '' or field_str == 'None':
        return ''
    
    # If it's already a clean value, return it
    if not str(field_str).startswith('value='):
        return field_str
    
    # Extract value from the malformed string
    # Pattern: value='...' or value=<EnumType.VALUE: 'Display Value'> or value=2024
    try:
        # Try to match enum pattern first
        enum_match = re.search(r"value=<[^>]+:\s*'([^']+)'", str(field_str))
        if enum_match:
            return enum_match.group(1)
        
        # Try to match simple string value
        string_match = re.search(r"value='([^']*)'", str(field_str))
        if string_match:
            return string_match.group(1)
        
        # Try to match numeric value
        numeric_match = re.search(r"value=(\d+)", str(field_str))
        if numeric_match:
            return numeric_match.group(1)
        
        # Try to match None value
        if 'value=None' in str(field_str):
            return ''
            
    except Exception as e:
        print(f"Error extracting value from '{field_str}': {e}")
    
    return ''

def repair_csv(input_file, output_file):
    """Repair the CSV file by fixing malformed metadata fields."""
    
    # Fields that need repair (metadata fields that might be malformed)
    metadata_fields = ['title', 'doc_type', 'health_topic', 'creator', 
                      'year', 'country', 'language', 'governance_level']
    
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        repaired_rows = []
        rows_fixed = 0
        
        for i, row in enumerate(reader, 1):
            needs_repair = False
            
            # Check if any metadata field needs repair
            for field in metadata_fields:
                if field in row and row[field] and 'value=' in str(row[field]):
                    needs_repair = True
                    break
            
            if needs_repair:
                rows_fixed += 1
                # Repair metadata fields
                for field in metadata_fields:
                    if field in row:
                        row[field] = extract_value_from_field(row[field])
                print(f"Fixed row {i}: {row['filename']}")
            
            repaired_rows.append(row)
    
    # Write repaired CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(repaired_rows)
    
    print(f"\n✅ Repair complete!")
    print(f"📊 Total rows: {len(repaired_rows)}")
    print(f"🔧 Rows fixed: {rows_fixed}")
    print(f"📄 Output saved to: {output_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
        output_csv = input_csv.replace('.csv', '_repaired.csv')
    else:
        input_csv = 'meta_gpt5_results_20250810_190823.csv'
        output_csv = 'meta_gpt5_results_20250810_190823_repaired.csv'
    
    print(f"🔧 Repairing CSV: {input_csv}")
    repair_csv(input_csv, output_csv)