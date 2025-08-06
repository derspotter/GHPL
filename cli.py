#!/usr/bin/env python3
"""
CLI tool for PDF metadata extraction with ground truth validation.
Integrates all existing functions from get_metadata.py and ground_truth_validation.py.
"""

import os
import argparse
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from google import genai
from google.genai import types
import pandas as pd
import pydantic

# Import existing functions
from get_metadata import (
    prepare_and_upload_pdf_subset,
    get_metadata_from_gemini,
    get_confidence_level,
    recommend_action
)

from ground_truth_validation import (
    load_ground_truth_metadata,
    compare_with_ground_truth,
    adjust_confidence_with_ground_truth,
    generate_accuracy_report,
    track_all_deviations,
    export_deviations_to_excel,
    print_ground_truth_stats
)

# Pydantic models for search resolution results
class FieldResolution(pydantic.BaseModel):
    """Resolution for a single metadata field conflict."""
    resolved_value: str = pydantic.Field(description="The resolved value based on search results")
    confidence: float = pydantic.Field(ge=0.0, le=1.0, description="Confidence in the resolution (0.0-1.0)")
    recommendation: str = pydantic.Field(description="One of: extracted, reference, alternative, needs_review")
    reasoning: str = pydantic.Field(description="Explanation of why this resolution was chosen")

class SearchResolutionResponse(pydantic.BaseModel):
    """Complete response from search grounding resolution."""
    resolutions: Dict[str, FieldResolution] = pydantic.Field(description="Resolution for each conflicting field")
    search_evidence: str = pydantic.Field(description="Key evidence from search results")
    sources: List[str] = pydantic.Field(default_factory=list, description="URLs or source descriptions")
    overall_confidence: float = pydantic.Field(ge=0.0, le=1.0, description="Overall confidence in resolutions")

