import pandas as pd
import datetime
import os
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import urlparse, unquote
from get_metadata import DocumentMetadata, calculate_overall_confidence

def load_ground_truth_metadata(excel_path: str) -> dict:
    """Load reference metadata from Excel file."""
    if not Path(excel_path).exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    
    df = pd.read_excel(excel_path)
    
    # Create lookup dictionary keyed by filename extracted from public_file_url
    ground_truth = {}
    for _, row in df.iterrows():
        # Extract filename from public_file_url if available
        if pd.notna(row.get('public_file_url')):
            url = row['public_file_url']
            # Use same URL parsing as check_single_folder.py
            parsed_url = urlparse(url)
            filename = Path(os.path.basename(unquote(parsed_url.path))).stem
            # Handle additional URL encoding
            filename = filename.replace('%20', ' ').replace('%28', '(').replace('%29', ')')
        else:
            # Fallback to using id if no URL
            filename = f"doc_{row.get('id', 'unknown')}"
        
        ground_truth[filename] = {
            'title': row.get('title') if pd.notna(row.get('title')) else None,
            'creator': row.get('creator') if pd.notna(row.get('creator')) else None,
            'year': int(row.get('year')) if pd.notna(row.get('year')) else None,
            'doc_type': row.get('doc_type') if pd.notna(row.get('doc_type')) else None,
            'health_topic': row.get('health_topic') if pd.notna(row.get('health_topic')) else None,
            'country': row.get('country') if pd.notna(row.get('country')) else None,
            'language': row.get('language') if pd.notna(row.get('language')) else None,
            'level': None,  # Not available in Excel, but part of our schema
            # Additional fields for debugging
            'id': row.get('id'),
            'pdf_title': row.get('pdf_title') if pd.notna(row.get('pdf_title')) else None,
            'article_title': row.get('article_title') if pd.notna(row.get('article_title')) else None
        }
    
    print(f"Loaded ground truth for {len(ground_truth)} documents from {excel_path}")
    return ground_truth

def compare_with_ground_truth(extracted_metadata: DocumentMetadata, 
                             ground_truth: dict, 
                             pdf_filename: str) -> dict:
    """Compare extracted metadata with ground truth and calculate accuracy."""
    
    # Try multiple filename variations for matching
    filename_variants = [
        Path(pdf_filename).stem,
        Path(pdf_filename).name,
        pdf_filename,
        Path(pdf_filename).stem.replace('_', ' ').replace('-', ' ')
    ]
    
    reference = None
    filename_key = None
    
    for variant in filename_variants:
        if variant in ground_truth:
            reference = ground_truth[variant]
            filename_key = variant
            break
    
    if reference is None:
        return {"status": "no_reference", "accuracy": None, "filename_tried": filename_variants}
    
    results = {
        "status": "compared",
        "filename_key": filename_key,
        "matches": {},
        "discrepancies": {},
        "field_accuracy": {},
        "overall_accuracy": 0.0
    }
    
    fields_to_compare = ['title', 'creator', 'year', 'doc_type', 'health_topic', 'country', 'language', 'level']
    correct_fields = 0
    total_fields = 0
    
    for field in fields_to_compare:
        extracted_field = getattr(extracted_metadata, field)
        reference_value = reference.get(field)
        
        if reference_value is not None:  # Only compare if ground truth exists
            total_fields += 1
            extracted_value = extracted_field.value if hasattr(extracted_field, 'value') else extracted_field
            
            # Normalize values for comparison (handle enum values properly)
            ref_norm = str(reference_value).strip().lower()
            # For enum values, get the actual string value
            if hasattr(extracted_value, 'value'):
                ext_display = extracted_value.value
                ext_norm = str(extracted_value.value).strip().lower()
            else:
                ext_display = extracted_value
                ext_norm = str(extracted_value).strip().lower() if extracted_value else ""
            
            if ref_norm == ext_norm:
                results["matches"][field] = {
                    "extracted": ext_display,
                    "reference": reference_value,
                    "confidence": extracted_field.confidence if hasattr(extracted_field, 'confidence') else 1.0
                }
                correct_fields += 1
            else:
                results["discrepancies"][field] = {
                    "extracted": ext_display,
                    "reference": reference_value,
                    "confidence": extracted_field.confidence if hasattr(extracted_field, 'confidence') else 0.0
                }
            
            # Calculate field-level accuracy
            results["field_accuracy"][field] = 1.0 if ref_norm == ext_norm else 0.0
    
    # Calculate overall accuracy
    results["overall_accuracy"] = correct_fields / total_fields if total_fields > 0 else 0.0
    
    return results

