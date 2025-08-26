#!/usr/bin/env python3
"""
Test the specific retry function from meta_ghpl_gpt5.py
"""

import os
import tempfile
import pikepdf
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

@retry(
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type((Exception,))
)
def upload_files_with_retry(client, temp_first_path, temp_last_path, filename):
    """Upload PDF files with tenacity retry logic."""
    uploaded_first = None
    uploaded_last = None
    
    print(f"📤 Attempting upload for {filename}...")
    print(f"   First file path: {temp_first_path}")
    print(f"   Last file path: {temp_last_path}")
    
    # Upload first pages
    try:
        with open(temp_first_path, "rb") as f:
            print(f"   Opening file: {f.name}")
            uploaded_first = client.files.create(file=f, purpose="user_data")
        print(f"✅ {filename}: Uploaded first pages: {uploaded_first.id}")
    except Exception as e:
        print(f"❌ Error uploading first file: {type(e).__name__}: {e}")
        raise
    
    # Upload last pages if exists
    if temp_last_path:
        try:
            with open(temp_last_path, "rb") as f:
                uploaded_last = client.files.create(file=f, purpose="user_data")
            print(f"✅ {filename}: Uploaded last pages: {uploaded_last.id}")
        except Exception as e:
            print(f"❌ Error uploading last file: {type(e).__name__}: {e}")
            raise
    
    return uploaded_first, uploaded_last

def test_upload():
    API_KEY = os.environ.get("OPENAI_API_KEY")
    if not API_KEY:
        print("❌ OPENAI_API_KEY not found")
        return
    
    client = OpenAI(api_key=API_KEY, timeout=900.0)
    
    # Create PDF file like the main script does
    pdf_path = "docs_correct/2017-27762.pdf"
    
    temp_first_path = None
    temp_last_path = None
    
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix="_first.pdf") as temp_f:
            temp_first_path = temp_f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix="_last.pdf") as temp_f:
            temp_last_path = temp_f.name
        
        # Extract pages using pikepdf (same as original)
        with pikepdf.open(pdf_path) as source_pdf:
            total_pages = len(source_pdf.pages)
            print(f"Total pages in PDF: {total_pages}")
            
            # Create first pages PDF
            first_pdf = pikepdf.Pdf.new()
            pages_to_extract = min(total_pages, 10)
            for i in range(pages_to_extract):
                first_pdf.pages.append(source_pdf.pages[i])
            first_pdf.save(temp_first_path)
            print(f"✅ Extracted first {pages_to_extract} pages to {temp_first_path}")
            
            # For this test file, no last pages needed
            temp_last_path = None
        
        # Test the upload function
        uploaded_first, uploaded_last = upload_files_with_retry(
            client, temp_first_path, temp_last_path, "2017-27762.pdf"
        )
        
        print("✅ Upload successful!")
        
        # Clean up
        if uploaded_first:
            client.files.delete(uploaded_first.id)
            print("✅ Deleted first file")
        if uploaded_last:
            client.files.delete(uploaded_last.id)
            print("✅ Deleted last file")
            
    except Exception as e:
        print(f"❌ Test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup temporary files
        if temp_first_path and os.path.exists(temp_first_path):
            os.remove(temp_first_path)
        if temp_last_path and os.path.exists(temp_last_path):
            os.remove(temp_last_path)

if __name__ == "__main__":
    test_upload()