# Search grounding functions for automatic conflict resolution
def query_gemini_with_search(discrepancies: dict, extracted_metadata, pdf_filename: str, client, verbose: bool = True) -> dict:
    """Use ONE search to resolve ALL metadata conflicts for this document."""
    
    if verbose:
        print("\n📝 PREPARING SEARCH GROUNDING REQUEST")
        print("="*50)
    
    # Build conflict summary
    conflict_summary = []
    for field_name, conflict_data in discrepancies.items():
        conflict_summary.append(f"• {field_name}: Extracted='{conflict_data['extracted']}' vs Reference='{conflict_data['reference']}'")
    
    # Extract document context for search
    title = extracted_metadata.title.value or Path(pdf_filename).stem.replace("_", " ")
    country = extracted_metadata.country.value or "unknown country"
    
    if verbose:
        print(f"Document context:")
        print(f"  Title: {title}")
        print(f"  Country: {country}")
        print(f"  Filename: {Path(pdf_filename).stem}")
        print(f"\nConflicts to resolve ({len(discrepancies)}):")
        for conflict in conflict_summary:
            print(f"  {conflict}")
    
    # Build the expected schema for the response
    schema_example = {
        "resolutions": {},
        "search_evidence": "key evidence from search results",
        "sources": ["URL or source description"],
        "overall_confidence": 0.0
    }
    
    # Add resolution structure for each conflicting field
    for field_name in discrepancies.keys():
        schema_example["resolutions"][field_name] = {
            "resolved_value": "the most accurate value based on search",
            "confidence": 0.0,
            "recommendation": "extracted|reference|alternative|needs_review",
            "reasoning": "explanation of resolution"
        }
    
    analysis_prompt = f"""
    I have multiple metadata conflicts for a health policy document from {country}:
    Document title: "{title}"
    Filename: {Path(pdf_filename).stem}
    
    Conflicts to resolve:
    {chr(10).join(conflict_summary)}
    
    Please search for information about this document and resolve ALL conflicts. Consider:
    
    1. **Official Sources**: Government websites, institutional publications
    2. **Document Catalogs**: Library systems, policy databases  
    3. **Publication Records**: Official publication dates and titles
    4. **Organization Information**: Official names and attributions
    
    Based on your search results, provide resolutions following this EXACT JSON structure:
    
    ```json
    {json.dumps(schema_example, indent=2)}
    ```
    
    For the "recommendation" field, use one of these exact values:
    - "extracted": if search confirms the extracted value is correct
    - "reference": if search confirms the reference value is correct  
    - "alternative": if search finds a different value is correct
    - "needs_review": if search cannot determine with confidence
    
    **Critical**: Only provide confidence >0.8 if search results clearly support one value.
    **IMPORTANT**: Return your response as a valid JSON object wrapped in ```json``` markdown code blocks.
    """
    
    try:
        if verbose:
            print("\n🌐 EXECUTING SEARCH GROUNDING")
            print("-"*50)
            print("Model: gemini-2.5-pro")
            print("Search tool: Google Search grounding enabled")
        
        # Configure Google Search grounding tool (correct syntax per docs)
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[analysis_prompt],
            config=types.GenerateContentConfig(
                tools=[grounding_tool]  # Enable search grounding
                # Note: response_mime_type='application/json' is incompatible with tools
            )
        )
        
        if verbose:
            print("✅ Search grounding request completed")
            print("\n📊 RAW RESPONSE")
            print("-"*50)
            print(f"Response text: {response.text[:500]}..." if len(response.text) > 500 else f"Response text: {response.text}")
            
            # Check for grounding metadata
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata'):
                    print("\n🔍 GROUNDING METADATA FOUND")
                    grounding_meta = candidate.grounding_metadata
                    if hasattr(grounding_meta, 'search_entry_point') and grounding_meta.search_entry_point:
                        try:
                            # SearchEntryPoint might be an object, not a string
                            entry_str = str(grounding_meta.search_entry_point)
                            print(f"Search entry point: {entry_str[:100]}...")
                        except:
                            print("Search entry point: [Found but not displayable]")
                    if hasattr(grounding_meta, 'grounding_chunks') and grounding_meta.grounding_chunks:
                        print(f"Number of search results: {len(grounding_meta.grounding_chunks)}")
                else:
                    print("\n⚠️  No grounding metadata in response")
        
        # Try to extract JSON from the response text
        response_text = response.text
        
        # Look for JSON in markdown code blocks first
        import re
        json_text = None
        
        # Try to find JSON in ```json``` blocks
        json_block_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_block_match:
            json_text = json_block_match.group(1)
        else:
            # Fall back to finding any JSON object
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
            else:
                json_text = response_text
        
        result = json.loads(json_text)
        
        # Validate with Pydantic if possible
        try:
            validated_result = SearchResolutionResponse.model_validate(result)
            if verbose:
                print("✅ Response validated with Pydantic schema")
        except Exception as e:
            if verbose:
                print(f"⚠️  Pydantic validation failed: {e}")
                print("   Using raw JSON result")
        
        if verbose:
            print("\n📋 PARSED SEARCH RESULTS")
            print("-"*50)
            print(f"Overall confidence: {result.get('overall_confidence', 'N/A')}")
            print(f"Search evidence: {result.get('search_evidence', 'N/A')[:200]}..." if len(result.get('search_evidence', '')) > 200 else f"Search evidence: {result.get('search_evidence', 'N/A')}")
            print(f"Sources: {result.get('sources', [])}")
            
            resolutions = result.get('resolutions', {})
            print(f"\nField resolutions ({len(resolutions)}):")
            for field, resolution in resolutions.items():
                print(f"  • {field}:")
                print(f"    - Resolved value: {resolution.get('resolved_value', 'N/A')}")
                print(f"    - Confidence: {resolution.get('confidence', 'N/A')}")
                print(f"    - Recommendation: {resolution.get('recommendation', 'N/A')}")
                print(f"    - Reasoning: {resolution.get('reasoning', 'N/A')[:100]}..." if len(resolution.get('reasoning', '')) > 100 else f"    - Reasoning: {resolution.get('reasoning', 'N/A')}")
        
        return result
        
    except json.JSONDecodeError as e:
        if verbose:
            print(f"\n❌ JSON PARSING ERROR: {e}")
            print(f"Raw response: {response.text[:1000]}")
        return {
            "resolutions": {},
            "search_evidence": f"JSON parsing failed: {e}",
            "sources": [],
            "overall_confidence": 0.0
        }
    except Exception as e:
        if verbose:
            print(f"\n❌ SEARCH GROUNDING ERROR: {type(e).__name__}: {e}")
        return {
            "resolutions": {},
            "search_evidence": f"Search analysis failed: {e}",
            "sources": [],
            "overall_confidence": 0.0
        }