def adjust_confidence_with_ground_truth(metadata: DocumentMetadata, 
                                       comparison_results: dict) -> DocumentMetadata:
    """Adjust confidence scores based on ground truth comparison."""
    
    if comparison_results["status"] != "compared":
        return metadata
    
    # Boost confidence for correct fields
    for field_name in comparison_results["matches"]:
        field = getattr(metadata, field_name)
        if hasattr(field, 'confidence'):
            # Boost confidence by 10% for ground truth matches
            field.confidence = min(1.0, field.confidence + 0.1)
            field.evidence += " [Validated against reference data]"
    
    # Lower confidence for incorrect fields
    for field_name in comparison_results["discrepancies"]:
        field = getattr(metadata, field_name)
        if hasattr(field, 'confidence'):
            # Reduce confidence by 30% for discrepancies
            field.confidence = max(0.0, field.confidence - 0.3)
            ref_value = comparison_results["discrepancies"][field_name]["reference"]
            field.evidence += f" [Differs from reference: '{ref_value}']"
            
            # Add reference value as alternative if not already present
            if hasattr(field, 'alternatives') and field.alternatives is not None:
                if str(ref_value) not in field.alternatives:
                    field.alternatives.append(str(ref_value))
    
    # Recalculate overall scores
    metadata.overall_confidence = calculate_overall_confidence(metadata)
    
    return metadata

def generate_accuracy_report(comparison_results: dict) -> str:
    """Generate human-readable accuracy report."""
    
    if comparison_results["status"] != "compared":
        return "No reference data available for comparison."
    
    report = []
    report.append(f"Overall Accuracy: {comparison_results['overall_accuracy']:.1%}")
    report.append(f"Matched filename: {comparison_results.get('filename_key', 'N/A')}")
    report.append("-" * 50)
    
    if comparison_results["matches"]:
        report.append("✅ Correct Extractions:")
        for field, data in comparison_results["matches"].items():
            conf = data["confidence"]
            report.append(f"  • {field}: '{data['extracted']}' (confidence: {conf:.2f})")
    
    if comparison_results["discrepancies"]:
        report.append("\n❌ Discrepancies Found:")
        for field, data in comparison_results["discrepancies"].items():
            conf = data["confidence"]
            report.append(f"  • {field}:")
            report.append(f"    - Extracted: '{data['extracted']}' (confidence: {conf:.2f})")
            report.append(f"    - Reference: '{data['reference']}'")
    
    return "\n".join(report)

def track_all_deviations(comparison_results: dict, pdf_filename: str, 
                        extracted_metadata: DocumentMetadata) -> dict:
    """Track ALL deviations between extraction and Excel reference data."""
    
    if comparison_results["status"] != "compared":
        return {"status": "no_tracking"}
    
    deviation_entry = {
        "document": pdf_filename,
        "filename_key": comparison_results.get("filename_key"),
        "timestamp": datetime.datetime.now().isoformat(),
        "overall_accuracy": comparison_results["overall_accuracy"],
        "all_deviations": []
    }
    
    # Log every single discrepancy without any filtering
    for field, data in comparison_results["discrepancies"].items():
        field_obj = getattr(extracted_metadata, field)
        deviation = {
            "field": field,
            "extracted_value": data["extracted"],
            "reference_value": data["reference"],
            "extraction_confidence": data["confidence"],
            "evidence": field_obj.evidence if hasattr(field_obj, 'evidence') else "",
            "source_page": field_obj.source_page if hasattr(field_obj, 'source_page') else None,
            "alternatives": field_obj.alternatives if hasattr(field_obj, 'alternatives') else []
        }
        deviation_entry["all_deviations"].append(deviation)
    
    return deviation_entry

