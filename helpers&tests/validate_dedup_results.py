#!/usr/bin/env python3
"""
Validate deduplication results and generate a PDF summary report.
"""

import os
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import json

# For PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error hashing {filepath}: {e}")
        return None

def get_file_stats(folder):
    """Get file statistics for a folder."""
    if not os.path.exists(folder):
        return {"count": 0, "total_size": 0, "extensions": {}}
    
    count = 0
    total_size = 0
    extensions = Counter()
    
    for root, dirs, files in os.walk(folder):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                size = os.path.getsize(filepath)
                total_size += size
                count += 1
                ext = Path(file).suffix.lower()
                extensions[ext] += 1
            except Exception as e:
                print(f"Error getting stats for {filepath}: {e}")
    
    return {
        "count": count,
        "total_size": total_size,
        "total_size_mb": total_size / (1024 * 1024),
        "extensions": dict(extensions)
    }

def validate_duplicates(original_folder, duplicates_folder):
    """Validate that files in duplicates folder are actually duplicates."""
    print("🔍 Validating duplicate files...")
    
    if not os.path.exists(duplicates_folder):
        return {"verified_duplicates": 0, "invalid_duplicates": 0, "validation_errors": []}
    
    # Get hashes of all files in original folder
    original_hashes = {}
    print("  📊 Hashing original files...")
    for root, dirs, files in os.walk(original_folder):
        # Skip the special folders created by deduplication
        dirs[:] = [d for d in dirs if d not in ['duplicates', 'invalid', 'converted_originals']]
        
        for file in files:
            filepath = os.path.join(root, file)
            file_hash = calculate_file_hash(filepath)
            if file_hash:
                if file_hash in original_hashes:
                    original_hashes[file_hash].append(filepath)
                else:
                    original_hashes[file_hash] = [filepath]
    
    # Check files in duplicates folder
    verified_duplicates = 0
    invalid_duplicates = 0
    validation_errors = []
    
    print("  🔍 Validating duplicate files...")
    for root, dirs, files in os.walk(duplicates_folder):
        for file in files:
            filepath = os.path.join(root, file)
            file_hash = calculate_file_hash(filepath)
            
            if file_hash:
                if file_hash in original_hashes:
                    verified_duplicates += 1
                    print(f"    ✅ Verified duplicate: {file}")
                else:
                    invalid_duplicates += 1
                    validation_errors.append(f"File in duplicates/ has no match in originals: {file}")
                    print(f"    ❌ Invalid duplicate: {file}")
            else:
                validation_errors.append(f"Could not hash duplicate file: {filepath}")
    
    return {
        "verified_duplicates": verified_duplicates,
        "invalid_duplicates": invalid_duplicates,
        "validation_errors": validation_errors,
        "original_unique_hashes": len([h for h, files in original_hashes.items() if len(files) == 1]),
        "original_duplicate_hashes": len([h for h, files in original_hashes.items() if len(files) > 1])
    }

def analyze_folders(base_folder):
    """Analyze all folders and validate the deduplication results."""
    print(f"📁 Analyzing folders in {base_folder}...")
    
    results = {
        "analysis_date": datetime.now().isoformat(),
        "base_folder": str(base_folder),
        "folders": {}
    }
    
    # Define folder structure
    folders_to_check = {
        "main": base_folder,
        "invalid": os.path.join(base_folder, "invalid"),
        "duplicates": os.path.join(base_folder, "duplicates"),  
        "converted_originals": os.path.join(base_folder, "converted_originals")
    }
    
    # Get stats for each folder
    for folder_name, folder_path in folders_to_check.items():
        print(f"  📊 Analyzing {folder_name}...")
        stats = get_file_stats(folder_path)
        results["folders"][folder_name] = stats
        
        print(f"    Files: {stats['count']}")
        print(f"    Size: {stats['total_size_mb']:.1f} MB")
        if stats['extensions']:
            print(f"    Extensions: {dict(list(stats['extensions'].items())[:5])}")
    
    # Validate duplicates
    duplicate_validation = validate_duplicates(base_folder, folders_to_check["duplicates"])
    results["duplicate_validation"] = duplicate_validation
    
    # Calculate totals
    total_files = sum(stats['count'] for stats in results["folders"].values())
    total_size_mb = sum(stats['total_size_mb'] for stats in results["folders"].values())
    
    results["summary"] = {
        "total_files_all_folders": total_files,
        "total_size_mb_all_folders": total_size_mb,
        "claimed_vs_actual": {
            "claimed_duplicates_moved": 33,  # From log
            "actual_files_in_duplicates": results["folders"]["duplicates"]["count"],
            "claimed_invalid_pdfs": 110,    # From log
            "actual_files_in_invalid": results["folders"]["invalid"]["count"],
            "claimed_word_conversions": 211, # From log
            "actual_files_in_converted_originals": results["folders"]["converted_originals"]["count"]
        }
    }
    
    return results