def resolve_deviations_with_search(discrepancies: dict, pdf_filename: str, 
                                  extracted_metadata, client, confidence_threshold: float = 0.8, verbose: bool = True) -> dict:
    """Use ONE search to resolve ALL metadata conflicts for this document."""
    
    if not discrepancies:
        return {"resolved": {}, "remaining": {}, "resolution_rate": 1.0}
    
    print("🔍 Attempting to resolve conflicts with search grounding...")
    print(f"   Confidence threshold: {confidence_threshold}")
    print(f"   Number of conflicts: {len(discrepancies)}")
    
    # Execute single search for all conflicts (Gemini auto-generates queries)
    search_results = query_gemini_with_search(discrepancies, extracted_metadata, pdf_filename, client, verbose)
    
    if verbose:
        print("\n📈 PROCESSING SEARCH RESOLUTIONS")
        print("-"*50)
        print(f"Threshold for auto-resolution: {confidence_threshold}")
    
    # Debug: Check what we actually got
    if verbose:
        print(f"\n🔍 DEBUG SEARCH RESULTS STRUCTURE")
        print(f"Type of search_results: {type(search_results)}")
        print(f"Keys in search_results: {list(search_results.keys()) if isinstance(search_results, dict) else 'Not a dict'}")
        if isinstance(search_results, dict) and "resolutions" in search_results:
            resolutions = search_results["resolutions"]
            print(f"Type of resolutions: {type(resolutions)}")
            print(f"Keys in resolutions: {list(resolutions.keys()) if isinstance(resolutions, dict) else 'Not a dict'}")
        else:
            print("⚠️  No 'resolutions' key found in search_results")
    
    # Process results for each field
    resolved_conflicts = {}
    remaining_conflicts = {}
    
    for field_name, conflict_data in discrepancies.items():
        field_resolution = search_results.get("resolutions", {}).get(field_name)
        
        if verbose:
            print(f"\n  Field: {field_name}")
            print(f"    Looking for resolution...")
            print(f"    Found field_resolution: {field_resolution is not None}")
            if field_resolution:
                print(f"    Resolution keys: {list(field_resolution.keys()) if isinstance(field_resolution, dict) else 'Not a dict'}")
        
        if field_resolution:
            confidence = field_resolution.get("confidence", 0)
            if verbose:
                print(f"    Search confidence: {confidence}")
                print(f"    Meets threshold: {'✅ Yes' if confidence >= confidence_threshold else '❌ No'}")
            
            if confidence >= confidence_threshold:
                resolved_conflicts[field_name] = field_resolution
                resolved_conflicts[field_name]["search_evidence"] = search_results.get("search_evidence", "")
                resolved_conflicts[field_name]["sources"] = search_results.get("sources", [])
                if verbose:
                    print(f"    → RESOLVED as: {field_resolution.get('resolved_value')}")
            else:
                remaining_conflicts[field_name] = conflict_data
                remaining_conflicts[field_name]["search_notes"] = field_resolution.get("reasoning", "Inconclusive")
                if verbose:
                    print(f"    → UNRESOLVED (confidence too low)")
        else:
            remaining_conflicts[field_name] = conflict_data
            if verbose:
                print(f"    → NO RESOLUTION from search")
    
    resolution_rate = len(resolved_conflicts) / len(discrepancies) if discrepancies else 0
    
    if verbose:
        print(f"\n📊 RESOLUTION SUMMARY")
        print("-"*50)
        print(f"Total conflicts: {len(discrepancies)}")
        print(f"Resolved: {len(resolved_conflicts)} ({resolution_rate:.1%})")
        print(f"Remaining: {len(remaining_conflicts)}")
    
    return {
        "resolved": resolved_conflicts,
        "remaining": remaining_conflicts,
        "resolution_rate": resolution_rate,
        "search_used": True
    }

def apply_search_resolution(metadata, resolved_conflicts: dict):
    """Update metadata based on search-grounded conflict resolution."""
    
    for field_name, resolution in resolved_conflicts.items():
        field = getattr(metadata, field_name)
        recommendation = resolution["recommendation"]
        
        if recommendation == "extracted":
            # Search supports extracted value
            field.confidence = min(1.0, field.confidence + 0.3)  # Major boost
            field.evidence += f" [Search validated: {resolution.get('reasoning', 'Search confirmed')}]"
            
        elif recommendation == "reference":
            # Search supports reference value - update field
            if hasattr(field.value, 'value'):  # Handle enum values
                # For enums, we need to find the matching enum value
                field.value = resolution["resolved_value"]
            else:
                field.value = resolution["resolved_value"]
            field.confidence = 0.9  # High confidence from search validation
            field.evidence = f"Search-corrected from reference data: {resolution.get('reasoning', 'Search confirmed reference')}"
            
        elif recommendation == "alternative":
            # Search found different value
            field.value = resolution["resolved_value"]
            field.confidence = 0.85  # High confidence for search-found alternative
            field.evidence = f"Search-discovered value: {resolution.get('reasoning', 'Search found alternative')}"
            if hasattr(field, 'alternatives'):
                field.alternatives.extend([str(field.value), resolution.get("reference_value", "")])
            
        # Add search sources as evidence
        if resolution.get("sources"):
            field.evidence += f" [Sources: {', '.join(resolution['sources'][:2])}]"
    
    return metadata

