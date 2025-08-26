#!/usr/bin/env python3
"""
Simple test script to demonstrate the ground truth validation functionality.
"""

from ground_truth_validation import (
    load_ground_truth_metadata,
    print_ground_truth_stats
)

def main():
    excel_path = "/home/justus/Nextcloud/GHPL/documents-info.xlsx"
    
    print("🔍 Testing Ground Truth Validation System")
    print("="*50)
    
    # Load and display stats
    ground_truth = load_ground_truth_metadata(excel_path)
    print_ground_truth_stats(ground_truth)
    
    # Show some example entries
    print("\n📋 Sample Ground Truth Entries:")
    print("-" * 30)
    
    count = 0
    for filename, data in ground_truth.items():
        if count >= 3:  # Show only first 3
            break
        if data.get('title') and data.get('country'):
            print(f"\n📄 {filename}")
            print(f"   Title: {data['title']}")
            print(f"   Country: {data['country']}")
            if data.get('doc_type'):
                print(f"   Type: {data['doc_type']}")
            if data.get('year'):
                print(f"   Year: {data['year']}")
            count += 1
    
    print(f"\n✅ Ground truth validation system loaded successfully!")
    print(f"   Ready to validate {len(ground_truth)} documents")

if __name__ == "__main__":
    main()