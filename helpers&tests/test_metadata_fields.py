#!/usr/bin/env python3
"""
Test what fields actually exist on DocumentMetadata objects.
"""

import sys
sys.path.append('.')

from meta import DocumentMetadata, StringFieldMetadata, DocTypeFieldMetadata, HealthTopicFieldMetadata, CreatorFieldMetadata, GovernanceLevelFieldMetadata, IntFieldMetadata

def test_metadata_fields():
    print("🧪 TESTING DOCUMENTMETADATA FIELD ACCESS")
    print("=" * 50)
    
    # Create a DocumentMetadata object with default values
    metadata = DocumentMetadata(
        doc_type=DocTypeFieldMetadata(),
        health_topic=HealthTopicFieldMetadata(),
        creator=CreatorFieldMetadata(),
        level=GovernanceLevelFieldMetadata(),
        title=StringFieldMetadata(),
        country=StringFieldMetadata(),
        language=StringFieldMetadata(),
        year=IntFieldMetadata()
    )
    
    print(f"Object type: {type(metadata)}")
    print(f"All attributes: {[attr for attr in dir(metadata) if not attr.startswith('_')]}")
    print()
    
    # Test field access
    fields_to_test = ['doc_type', 'health_topic', 'creator', 'level', 'title', 'country', 'language', 'year']
    
    for field_name in fields_to_test:
        has_field = hasattr(metadata, field_name)
        print(f"hasattr(metadata, '{field_name}'): {has_field}")
        
        if has_field:
            try:
                field_value = getattr(metadata, field_name)
                print(f"  getattr result: {field_value}")
                print(f"  type: {type(field_value)}")
                if hasattr(field_value, 'value'):
                    print(f"  field.value: {field_value.value}")
            except Exception as e:
                print(f"  ERROR accessing field: {e}")
        print()

if __name__ == "__main__":
    test_metadata_fields()