def generate_search_resolution_report(resolution_results: dict) -> str:
    """Generate report showing how search grounding resolved conflicts."""
    
    report = []
    report.append("🔍 SEARCH-GROUNDED CONFLICT RESOLUTION")
    report.append("=" * 50)
    
    resolved = resolution_results["resolved"]
    remaining = resolution_results["remaining"]
    resolution_rate = resolution_results["resolution_rate"]
    
    report.append(f"Resolution Rate: {resolution_rate:.1%}")
    report.append(f"Automatically Resolved: {len(resolved)}")
    report.append(f"Still Need Review: {len(remaining)}")
    
    if resolved:
        report.append("\n✅ AUTOMATICALLY RESOLVED:")
        for field, resolution in resolved.items():
            report.append(f"  • {field}: '{resolution['resolved_value']}'")
            report.append(f"    └─ Confidence: {resolution['confidence']:.2f}")
            report.append(f"    └─ Reasoning: {resolution.get('reasoning', 'N/A')}")
            if resolution.get('sources'):
                report.append(f"    └─ Sources: {', '.join(resolution['sources'][:1])}")
    
    if remaining:
        report.append("\n⚠️  STILL NEED REVIEW:")
        for field, conflict in remaining.items():
            report.append(f"  • {field}: '{conflict['extracted']}' vs '{conflict['reference']}'")
            if conflict.get('search_notes'):
                report.append(f"    └─ Search Notes: {conflict['search_notes']}")
    
    return "\n".join(report)

# Interactive resolution functions
def prompt_user_choice(field_name: str, extracted_value: Any, reference_value: Any, 
                      confidence: float, evidence: str) -> Tuple[Any, str]:
    """Prompt user to choose between extracted and reference values."""
    print(f"\n{'='*60}")
    print(f"DISCREPANCY FOUND IN FIELD: {field_name.upper()}")
    print(f"{'='*60}")
    
    print(f"📊 Extracted Value: '{extracted_value}'")
    print(f"   ├─ Confidence: {confidence:.2f}")
    print(f"   └─ Evidence: {evidence}")
    
    print(f"\n📚 Reference Value: '{reference_value}'")
    print(f"   └─ From ground truth data")
    
    print(f"\nChoose:")
    print(f"  [1] Use extracted value: '{extracted_value}'")
    print(f"  [2] Use reference value: '{reference_value}'")
    print(f"  [3] Enter custom value")
    print(f"  [4] Flag as unresolved/needs review")
    print(f"  [s] Skip this field (keep extracted)")
    
    while True:
        choice = input("\nEnter your choice (1/2/3/4/s): ").strip().lower()
        
        if choice == '1':
            return extracted_value, f"User chose extracted value over reference '{reference_value}'"
        elif choice == '2':
            return reference_value, f"User chose reference value over extracted '{extracted_value}'"
        elif choice == '3':
            custom_value = input(f"Enter custom value for {field_name}: ").strip()
            if custom_value:
                return custom_value, f"User entered custom value, alternatives were: extracted='{extracted_value}', reference='{reference_value}'"
            else:
                print("Empty value entered, please try again.")
        elif choice == '4':
            return None, f"User flagged as unresolved: extracted='{extracted_value}', reference='{reference_value}'"
        elif choice == 's':
            return extracted_value, f"User skipped, kept extracted value over reference '{reference_value}'"
        else:
            print("Invalid choice. Please enter 1, 2, 3, 4, or s.")

def show_pre_resolution_summary(comparison_results: Dict[str, Any]):
    """Show a summary before starting interactive resolution."""
    if comparison_results["status"] != "compared":
        return
    
    discrepancies = comparison_results.get("discrepancies", {})
    matches = comparison_results.get("matches", {})
    
    print(f"\n📊 VALIDATION SUMMARY")
    print(f"{'='*40}")
    print(f"Overall Accuracy: {comparison_results['overall_accuracy']:.1%}")
    print(f"Correct fields: {len(matches)}")
    print(f"Discrepancies: {len(discrepancies)}")
    
    if discrepancies:
        print(f"\nFields with discrepancies:")
        for field, data in discrepancies.items():
            print(f"  • {field}: '{data['extracted']}' vs '{data['reference']}'")

