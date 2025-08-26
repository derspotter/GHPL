#!/usr/bin/env python3
"""
Test field extraction logic to understand why enum fields are empty.
"""

import sys
sys.path.append('.')

from meta import DocumentMetadata, DocTypeFieldMetadata, CreatorFieldMetadata, HealthTopicFieldMetadata, GovernanceLevelFieldMetadata

# Test what happens when fields have null values
def test_extract_field_value():
    def extract_field_value(field, field_name=""):
        print(f"\n=== Testing {field_name} ===")
        print(f"field = {field}")
        print(f"field is None: {field is None}")
        
        if field:
            print(f"field has 'value' attr: {hasattr(field, 'value')}")
            if hasattr(field, 'value'):
                print(f"field.value = {field.value}")
                print(f"field.value is None: {field.value is None}")
                print(f"field.value type: {type(field.value)}")
                
                if hasattr(field.value, 'value'):  # Enum field
                    print(f"field.value.value = {field.value.value}")
                    result = field.value.value
                else:
                    result = field.value
                print(f"Extracted result: '{result}'")
                return result
        print("Returning None")
        return None

    print("🧪 TESTING FIELD EXTRACTION LOGIC")
    print("=" * 50)
    
    # Test 1: Completely null field
    print("\n📋 TEST 1: Null field")
    result1 = extract_field_value(None, "null_field")
    
    # Test 2: Field with null value
    print("\n📋 TEST 2: Field with null value")
    null_field = DocTypeFieldMetadata()  # Default constructor should have None value
    result2 = extract_field_value(null_field, "doc_type_null")
    
    # Test 3: Field with actual enum value
    print("\n📋 TEST 3: Field with enum value")
    from meta import DocType
    enum_field = DocTypeFieldMetadata(value=DocType.POLICY, confidence=0.8)
    result3 = extract_field_value(enum_field, "doc_type_with_value")
    
    # Test 4: Test what happens if enum field has string value instead of enum
    print("\n📋 TEST 4: Field with string value (not enum)")
    try:
        string_field = DocTypeFieldMetadata()
        string_field.value = "Policy"  # String instead of enum
        result4 = extract_field_value(string_field, "doc_type_string")
    except Exception as e:
        print(f"Error with string value: {e}")
        result4 = None
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    print(f"Null field result: '{result1}'")
    print(f"Null value result: '{result2}'")
    print(f"Enum value result: '{result3}'")
    print(f"String value result: '{result4}'")

if __name__ == "__main__":
    test_extract_field_value()