#!/usr/bin/env python3
"""
Test what happens when we write None values to CSV.
"""

import csv
import io

# Test what happens when we write different values to CSV
test_data = {
    'field1': None,
    'field2': 'None',  # string 'None'
    'field3': '',      # empty string
    'field4': 'Policy'  # actual value
}

print("🧪 TESTING CSV WRITING")
print("=" * 30)
print("Input data:", test_data)

# Write to CSV
output = io.StringIO()
writer = csv.DictWriter(output, fieldnames=['field1', 'field2', 'field3', 'field4'])
writer.writeheader()
writer.writerow(test_data)

csv_content = output.getvalue()
print("\nCSV output:")
print(repr(csv_content))

print("\nParsing it back:")
lines = csv_content.strip().split('\n')
for i, line in enumerate(lines):
    print(f"Line {i}: {line}")
    if i == 1:  # Data row
        values = line.split(',')
        for j, val in enumerate(values):
            print(f"  field{j+1}: '{val}' (length: {len(val)})")