def batch_choice_prompt(discrepancies: Dict[str, Any]) -> str:
    """Ask user if they want to apply the same choice to all discrepancies."""
    if len(discrepancies) <= 1:
        return "ask"  # Individual handling for single discrepancy
    
    print(f"\n{'='*80}")
    print(f"BATCH PROCESSING - {len(discrepancies)} DISCREPANCIES FOUND")
    print(f"{'='*80}")
    print(f"\nHere are all the fields with discrepancies:\n")
    
    # Display all discrepancies in a table format
    print(f"{'Field':<15} {'Extracted Value':<35} {'Reference Value':<35}")
    print(f"{'-'*15} {'-'*35} {'-'*35}")
    
    for field_name, data in discrepancies.items():
        extracted = str(data["extracted"])[:33] + ".." if len(str(data["extracted"])) > 35 else str(data["extracted"])
        reference = str(data["reference"])[:33] + ".." if len(str(data["reference"])) > 35 else str(data["reference"])
        print(f"{field_name:<15} {extracted:<35} {reference:<35}")
    
    print(f"\n🔄 BATCH OPTIONS")
    print(f"Would you like to:")
    print(f"  [a] Handle each field individually (see detailed evidence)")
    print(f"  [e] Keep ALL extracted values (trust AI extraction)")  
    print(f"  [r] Use ALL reference values (trust ground truth data)")
    
    while True:
        choice = input("\nEnter your choice (a/e/r): ").strip().lower()
        
        if choice == 'a':
            return "ask"  # Individual handling
        elif choice == 'e':
            return "keep_extracted"
        elif choice == 'r':
            return "keep_reference"
        else:
            print("Invalid choice. Please enter a, e, or r.")

def adjust_confidence_for_user_choice(field, choice_reason: str):
    """Adjust confidence based on user interaction."""
    if "reference value" in choice_reason:
        field.confidence = min(1.0, field.confidence + 0.2)  # Boost for reference choice
    elif "custom value" in choice_reason:
        field.confidence = 0.9  # High confidence for manual entry
    elif "extracted value" in choice_reason:
        # Keep original confidence for extracted value choices
        pass
    elif "unresolved" in choice_reason or "needs review" in choice_reason:
        field.confidence = 0.1  # Very low confidence for unresolved conflicts
        field.value = None  # Clear conflicted value
    
    field.evidence += f" [Interactive choice: {choice_reason}]"

def interactive_resolve_discrepancies(metadata, comparison_results: Dict[str, Any], 
                                    auto_mode: str = "ask"):
    """Interactively resolve discrepancies between extracted and reference metadata."""
    if comparison_results["status"] != "compared":
        print("No ground truth comparison available - no discrepancies to resolve")
        return metadata, [], []
    
    discrepancies = comparison_results.get("discrepancies", {})
    if not discrepancies:
        print("✅ No discrepancies found - all values match ground truth!")
        return metadata, [], []
    
    print(f"\n📋 Found {len(discrepancies)} discrepancies to resolve")
    
    # Handle auto modes
    if auto_mode == "keep_extracted":
        print("🤖 Auto-mode: Keeping all extracted values")
        return metadata, [], []
    elif auto_mode == "keep_reference":
        print("🤖 Auto-mode: Using all reference values")
        user_decisions = []
        for field_name, data in discrepancies.items():
            field = getattr(metadata, field_name)
            field.value = data["reference"]
            reason = f"Auto-selected reference value over extracted '{data['extracted']}'"
            adjust_confidence_for_user_choice(field, reason)
            user_decisions.append({
                'field': field_name,
                'choice': 'reference',
                'extracted': data['extracted'],
                'reference': data['reference'],
                'final_value': data['reference'],
                'reason': reason,
                'timestamp': datetime.datetime.now().isoformat()
            })
        return metadata, user_decisions, []
    
    # Interactive mode - prompt for each discrepancy
    updated_fields = []
    user_decisions = []
    unresolved_items = []
    
    for field_name, data in discrepancies.items():
        field = getattr(metadata, field_name)
        
        chosen_value, choice_reason = prompt_user_choice(
            field_name=field_name,
            extracted_value=data["extracted"],
            reference_value=data["reference"],
            confidence=data["confidence"],
            evidence=field.evidence
        )
        
        # Track user decision
        decision = {
            'field': field_name,
            'extracted': data['extracted'],
            'reference': data['reference'],
            'final_value': chosen_value,
            'reason': choice_reason,
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        if "unresolved" in choice_reason:
            unresolved_items.append(decision)
            decision['choice'] = 'unresolved'
        elif "reference value" in choice_reason:
            decision['choice'] = 'reference'
        elif "custom value" in choice_reason:
            decision['choice'] = 'custom'
        else:
            decision['choice'] = 'extracted'
        
        user_decisions.append(decision)
        
        # Update the field
        field.value = chosen_value
        adjust_confidence_for_user_choice(field, choice_reason)
        updated_fields.append(field_name)
    
    if updated_fields:
        print(f"\n✅ Updated fields: {', '.join(updated_fields)}")
    
    return metadata, user_decisions, unresolved_items

def export_corrected_metadata(user_decisions: List[Dict], output_path: str = "user_corrected_metadata.xlsx"):
    """Export user-corrected metadata to separate Excel file."""
    if not user_decisions:
        print("No user corrections to export")
        return None
    
    rows = []
    for decision in user_decisions:
        rows.append({
            'field': decision['field'],
            'extracted_value': decision['extracted'],
            'reference_value': decision['reference'],
            'final_value': decision['final_value'],
            'choice_type': decision['choice'],
            'reason': decision['reason'],
            'timestamp': decision['timestamp']
        })
    
    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False)
    print(f"User corrections exported to: {output_path}")
    return output_path