def generate_deviation_report(deviation_log: list) -> str:
    """Generate comprehensive deviation report for Excel data quality assessment."""
    
    if not deviation_log:
        return "No deviations tracked."
    
    report = []
    report.append("=== DEVIATION ANALYSIS REPORT ===")
    report.append(f"Total documents analyzed: {len(deviation_log)}")
    
    # Collect all deviations
    all_deviations = []
    for entry in deviation_log:
        for dev in entry["all_deviations"]:
            dev["document"] = entry["document"]
            all_deviations.append(dev)
    
    if not all_deviations:
        report.append("✅ No deviations found - perfect alignment!")
        return "\n".join(report)
    
    report.append(f"Total deviations found: {len(all_deviations)}")
    
    # Group by field
    field_deviations = {}
    for dev in all_deviations:
        field = dev["field"]
        if field not in field_deviations:
            field_deviations[field] = []
        field_deviations[field].append(dev)
    
    report.append("\n=== DEVIATIONS BY FIELD ===")
    for field, deviations in field_deviations.items():
        report.append(f"\n{field.upper()} ({len(deviations)} deviations):")
        for dev in deviations[:5]:  # Show first 5 examples
            report.append(f"  📄 {dev['document']}")
            report.append(f"    Extracted: '{dev['extracted_value']}' (confidence: {dev['extraction_confidence']:.2f})")
            report.append(f"    Reference: '{dev['reference_value']}'")
            if dev['evidence']:
                report.append(f"    Evidence: {dev['evidence']}")
        
        if len(deviations) > 5:
            report.append(f"    ... and {len(deviations) - 5} more")
    
    return "\n".join(report)

def export_deviations_to_excel(deviation_log: list, output_path: str = "all_deviations.xlsx", append_mode: bool = False):
    """Export all deviations to Excel for manual review and Excel data correction.
    
    Args:
        deviation_log: List of deviation entries
        output_path: Excel file path
        append_mode: If True, append to existing file instead of overwriting
    """
    
    rows = []
    for entry in deviation_log:
        if not isinstance(entry, dict):
            continue
            
        # Handle different deviation entry structures
        all_deviations = entry.get("all_deviations", [])
        if not all_deviations:
            continue
            
        for dev in all_deviations:
            try:
                rows.append({
                    "document": entry.get("document", "unknown"),
                    "filename_key": entry.get("filename_key", ""),
                    "field": dev.get("field", ""),
                    "extracted_value": dev.get("extracted_value", ""),
                    "reference_value": dev.get("reference_value", ""),
                    "extraction_confidence": dev.get("extraction_confidence", 0.0),
                    "evidence": dev.get("evidence", ""),
                    "source_page": dev.get("source_page", ""),
                    "alternatives": ", ".join(dev.get("alternatives", [])) if dev.get("alternatives") else "",
                    "timestamp": entry.get("timestamp", "")
                })
            except Exception as e:
                print(f"Warning: Skipping malformed deviation entry: {e}")
    
    if rows:
        # Create DataFrame with new data
        new_df = pd.DataFrame(rows)
        
        if append_mode and os.path.exists(output_path):
            # Append mode - load existing data and combine
            try:
                existing_df = pd.read_excel(output_path)
                # Combine DataFrames, avoiding duplicates based on document + field + timestamp
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                # Remove duplicates based on document, field, and timestamp
                combined_df = combined_df.drop_duplicates(
                    subset=['document', 'field', 'timestamp'], keep='last'
                )
                combined_df.to_excel(output_path, index=False)
                print(f"Deviations appended to existing file: {output_path}")
                print(f"   • Previous entries: {len(existing_df)}")
                print(f"   • New entries: {len(new_df)}")
                print(f"   • Total entries: {len(combined_df)}")
            except Exception as e:
                print(f"Warning: Could not append to existing deviations file, overwriting: {e}")
                new_df.to_excel(output_path, index=False)
        else:
            # Normal mode - overwrite file
            new_df.to_excel(output_path, index=False)
        
        return output_path
    else:
        print("No deviations to export")
        return None

def print_ground_truth_stats(ground_truth: dict):
    """Print statistics about the ground truth data."""
    if not ground_truth:
        print("No ground truth data loaded")
        return
    
    print(f"\n=== Ground Truth Statistics ===")
    print(f"Total documents in reference: {len(ground_truth)}")
    
    # Count field availability
    field_counts = {}
    for doc in ground_truth.values():
        for field, value in doc.items():
            if field not in ['id', 'pdf_title', 'article_title']:  # Skip metadata fields
                if field not in field_counts:
                    field_counts[field] = 0
                if value is not None:
                    field_counts[field] += 1
    
    print("\nField availability:")
    for field, count in sorted(field_counts.items()):
        percentage = (count / len(ground_truth)) * 100
        print(f"  {field}: {count} ({percentage:.1f}%)")