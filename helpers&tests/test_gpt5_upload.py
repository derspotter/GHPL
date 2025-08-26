#!/usr/bin/env python3
"""
Minimal test to reproduce the GPT-5 authentication error.
"""

import os
import tempfile
import traceback
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
from openai import OpenAI

@retry(
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type((Exception,))
)
def upload_files_with_retry(client, temp_path, filename):
    """Upload PDF files with tenacity retry logic."""
    with open(temp_path, "rb") as f:
        uploaded = client.files.create(file=f, purpose="user_data")
    print(f"✅ {filename}: Uploaded: {uploaded.id}")
    return uploaded

def main():
    # Test the exact same code path as meta_ghpl_gpt5.py
    API_KEY = os.environ.get("OPENAI_API_KEY")
    if not API_KEY:
        print("❌ OPENAI_API_KEY not found")
        return
    
    print(f"🔧 API Key prefix: {API_KEY[:20]}...")
    
    # Create test file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_f:
        temp_path = temp_f.name
        temp_f.write(b"test PDF content")
    
    try:
        # Initialize client same way as script
        client = OpenAI(api_key=API_KEY, timeout=900.0)
        print("🔧 OpenAI client initialized")
        
        # Try upload with same retry logic
        filename = "test.pdf"
        uploaded = upload_files_with_retry(client, temp_path, filename)
        
        print("✅ Upload successful!")
        
        # Clean up
        client.files.delete(uploaded.id)
        print("✅ File deleted")
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        print("Full traceback:")
        traceback.print_exc()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    main()