def export_unresolved_items(unresolved_items: List[Dict], output_path: str = "unresolved_metadata.xlsx"):
    """Export items flagged as unresolved for future review or expert consultation."""
    if not unresolved_items:
        print("No unresolved items to export")
        return None
    
    rows = []
    for item in unresolved_items:
        rows.append({
            'field': item['field'],
            'extracted_value': item['extracted'],
            'reference_value': item['reference'],
            'reason': item['reason'],
            'timestamp': item['timestamp'],
            'status': 'needs_expert_review'
        })
    
    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False)
    print(f"Unresolved items exported to: {output_path}")
    return output_path

def log_user_decisions(decisions: List[Dict], output_path: str = "user_decision_log.json"):
    """Log all user choices with timestamps for audit trail."""
    if not decisions:
        return None
    
    log_entry = {
        'session_timestamp': datetime.datetime.now().isoformat(),
        'total_decisions': len(decisions),
        'decisions': decisions
    }
    
    # Load existing log if it exists
    existing_log = []
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r') as f:
                existing_log = json.load(f)
        except:
            existing_log = []
    
    # Add new entry
    if isinstance(existing_log, list):
        existing_log.append(log_entry)
    else:
        existing_log = [log_entry]
    
    # Save updated log
    with open(output_path, 'w') as f:
        json.dump(existing_log, f, indent=2)
    
    print(f"User decisions logged to: {output_path}")
    return output_path

def display_results_with_validation(metadata, comparison_results):
    """Display extraction results with validation info."""
    print("\n" + "="*60)
    print("EXTRACTION RESULTS WITH VALIDATION")
    print("="*60)
    
    # Overall scores
    print(f"Overall Confidence: {metadata.overall_confidence:.2f} ({get_confidence_level(metadata.overall_confidence or 0.0).value})")
    print(f"Metadata Completeness: {metadata.metadata_completeness:.1%}")
    
    # Ground truth comparison
    if comparison_results["status"] == "compared":
        print(f"Ground Truth Accuracy: {comparison_results['overall_accuracy']:.1%}")
    
    print("-" * 60)
    
    # Display each field
    def display_field(name: str, field):
        if field.value is not None:
            confidence_level = get_confidence_level(field.confidence)
            # Display the actual enum value, not the enum representation
            display_value = field.value.value if hasattr(field.value, 'value') else field.value
            print(f"{name}: {display_value}")
            print(f"  ├─ Confidence: {field.confidence:.2f} ({confidence_level.value})")
            if field.evidence:
                print(f"  ├─ Evidence: {field.evidence}")
            if field.source_page:
                print(f"  ├─ Source: Page {field.source_page}")
            if field.alternatives:
                print(f"  └─ Alternatives: {', '.join(field.alternatives)}")
        else:
            print(f"{name}: Not found")
        print()
    
    display_field("Title", metadata.title)
    display_field("Document Type", metadata.doc_type)
    display_field("Health Topic", metadata.health_topic)
    display_field("Creator", metadata.creator)
    display_field("Year", metadata.year)
    display_field("Country", metadata.country)
    display_field("Language", metadata.language)
    display_field("Governance Level", metadata.level)
    
    # Validation report
    print("-" * 60)
    print("GROUND TRUTH VALIDATION")
    print("-" * 60)
    print(generate_accuracy_report(comparison_results))
    
    # Recommendations
    print("\n" + "-" * 60)
    print("RECOMMENDATIONS")
    print("-" * 60)
    recommendations = recommend_action(metadata)
    if recommendations['requires_review']:
        print("⚠️  Manual Review Recommended:")
        for rec in recommendations['recommendations']:
            print(f"  • {rec['field']}: {rec['reason']}")
            if 'alternatives' in rec:
                print(f"    Alternatives: {', '.join(rec['alternatives'])}")
    else:
        print("✅ All fields extracted with acceptable confidence")

