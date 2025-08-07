import json
import html
from urllib.parse import unquote_plus, quote, urlparse, urlunparse

def correct_url(url):
    """
    This function decodes, cleans, and re-encodes a URL.
    """
    # 1. Decode the URL
    decoded_url = html.unescape(unquote_plus(url))

    # 2. Parse the URL into its components
    parsed_url = urlparse(decoded_url)
    
    # 3. Clean the path
    path = parsed_url.path
    # Remove known incorrect path prefixes
    path = path.replace("/doc-files/documents/knowledgehub.health.gov.za/2023-04/", "")
    path = path.replace("/doc-files/documents/search.google/", "")
    # A more general way to get just the filename
    filename = path.split('/')[-1]

    # 4. Re-encode the filename
    encoded_filename = quote(filename, safe="()-")

    # 5. Re-assemble the URL with the correct base path
    # Assuming the correct container is 'doc-files'
    correct_path = f"/doc-files/{encoded_filename}"
    
    corrected_url = urlunparse(parsed_url._replace(path=correct_path, query="", params="", fragment=""))
    
    return corrected_url

# Load the failed downloads data
with open('failed_downloads.json', 'r') as f:
    data = json.load(f)

# Correct each URL
corrected_downloads = []
for item in data.get('failed_downloads', []):
    original_url = item.get('url')
    if original_url:
        corrected_url = correct_url(original_url)
        item['corrected_url'] = corrected_url
        corrected_downloads.append(item)

# Save the corrected data to a new JSON file
with open('corrected_downloads.json', 'w') as f:
    json.dump({"corrected_downloads": corrected_downloads}, f, indent=2)

print("Finished correcting URLs. The results have been saved to 'corrected_downloads.json'")