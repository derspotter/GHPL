#!/usr/bin/env python3
"""
Test GPT-5 Responses API specifically
"""

import os
from pydantic import BaseModel, Field
from openai import OpenAI

class SimpleMetadata(BaseModel):
    title: str = Field(description="Document title")
    year: int = Field(description="Publication year")

def test_responses_api():
    API_KEY = os.environ.get("OPENAI_API_KEY")
    if not API_KEY:
        print("❌ OPENAI_API_KEY not found")
        return
    
    client = OpenAI(api_key=API_KEY)
    
    try:
        print("🔧 Testing GPT-5 Responses API...")
        
        # Simple test without files
        response = client.responses.parse(
            model="gpt-5-mini",
            input=[
                {
                    "role": "user",
                    "content": "Extract metadata from this text: 'Federal Register Vol. 82, No. 246 Tuesday, December 26, 2017 Notices'"
                }
            ],
            text_format=SimpleMetadata
        )
        
        print("✅ Responses API works!")
        print(f"Result: {response}")
        
        # Access the parsed data
        if hasattr(response, 'output_parsed') and response.output_parsed:
            metadata = response.output_parsed
            print(f"Title: {metadata.title}")
            print(f"Year: {metadata.year}")
        
    except Exception as e:
        print(f"❌ Responses API failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_responses_api()