def process_pdf_with_validation(pdf_path: str, ground_truth: dict, api_key: str, 
                               interactive_mode: str = "none", enable_search: bool = False, 
                               search_threshold: float = 0.8):
    """Process a single PDF with validation and optional interactive resolution."""
    print(f"\nProcessing: {Path(pdf_path).name}")
    print("="*50)
    
    # Initialize client
    g_client = genai.Client(api_key=api_key)
    
    # Extract metadata using existing function
    first_pages, last_pages = prepare_and_upload_pdf_subset(g_client, pdf_path)
    if not first_pages:
        print("Failed to prepare PDF subsets")
        return None
    
    metadata = get_metadata_from_gemini(g_client, first_pages, last_pages)
    if not metadata:
        print("Failed to extract metadata")
        return None
    
    # Compare with ground truth
    comparison_results = compare_with_ground_truth(metadata, ground_truth, pdf_path)
    
    # Initialize tracking variables
    user_decisions = []
    unresolved_items = []
    search_resolution_results = None
    
    if comparison_results["status"] == "compared":
        print(f"✅ Ground truth match found: {comparison_results.get('filename_key')}")
        
        # Search grounding resolution (if enabled and there are discrepancies)
        discrepancies = comparison_results.get("discrepancies", {})
        if enable_search and discrepancies:
            search_resolution_results = resolve_deviations_with_search(
                discrepancies, pdf_path, metadata, g_client, search_threshold
            )
            
            if search_resolution_results["resolved"]:
                # Apply search resolutions to metadata
                metadata = apply_search_resolution(metadata, search_resolution_results["resolved"])
                
                # Show search resolution report
                print(f"\n{generate_search_resolution_report(search_resolution_results)}")
                
                # Update discrepancies to only remaining conflicts
                discrepancies = search_resolution_results["remaining"]
                
                # Update comparison results with remaining discrepancies
                comparison_results["discrepancies"] = discrepancies
        
        # Interactive resolution if requested
        if interactive_mode != "none":
            show_pre_resolution_summary(comparison_results)
            if discrepancies and interactive_mode == "interactive":
                # Ask for batch handling preference
                auto_mode = batch_choice_prompt(discrepancies)
                metadata, user_decisions, unresolved_items = interactive_resolve_discrepancies(
                    metadata, comparison_results, auto_mode)
            elif interactive_mode in ["auto_reference", "auto_extracted"]:
                auto_mode = "keep_reference" if interactive_mode == "auto_reference" else "keep_extracted"
                metadata, user_decisions, unresolved_items = interactive_resolve_discrepancies(
                    metadata, comparison_results, auto_mode)
        
        # Adjust confidence based on ground truth (if not interactive)
        if interactive_mode == "none":
            metadata = adjust_confidence_with_ground_truth(metadata, comparison_results)
    else:
        print("⚠️  No ground truth match found")
    
    # Track deviations
    deviation_entry = track_all_deviations(comparison_results, pdf_path, metadata)
    
    return {
        'metadata': metadata,
        'comparison_results': comparison_results,
        'deviation_entry': deviation_entry,
        'user_decisions': user_decisions,
        'unresolved_items': unresolved_items,
        'search_resolution_results': search_resolution_results
    }

