import pandas as pd
from pathlib import Path
from urllib.parse import urlparse

# Load the Excel file
df = pd.read_excel("/home/justus/Nextcloud/GHPL/documents-info.xlsx")

# Search for the specific filename
target_filename = "ZAF_D1_Hypertension_Guideline_December_2006"

print(f"Searching for filename: {target_filename}")
print("-" * 50)

for _, row in df.iterrows():
    if pd.notna(row['public_file_url']):
        url_path = urlparse(row['public_file_url']).path
        filename = Path(url_path).stem
        
        if target_filename in filename:
            print(f"Found exact match:")
            print(f"  ID: {row.get('id')}")
            print(f"  Title: {row.get('title')}")
            print(f"  Doc Type: {row.get('doc_type')}")
            print(f"  Health Topic: {row.get('health_topic')}")
            print(f"  Country: {row.get('country')}")
            print(f"  Creator: {row.get('creator')}")
            print(f"  Year: {row.get('year')}")
            print(f"  Filename: {filename}")
            print(f"  URL: {row.get('public_file_url')}")
            break
else:
    print("Document not found in Excel data.")