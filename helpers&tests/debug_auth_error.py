#!/usr/bin/env python3
"""
Debug the exact authentication error
"""

import os
import sys
sys.path.insert(0, '.')

from meta_ghpl_gpt5 import upload_pdf_subset
from openai import OpenAI

def test_exact_path():
    API_KEY = os.environ.get("OPENAI_API_KEY")
    if not API_KEY:
        print("❌ OPENAI_API_KEY not found")
        return
    
    print(f"🔧 Testing with API key: {API_KEY[:20]}...")
    
    # Initialize client exactly like the main script
    client = OpenAI(api_key=API_KEY, timeout=900.0)
    print("🔧 OpenAI client initialized")
    
    # Test the exact function call
    try:
        first_pages_file, last_pages_file = upload_pdf_subset(client, "docs_correct/2017-27762.pdf")
        print(f"Result: first={first_pages_file}, last={last_pages_file}")
        
        # Clean up if successful
        if first_pages_file:
            try:
                client.files.delete(first_pages_file.id)
                print("✅ Cleaned up first file")
            except:
                pass
        if last_pages_file:
            try:
                client.files.delete(last_pages_file.id)
                print("✅ Cleaned up last file")
            except:
                pass
                
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        
        # Try to get the underlying cause
        if hasattr(e, '__cause__') and e.__cause__:
            print(f"   Caused by: {type(e.__cause__).__name__}: {e.__cause__}")
        
        if hasattr(e, 'last_attempt') and e.last_attempt:
            print(f"   Last attempt: {e.last_attempt}")
            if hasattr(e.last_attempt, 'exception') and e.last_attempt.exception:
                print(f"   Last exception: {type(e.last_attempt.exception()).__name__}: {e.last_attempt.exception()}")

if __name__ == "__main__":
    test_exact_path()