def main():
    parser = argparse.ArgumentParser(description='PDF metadata extraction with ground truth validation and interactive resolution')
    parser.add_argument('pdf_path', help='Path to PDF file to process')
    parser.add_argument('--excel', default='/home/justus/Nextcloud/GHPL/documents-info.xlsx', 
                       help='Path to Excel file with ground truth data')
    parser.add_argument('--api-key', 
                       default=os.environ.get('GEMINI_API_KEY', ''),
                       help='Gemini API key (defaults to GEMINI_API_KEY env var)')
    parser.add_argument('--export-deviations', help='Export deviations to Excel file')
    parser.add_argument('--stats-only', action='store_true', help='Only show ground truth statistics')
    
    # Interactive resolution options
    parser.add_argument('--interactive', action='store_true', help='Enable interactive resolution of discrepancies')
    parser.add_argument('--auto-reference', action='store_true', help='Automatically use reference values for all discrepancies')
    parser.add_argument('--auto-extracted', action='store_true', help='Automatically use extracted values for all discrepancies')
    
    # Search grounding options
    parser.add_argument('--auto-resolve', action='store_true', help='Enable automatic search resolution of conflicts')
    parser.add_argument('--with-search', action='store_true', help='Use search grounding with interactive mode')
    parser.add_argument('--search-threshold', type=float, default=0.8, help='Minimum confidence for auto-resolution (default: 0.8)')
    
    # Export options for interactive results
    parser.add_argument('--export-corrections', help='Export user corrections to Excel file')
    parser.add_argument('--export-unresolved', help='Export unresolved items to Excel file')
    parser.add_argument('--log-decisions', help='Log all user decisions to JSON file')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.pdf_path):
        print(f"Error: PDF file not found: {args.pdf_path}")
        return 1
    
    if not os.path.exists(args.excel):
        print(f"Error: Excel file not found: {args.excel}")
        return 1
    
    if not args.api_key:
        print("Error: API key required")
        return 1
    
    # Determine interactive mode
    interactive_mode = "none"
    if args.interactive:
        interactive_mode = "interactive"
    elif args.auto_reference:
        interactive_mode = "auto_reference"
    elif args.auto_extracted:
        interactive_mode = "auto_extracted"
    
    # Determine search enablement
    enable_search = args.auto_resolve or args.with_search
    
    # Validate conflicting options
    interactive_options = sum([args.interactive, args.auto_reference, args.auto_extracted])
    if interactive_options > 1:
        print("Error: Only one interactive mode can be selected at a time")
        return 1
    
    # Validate search threshold
    if not (0.0 <= args.search_threshold <= 1.0):
        print("Error: Search threshold must be between 0.0 and 1.0")
        return 1
    
    try:
        # Load ground truth
        print("Loading ground truth data...")
        ground_truth = load_ground_truth_metadata(args.excel)
        print_ground_truth_stats(ground_truth)
        
        if args.stats_only:
            return 0
        
        # Process PDF with interactive mode and search options
        results = process_pdf_with_validation(args.pdf_path, ground_truth, args.api_key, interactive_mode, enable_search, args.search_threshold)
        
        if results:
            # Display results
            display_results_with_validation(results['metadata'], results['comparison_results'])
            
            # Export deviations if requested
            if args.export_deviations and results['deviation_entry'].get('status') != 'no_tracking':
                deviation_log = [results['deviation_entry']]
                export_path = export_deviations_to_excel(deviation_log, args.export_deviations)
                if export_path:
                    print(f"\n📊 Deviations exported to: {export_path}")
            
            # Export interactive results if requested
            if args.export_corrections and results['user_decisions']:
                export_corrected_metadata(results['user_decisions'], args.export_corrections)
            
            if args.export_unresolved and results['unresolved_items']:
                export_unresolved_items(results['unresolved_items'], args.export_unresolved)
            
            if args.log_decisions and results['user_decisions']:
                log_user_decisions(results['user_decisions'], args.log_decisions)
            
            # Summary of interactive session and search results
            if (interactive_mode != "none" and (results['user_decisions'] or results['unresolved_items'])) or results['search_resolution_results']:
                print(f"\n📋 SESSION SUMMARY")
                print(f"{'='*40}")
                
                # Search resolution summary
                if results['search_resolution_results']:
                    search_results = results['search_resolution_results']
                    print(f"Search resolution rate: {search_results['resolution_rate']:.1%}")
                    print(f"Auto-resolved conflicts: {len(search_results['resolved'])}")
                
                # Interactive session summary
                if interactive_mode != "none":
                    print(f"Total user decisions: {len(results['user_decisions'])}")
                    print(f"Unresolved items: {len(results['unresolved_items'])}")
                
                if results['user_decisions']:
                    choice_counts = {}
                    for decision in results['user_decisions']:
                        choice_type = decision['choice']
                        choice_counts[choice_type] = choice_counts.get(choice_type, 0) + 1
                    
                    print("Choice breakdown:")
                    for choice_type, count in choice_counts.items():
                        print(f"  • {choice_type}: {count}")
        else:
            print("❌ Failed to process PDF")
            return 1
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())