#!/usr/bin/env python3
"""
Test extract_field_value function with actual enum values to find the bug.
"""

import sys
sys.path.append('.')

from meta import DocumentMetadata, DocTypeFieldMetadata, HealthTopicFieldMetadata, CreatorFieldMetadata, GovernanceLevelFieldMetadata
from meta import DocType, HealthTopic, Creator, GovernanceLevel

def test_extract_bug():
    def extract_field_value(field, field_name=""):
        print(f"\n=== Testing {field_name} ===")
        print(f"field = {field}")
        print(f"field is None: {field is None}")
        
        if field and hasattr(field, 'value'):
            print(f"field.value = {field.value}")
            print(f"field.value type: {type(field.value)}")
            print(f"field.value is None: {field.value is None}")
            
            if field.value is not None:
                print(f"hasattr(field.value, 'value'): {hasattr(field.value, 'value')}")
                if hasattr(field.value, 'value'):  # Enum field
                    print(f"field.value.value = {field.value.value}")
                    result = field.value.value
                    print(f"Returning enum value: '{result}'")
                    return result
                else:
                    result = field.value
                    print(f"Returning direct value: '{result}'")
                    return result
            else:
                print("field.value is None, returning None")
                return None
        else:
            print("field is None or has no 'value' attr, returning None")
            return None

    print("🧪 TESTING EXTRACT_FIELD_VALUE WITH ENUM VALUES")
    print("=" * 60)
    
    # Test with actual enum values that should work
    test_cases = [
        ("doc_type", DocTypeFieldMetadata(value=DocType.HEALTH_GUIDELINE, confidence=0.9)),
        ("health_topic", HealthTopicFieldMetadata(value=HealthTopic.CARDIOVASCULAR_HEALTH, confidence=0.8)),
        ("creator", CreatorFieldMetadata(value=Creator.AGENCY, confidence=0.85)),
        ("level", GovernanceLevelFieldMetadata(value=GovernanceLevel.NATIONAL, confidence=0.9)),
        ("doc_type_null", DocTypeFieldMetadata(value=None, confidence=0.0)),
    ]
    
    results = {}
    for field_name, field_obj in test_cases:
        result = extract_field_value(field_obj, field_name)
        results[field_name] = result
        print(f"FINAL RESULT for {field_name}: '{result}'")
        print("-" * 40)
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        print(f"{name:20}: '{result}'")
    
    # Check if there are differences in how enum types behave
    print("\n" + "=" * 60) 
    print("🔍 ENUM TYPE ANALYSIS")
    print("=" * 60)
    
    enums = [
        ("DocType.HEALTH_GUIDELINE", DocType.HEALTH_GUIDELINE),
        ("HealthTopic.CARDIOVASCULAR_HEALTH", HealthTopic.CARDIOVASCULAR_HEALTH),
        ("Creator.AGENCY", Creator.AGENCY),
        ("GovernanceLevel.NATIONAL", GovernanceLevel.NATIONAL),
    ]
    
    for name, enum_val in enums:
        print(f"{name}:")
        print(f"  value: {enum_val}")
        print(f"  type: {type(enum_val)}")
        print(f"  hasattr 'value': {hasattr(enum_val, 'value')}")
        if hasattr(enum_val, 'value'):
            print(f"  .value: {enum_val.value}")
        print()

if __name__ == "__main__":
    test_extract_bug()