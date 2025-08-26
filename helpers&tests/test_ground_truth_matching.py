#!/usr/bin/env python3
"""
Test ground truth matching to verify if it's working correctly.
"""

import os
from pathlib import Path
from ground_truth_validation import load_ground_truth_metadata, compare_with_ground_truth
from get_metadata import DocumentMetadata

def test_ground_truth_matching():
    """Test ground truth matching without API calls."""
    
    # Load ground truth
    print("Loading ground truth...")
    ground_truth = load_ground_truth_metadata('documents-info.xlsx')
    print(f"Loaded {len(ground_truth)} entries")
    
    # Test with actual PDF files
    docs_folder = 'docs_correct'
    if not os.path.exists(docs_folder):
        print(f"❌ {docs_folder} not found")
        return
    
    pdf_files = [f for f in os.listdir(docs_folder) if f.endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDF files")
    
    # Test ground truth matching for first 20 files
    match_count = 0
    no_match_count = 0
    
    print("\n" + "="*80)
    print("GROUND TRUTH MATCHING TEST")
    print("="*80)
    
    for i, pdf_file in enumerate(pdf_files[:20]):  # Test first 20
        pdf_path = os.path.join(docs_folder, pdf_file)
        
        # Create a dummy metadata object (we're only testing the matching logic)
        class DummyField:
            def __init__(self, value):
                self.value = value
                self.confidence = 0.8
                self.evidence = "test"
                self.source_page = 1
                self.alternatives = []
        
        dummy_metadata = type('DocumentMetadata', (), {
            'title': DummyField('Test Title'),
            'doc_type': DummyField('Policy'), 
            'health_topic': DummyField('Cancer'),
            'creator': DummyField('Ministry'),
            'year': DummyField(2023),
            'country': DummyField('USA'),
            'language': DummyField('English'),
            'level': DummyField('National')
        })()
        
        # Test ground truth matching
        comparison_results = compare_with_ground_truth(dummy_metadata, ground_truth, pdf_path)
        
        if comparison_results["status"] == "compared":
            match_count += 1
            filename_key = comparison_results.get('filename_key')
            print(f"✅ {pdf_file[:50]:50} -> {filename_key}")
        else:
            no_match_count += 1
            tried_filenames = comparison_results.get('filename_tried', [])
            print(f"❌ {pdf_file[:50]:50} -> No match")
            print(f"   Tried: {tried_filenames}")
            
            # Look for similar keys in ground truth
            file_stem = Path(pdf_file).stem
            similar_keys = [key for key in ground_truth.keys() if file_stem.lower() in key.lower() or key.lower() in file_stem.lower()][:3]
            if similar_keys:
                print(f"   Similar: {similar_keys}")
        
        if i >= 19:  # Stop after 20
            break
    
    print(f"\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total tested: {match_count + no_match_count}")
    print(f"Matches found: {match_count} ({match_count/(match_count + no_match_count)*100:.1f}%)")
    print(f"No matches: {no_match_count}")
    
    if no_match_count > 0:
        print(f"\n🔍 DIAGNOSIS:")
        print(f"If files exist in docs_correct but don't match ground truth,")
        print(f"the issue might be in filename encoding or ground truth key generation.")
    
    return match_count, no_match_count

if __name__ == "__main__":
    test_ground_truth_matching()