def generate_text_report(results, output_file):
    """Generate a text report of the validation results."""
    print(f"📄 Generating text report: {output_file}")
    
    with open(output_file, 'w') as f:
        f.write("GHPL DEDUPLICATION RESULTS VALIDATION REPORT\n")
        f.write("=" * 50 + "\n\n")
        
        # Analysis info
        f.write(f"Analysis Date: {results['analysis_date']}\n")
        f.write(f"Base Folder: {results['base_folder']}\n\n")
        
        # Summary
        f.write("SUMMARY\n")
        f.write("-" * 20 + "\n")
        f.write(f"Total Files (All Folders): {results['summary']['total_files_all_folders']:,}\n")
        f.write(f"Total Size (All Folders): {results['summary']['total_size_mb_all_folders']:.1f} MB\n\n")
        
        # Folder breakdown
        f.write("FOLDER BREAKDOWN\n")
        f.write("-" * 20 + "\n")
        f.write(f"{'Folder':<20} {'Files':<10} {'Size (MB)':<12} {'Main Extensions':<30}\n")
        f.write("-" * 72 + "\n")
        
        for folder_name, stats in results['folders'].items():
            if stats['count'] > 0:
                main_exts = list(stats['extensions'].keys())[:3]
                ext_str = ', '.join(main_exts) if main_exts else 'None'
                f.write(f"{folder_name.title():<20} {stats['count']:<10,} {stats['total_size_mb']:<12.1f} {ext_str:<30}\n")
        
        f.write("\n")
        
        # Claims validation
        f.write("CLAIMS VALIDATION\n")
        f.write("-" * 20 + "\n")
        f.write(f"{'Claim':<20} {'Claimed':<10} {'Actual':<10} {'Status':<10}\n")
        f.write("-" * 50 + "\n")
        
        claims = results['summary']['claimed_vs_actual']
        
        # Duplicates
        dup_status = "✅ PASS" if claims['claimed_duplicates_moved'] == claims['actual_files_in_duplicates'] else "❌ FAIL"
        f.write(f"{'Duplicates Moved':<20} {claims['claimed_duplicates_moved']:<10} {claims['actual_files_in_duplicates']:<10} {dup_status:<10}\n")
        
        # Invalid PDFs  
        pdf_status = "✅ PASS" if claims['claimed_invalid_pdfs'] == claims['actual_files_in_invalid'] else "❌ FAIL"
        f.write(f"{'Invalid PDFs':<20} {claims['claimed_invalid_pdfs']:<10} {claims['actual_files_in_invalid']:<10} {pdf_status:<10}\n")
        
        # Word conversions
        word_status = "✅ PASS" if claims['claimed_word_conversions'] == claims['actual_files_in_converted_originals'] else "❌ FAIL"
        f.write(f"{'Word Conversions':<20} {claims['claimed_word_conversions']:<10} {claims['actual_files_in_converted_originals']:<10} {word_status:<10}\n")
        
        f.write("\n")
        
        # Duplicate validation results
        if 'duplicate_validation' in results:
            f.write("DUPLICATE VALIDATION\n")
            f.write("-" * 20 + "\n")
            dup_val = results['duplicate_validation']
            
            f.write(f"Verified Duplicates: {dup_val['verified_duplicates']}\n")
            f.write(f"Invalid Duplicates: {dup_val['invalid_duplicates']}\n")
            f.write(f"Original Unique Hashes: {dup_val['original_unique_hashes']}\n")
            f.write(f"Original Duplicate Hash Groups: {dup_val['original_duplicate_hashes']}\n")
            
            if dup_val['validation_errors']:
                f.write(f"\nValidation Errors ({len(dup_val['validation_errors'])}):\n")
                for i, error in enumerate(dup_val['validation_errors'][:10], 1):  # Show first 10 errors
                    f.write(f"  {i}. {error}\n")
                if len(dup_val['validation_errors']) > 10:
                    f.write(f"  ... and {len(dup_val['validation_errors']) - 10} more errors\n")
        
        f.write("\n")
        
        # File extensions summary
        f.write("FILE EXTENSIONS SUMMARY\n")
        f.write("-" * 25 + "\n")
        all_extensions = {}
        for folder_name, stats in results['folders'].items():
            for ext, count in stats['extensions'].items():
                all_extensions[ext] = all_extensions.get(ext, 0) + count
        
        for ext, count in sorted(all_extensions.items(), key=lambda x: x[1], reverse=True):
            f.write(f"{ext or 'no extension':<15} {count:>8,} files\n")
    
    return True

def main():
    """Main validation function."""
    print("🔍 GHPL DEDUPLICATION RESULTS VALIDATION")
    print("=" * 50)
    
    base_folder = "docs_all_complete"
    
    if not os.path.exists(base_folder):
        print(f"❌ Base folder {base_folder} not found!")
        return
    
    # Analyze folders and validate results
    results = analyze_folders(base_folder)
    
    # Save JSON report
    json_file = "dedup_validation_report.json"
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"💾 JSON report saved: {json_file}")
    
    # Generate text report
    txt_file = "dedup_validation_report.txt"
    if generate_text_report(results, txt_file):
        print(f"📄 Text report generated: {txt_file}")
    else:
        print("❌ Could not generate text report")
    
    # Print summary to console
    print("\n📊 VALIDATION SUMMARY:")
    print("=" * 30)
    
    claims = results['summary']['claimed_vs_actual']
    print(f"Duplicates moved: {claims['actual_files_in_duplicates']} (claimed: {claims['claimed_duplicates_moved']})")
    print(f"Invalid PDFs: {claims['actual_files_in_invalid']} (claimed: {claims['claimed_invalid_pdfs']})")
    print(f"Word conversions: {claims['actual_files_in_converted_originals']} (claimed: {claims['claimed_word_conversions']})")
    
    total_files = results['summary']['total_files_all_folders']
    total_size = results['summary']['total_size_mb_all_folders']
    print(f"\nTotal files across all folders: {total_files:,}")
    print(f"Total size: {total_size:.1f} MB")

if __name__ == "__main__":
    main()