#!/usr/bin/env python3
"""
Debug the upload retry function
"""

import os
import tempfile
import pikepdf
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type, RetryError

def upload_files_without_retry(client, temp_first_path, temp_last_path, filename):
    """Upload without retry to see the actual error."""
    uploaded_first = None
    uploaded_last = None
    
    print(f"📤 Attempting upload for {filename} (no retry)...")
    
    # Upload first pages
    try:
        with open(temp_first_path, "rb") as f:
            print(f"   File size: {os.path.getsize(temp_first_path)} bytes")
            uploaded_first = client.files.create(file=f, purpose="user_data")
        print(f"✅ {filename}: Uploaded first pages: {uploaded_first.id}")
    except Exception as e:
        print(f"❌ Error uploading first file: {type(e).__name__}: {e}")
        print(f"   Error details: {str(e)}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response}")
        if hasattr(e, 'body'):
            print(f"   Body: {e.body}")
        raise
    
    return uploaded_first, uploaded_last

@retry(
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type((Exception,))
)
def upload_files_with_retry(client, temp_first_path, temp_last_path, filename):
    """Upload PDF files with tenacity retry logic."""
    print(f"🔄 Retry attempt for {filename}...")
    return upload_files_without_retry(client, temp_first_path, temp_last_path, filename)

def test_upload_debug():
    API_KEY = os.environ.get("OPENAI_API_KEY")
    if not API_KEY:
        print("❌ OPENAI_API_KEY not found")
        return
    
    print(f"🔧 API Key: {API_KEY[:20]}...")
    client = OpenAI(api_key=API_KEY, timeout=900.0)
    print("🔧 Client created")
    
    # Create PDF file exactly like the main script
    pdf_path = "docs_correct/2017-27762.pdf"
    
    temp_first_path = None
    temp_last_path = None
    
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix="_first.pdf") as temp_f:
            temp_first_path = temp_f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix="_last.pdf") as temp_f:
            temp_last_path = temp_f.name
        
        # Extract pages using pikepdf
        with pikepdf.open(pdf_path) as source_pdf:
            total_pages = len(source_pdf.pages)
            print(f"Total pages in PDF: {total_pages}")
            
            # Create first pages PDF
            first_pdf = pikepdf.Pdf.new()
            pages_to_extract = min(total_pages, 10)
            for i in range(pages_to_extract):
                first_pdf.pages.append(source_pdf.pages[i])
            first_pdf.save(temp_first_path)
            print(f"✅ Extracted first {pages_to_extract} pages")
            
            temp_last_path = None  # No last pages for this short document
        
        print("\n=== Testing without retry first ===")
        try:
            uploaded_first, uploaded_last = upload_files_without_retry(
                client, temp_first_path, temp_last_path, "test-no-retry"
            )
            print("✅ No-retry upload successful!")
            if uploaded_first:
                client.files.delete(uploaded_first.id)
        except Exception as e:
            print(f"❌ No-retry failed: {e}")
            print("This might explain the retry failures...")
        
        print("\n=== Testing with retry ===")
        try:
            uploaded_first, uploaded_last = upload_files_with_retry(
                client, temp_first_path, temp_last_path, "test-with-retry"
            )
            print("✅ Retry upload successful!")
            if uploaded_first:
                client.files.delete(uploaded_first.id)
        except RetryError as e:
            print(f"❌ Retry failed: {e}")
            print(f"   Last attempt result: {e.last_attempt}")
            if hasattr(e.last_attempt, 'exception'):
                actual_error = e.last_attempt.exception()
                print(f"   Actual error: {type(actual_error).__name__}: {actual_error}")
                
    finally:
        # Cleanup
        if temp_first_path and os.path.exists(temp_first_path):
            os.remove(temp_first_path)
        if temp_last_path and os.path.exists(temp_last_path):
            os.remove(temp_last_path)

if __name__ == "__main__":
    test_upload_debug()