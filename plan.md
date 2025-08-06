# PDF Metadata Extraction Enhancement Plan

## Overview
This plan outlines improvements to make the PDF metadata extraction script more robust, accurate, and versatile. The enhancements focus on multiple validation layers, confidence scoring, and handling edge cases.

## 1. Hybrid Approach: Leverage Built-in PDF Metadata

### Current State
- Script relies entirely on Gemini's interpretation of page content
- Ignores PDF's internal metadata dictionary

### Enhancement
- Extract built-in metadata from PDF's `/Info` dictionary and XMP metadata
- Use this as baseline/hints for the LLM

### Implementation Steps
1. Add `get_internal_metadata()` function using pikepdf
2. Extract Title, Author, Subject, Keywords, Creator, Producer, CreationDate, ModDate
3. Pass internal metadata to Gemini as additional context
4. Ask Gemini to validate, correct, or complete this information

### Benefits
- Highly reliable baseline information
- Reduces hallucination risk
- Provides fallback values

## 2. Confidence Scoring System

### Current State
- Binary extraction (found/not found)
- No indication of reliability

### Enhancement
- Add confidence scores (0.0-1.0) for each field
- Include evidence/justification for each extraction
- Calculate composite confidence score

### Implementation Steps

#### Step 1: Update Pydantic Models

```python
from typing import Optional, Union
from pydantic import BaseModel, Field

class FieldMetadata(BaseModel):
    """Metadata for a single extracted field with confidence scoring"""
    value: Optional[Union[str, int]] = Field(None, description="The extracted value")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: str = Field("", description="Justification or source of the extraction")
    source_page: Optional[int] = Field(None, description="Page number where value was found")
    alternatives: Optional[list[str]] = Field(default_factory=list, description="Alternative values found")

class DocumentMetadata(BaseModel):
    """Enhanced document metadata with confidence scoring"""
    doc_type: FieldMetadata
    health_topic: FieldMetadata
    country: FieldMetadata
    language: FieldMetadata
    creator: FieldMetadata
    year: FieldMetadata
    title: FieldMetadata
    level: FieldMetadata
    
    # Overall metadata quality score
    overall_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata_completeness: Optional[float] = Field(None, ge=0.0, le=1.0)
```

#### Step 2: Enhanced Prompt Engineering

```python
confidence_prompt = """
Analyze the provided PDF pages and extract metadata. For each field, provide:

1. **value**: The extracted information (or null if not found)
2. **confidence**: A score from 0.0 to 1.0 based on:
   - 1.0: Explicitly stated with clear labeling (e.g., "Title: [value]")
   - 0.8-0.9: Clearly visible but not explicitly labeled
   - 0.6-0.7: Inferred from prominent placement or formatting
   - 0.4-0.5: Inferred from context clues
   - 0.2-0.3: Educated guess based on document structure
   - 0.0-0.1: No evidence found
3. **evidence**: Specific text or location that supports your extraction
4. **source_page**: Which page (1, 2, 3, etc.) contained this information
5. **alternatives**: Other possible values you considered

Example for title field:
{
    "title": {
        "value": "National Cancer Control Strategy",
        "confidence": 0.95,
        "evidence": "Large bold text at top of page 1, preceded by national emblem",
        "source_page": 1,
        "alternatives": ["Cancer Control Strategy 2024"]
    }
}

Consider these specific guidelines:
- **Title**: Usually on first page, larger font, may be in header
- **Creator**: Look for logos, letterheads, "Published by", copyright notices
- **Year**: Check cover page, headers/footers, copyright, "Revised [year]"
- **Country**: National emblems, flags, addresses, phone country codes
- **Language**: Analyze the text itself, language declarations
- **Doc Type**: Keywords like "Policy", "Guidelines", "Strategy", "Act"
"""
```

#### Step 3: Confidence Score Calculation Algorithm

```python
def calculate_field_confidence(field: FieldMetadata, internal_metadata: dict = None) -> float:
    """Calculate adjusted confidence score for a field"""
    base_confidence = field.confidence
    
    # Boost factors
    boosts = []
    
    # 1. Internal metadata match boost
    if internal_metadata and field.value:
        for key, internal_value in internal_metadata.items():
            if str(field.value).lower() in str(internal_value).lower():
                boosts.append(0.2)  # 20% boost for internal metadata match
                break
    
    # 2. Source page boost (earlier pages = more reliable)
    if field.source_page:
        if field.source_page <= 3:
            boosts.append(0.1)  # 10% boost for early pages
        elif field.source_page >= 10:
            boosts.append(-0.1)  # 10% penalty for late pages
    
    # 3. Evidence quality boost
    if field.evidence:
        if any(keyword in field.evidence.lower() for keyword in ['title:', 'author:', 'published by:', 'copyright']):
            boosts.append(0.15)  # 15% boost for explicit labels
    
    # 4. No alternatives penalty (might indicate ambiguity)
    if field.alternatives and len(field.alternatives) > 2:
        boosts.append(-0.1)  # 10% penalty for many alternatives
    
    # Apply boosts (capped at 1.0)
    final_confidence = min(1.0, base_confidence + sum(boosts))
    return max(0.0, final_confidence)

def calculate_overall_confidence(metadata: DocumentMetadata) -> float:
    """Calculate overall document metadata confidence"""
    # Weight different fields by importance
    weights = {
        'title': 0.25,
        'creator': 0.20,
        'year': 0.15,
        'doc_type': 0.15,
        'country': 0.10,
        'health_topic': 0.10,
        'language': 0.05
    }
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for field_name, weight in weights.items():
        field = getattr(metadata, field_name)
        if field.value is not None:
            weighted_sum += field.confidence * weight
            total_weight += weight
    
    # Calculate completeness (how many fields were extracted)
    fields_found = sum(1 for f in weights.keys() if getattr(metadata, f).value is not None)
    completeness = fields_found / len(weights)
    
    # Overall confidence is weighted average adjusted by completeness
    if total_weight > 0:
        confidence = (weighted_sum / total_weight) * (0.7 + 0.3 * completeness)
    else:
        confidence = 0.0
    
    return round(confidence, 3)
```

#### Step 4: Confidence Thresholds and Actions

```python
class ConfidenceLevel(Enum):
    HIGH = "high"          # >= 0.8
    MEDIUM = "medium"      # >= 0.6
    LOW = "low"           # >= 0.4
    VERY_LOW = "very_low" # < 0.4

def get_confidence_level(score: float) -> ConfidenceLevel:
    if score >= 0.8:
        return ConfidenceLevel.HIGH
    elif score >= 0.6:
        return ConfidenceLevel.MEDIUM
    elif score >= 0.4:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.VERY_LOW

def recommend_action(metadata: DocumentMetadata) -> dict:
    """Recommend actions based on confidence scores"""
    recommendations = []
    
    for field_name in ['title', 'creator', 'year', 'doc_type']:
        field = getattr(metadata, field_name)
        level = get_confidence_level(field.confidence)
        
        if level == ConfidenceLevel.VERY_LOW:
            recommendations.append({
                'field': field_name,
                'action': 'manual_review',
                'reason': f'Very low confidence ({field.confidence})'
            })
        elif level == ConfidenceLevel.LOW and field.alternatives:
            recommendations.append({
                'field': field_name,
                'action': 'choose_alternative',
                'reason': f'Low confidence with alternatives available',
                'alternatives': field.alternatives
            })
    
    return {
        'overall_confidence': metadata.overall_confidence,
        'requires_review': len(recommendations) > 0,
        'recommendations': recommendations
    }
```

### Scoring Factors Detail

1. **Explicit Labeling (0.9-1.0)**
   - "Title: [text]"
   - "Published by: [organization]"
   - "Date: [year]"
   - Clear metadata sections

2. **Prominent Placement (0.7-0.9)**
   - Large font on cover page
   - Header/footer information
   - Logo with organization name
   - Copyright notices

3. **Contextual Inference (0.5-0.7)**
   - Document structure patterns
   - Repeated organizational mentions
   - Address or contact information
   - Domain-specific terminology

4. **Weak Evidence (0.3-0.5)**
   - Single mention in body text
   - Inferred from content topic
   - Partial information only
   - Ambiguous references

5. **No Evidence (0.0-0.3)**
   - Field not found
   - Pure speculation
   - Contradictory information

### Integration with External Validation

The confidence scores can be further refined by:
- **+0.2 boost**: External search confirms the metadata
- **-0.2 penalty**: External search contradicts the metadata
- **+0.1 boost**: Multiple external sources agree
- **Flag for review**: Significant discrepancies found

## 3. Ground Truth Validation via Excel Reference

### Current State
- No external validation
- Relies solely on document content
- No systematic accuracy measurement

### Enhancement
- Load known metadata from documents-info.xlsx as reference data (acknowledged to be error-prone)
- Compare Gemini extraction results with reference data
- **Track and log all deviations** for quality assessment and Excel data improvement
- Calculate accuracy metrics while considering reference data quality
- Generate deviation reports to identify patterns and improve both extraction and reference data

### Implementation Steps

#### Step 1: Excel Data Ingestion
```python
import pandas as pd
from pathlib import Path

def load_ground_truth_metadata(excel_path: str) -> dict:
    """Load reference metadata from Excel file."""
    df = pd.read_excel(excel_path)
    
    # Create lookup dictionary keyed by filename or PDF path
    ground_truth = {}
    for _, row in df.iterrows():
        filename = Path(row['filename']).stem if 'filename' in row else row['pdf_path']
        ground_truth[filename] = {
            'title': row.get('title'),
            'creator': row.get('creator'),
            'year': row.get('year'),
            'doc_type': row.get('doc_type'),
            'health_topic': row.get('health_topic'),
            'country': row.get('country'),
            'language': row.get('language'),
            'level': row.get('level')
        }
    return ground_truth
```

#### Step 2: Ground Truth Comparison
```python
def compare_with_ground_truth(extracted_metadata: DocumentMetadata, 
                             ground_truth: dict, 
                             pdf_filename: str) -> dict:
    """Compare extracted metadata with ground truth and calculate accuracy."""
    
    filename_key = Path(pdf_filename).stem
    if filename_key not in ground_truth:
        return {"status": "no_reference", "accuracy": None}
    
    reference = ground_truth[filename_key]
    results = {
        "status": "compared",
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
            
            # Normalize values for comparison
            ref_norm = str(reference_value).strip().lower()
            ext_norm = str(extracted_value).strip().lower() if extracted_value else ""
            
            if ref_norm == ext_norm:
                results["matches"][field] = {
                    "extracted": extracted_value,
                    "reference": reference_value,
                    "confidence": extracted_field.confidence if hasattr(extracted_field, 'confidence') else 1.0
                }
                correct_fields += 1
            else:
                results["discrepancies"][field] = {
                    "extracted": extracted_value,
                    "reference": reference_value,
                    "confidence": extracted_field.confidence if hasattr(extracted_field, 'confidence') else 0.0
                }
            
            # Calculate field-level accuracy
            results["field_accuracy"][field] = 1.0 if ref_norm == ext_norm else 0.0
    
    # Calculate overall accuracy
    results["overall_accuracy"] = correct_fields / total_fields if total_fields > 0 else 0.0
    
    return results
```

#### Step 3: Confidence Score Adjustment
```python
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
            if hasattr(field, 'alternatives'):
                if ref_value not in field.alternatives:
                    field.alternatives.append(str(ref_value))
    
    # Recalculate overall scores
    metadata.overall_confidence = calculate_overall_confidence(metadata)
    
    return metadata
```

#### Step 4: Accuracy Reporting
```python
def generate_accuracy_report(comparison_results: dict) -> str:
    """Generate human-readable accuracy report."""
    
    if comparison_results["status"] != "compared":
        return "No reference data available for comparison."
    
    report = []
    report.append(f"Overall Accuracy: {comparison_results['overall_accuracy']:.1%}")
    report.append("-" * 40)
    
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
```

#### Step 5: Comprehensive Deviation Tracking
```python
def track_all_deviations(comparison_results: dict, pdf_filename: str, 
                        extracted_metadata: DocumentMetadata) -> dict:
    """Track ALL deviations between extraction and Excel reference data."""
    
    if comparison_results["status"] != "compared":
        return {"status": "no_tracking"}
    
    deviation_entry = {
        "document": pdf_filename,
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

# Simple function to save all deviation data to Excel for manual review
def export_deviations_to_excel(deviation_log: list, output_path: str = "all_deviations.xlsx"):
    """Export all deviations to Excel for manual review and Excel data correction."""
    
    rows = []
    for entry in deviation_log:
        for dev in entry["all_deviations"]:
            rows.append({
                "document": entry["document"],
                "field": dev["field"],
                "extracted_value": dev["extracted_value"],
                "reference_value": dev["reference_value"],
                "extraction_confidence": dev["extraction_confidence"],
                "evidence": dev["evidence"],
                "source_page": dev["source_page"],
                "alternatives": ", ".join(dev["alternatives"]) if dev["alternatives"] else "",
                "timestamp": entry["timestamp"]
            })
    
    if rows:
        df = pd.DataFrame(rows)
        df.to_excel(output_path, index=False)
        print(f"All deviations exported to: {output_path}")
        return output_path
    
    return None
```

### Integration Benefits
- **Complete deviation tracking** - No filtering, capture everything
- **Excel data quality assessment** - Identify all inconsistencies in reference data
- **Extraction validation** - Verify when our extraction might be more accurate
- **Systematic pattern identification** - Find recurring issues across documents
- **Data improvement feedback loop** - Provide actionable insights for Excel data correction

### Validation Logic (Updated)
- **Exact match** → +10% confidence boost, validation flag
- **ANY discrepancy** → Track in deviation log, -30% confidence penalty, add reference as alternative
- **No reference** → No adjustment, but log for future reference data collection
- **Export all deviations** → Generate Excel report for manual review and data correction

## 4. Flexible Schema with Self-Correction

### Current State
- Fixed enums cause validation errors for unexpected values
- No recovery mechanism

### Enhancement
- Add "OTHER" category to enums
- Implement self-correction loop for validation errors

### Implementation Steps
1. Update all enums to include "OTHER" option
2. Add custom fields for "other" values
3. Implement retry logic:
   ```python
   try:
       metadata = parse_response()
   except ValidationError as e:
       corrected_metadata = retry_with_correction(e)
   ```

## 5. Additional Enhancements

### Multi-Language Support
- Detect document language early
- Use appropriate prompts for non-English documents
- Consider translation for metadata standardization

### Batch Processing
- Process multiple PDFs efficiently
- Implement progress tracking
- Add result caching

### Error Recovery
- Comprehensive error handling for each stage
- Fallback strategies for each failure mode
- Detailed logging for debugging

### Performance Optimization
- Implement page sampling strategies
- Cache Gemini file uploads
- Parallel processing where applicable

## 6. Interactive Metadata Resolution System ✅ NEXT PHASE

### Current State
- Ground truth validation identifies discrepancies automatically
- No user intervention when extracted metadata differs from reference data
- Confidence scores are adjusted automatically but users have no control

### Enhancement
- Add interactive CLI prompts when discrepancies are found
- Allow users to choose between extracted, reference, or custom values
- Store user corrections in separate files to preserve original data
- Build corrected dataset for future reference improvement

### Implementation Steps

#### Step 1: Interactive CLI Integration
```bash
# New CLI options for interactive mode
python cli.py docs/sample.pdf --interactive           # Prompt for each discrepancy
python cli.py docs/sample.pdf --interactive --batch   # Batch handling option
python cli.py docs/sample.pdf --auto-reference       # Auto-choose reference values
python cli.py docs/sample.pdf --auto-extracted       # Auto-choose extracted (default)
```

#### Step 2: Interactive Workflow
1. **Pre-resolution Summary**: Show overview of matches vs discrepancies
2. **Batch Choice Option**: For multiple discrepancies, offer:
   - Handle each field individually
   - Keep ALL extracted values
   - Use ALL reference values
3. **Individual Prompts**: For each discrepancy, show:
   ```
   DISCREPANCY FOUND IN FIELD: TITLE
   📊 Extracted Value: 'Updated Management of Hypertension...'
      ├─ Confidence: 0.90
      └─ Evidence: Large bold text at top of page 1
   
   📚 Reference Value: 'Hypertension Guideline December 2006'
      └─ From ground truth data
   
   Choose: 
     [1] Use extracted value
     [2] Use reference value  
     [3] Enter custom value
     [4] Flag as unresolved/needs review
     [s] Skip this field (keep extracted)
   ```
4. **Post-resolution**: Update metadata and recalculate confidence scores

#### Step 3: Storage Strategy
- **In-Memory Updates**: User choices immediately update DocumentMetadata object
- **Corrected Dataset**: Export user corrections to `user_corrected_metadata.xlsx`
- **Audit Trail**: Log all user decisions with timestamps and reasoning
- **Original Preservation**: Keep original ground truth data intact

#### Step 4: Confidence Adjustment for User Choices
```python
def adjust_confidence_for_user_choice(field: FieldMetadata, choice_type: str, reason: str):
    """Adjust confidence based on user interaction."""
    if "reference value" in reason:
        field.confidence = min(1.0, field.confidence + 0.2)  # Boost for reference choice
    elif "custom value" in reason:
        field.confidence = 0.9  # High confidence for manual entry
    elif "extracted value" in reason:
        # Keep original confidence for extracted value choices
        pass
    elif "unresolved" in reason or "needs review" in reason:
        field.confidence = 0.1  # Very low confidence for unresolved conflicts
        field.value = None  # Clear conflicted value
    
    field.evidence += f" [Interactive choice: {reason}]"
```

#### Step 5: Export Functions
```python
def export_corrected_metadata(corrected_entries: list, output_path: str = "user_corrected_metadata.xlsx"):
    """Export user-corrected metadata to separate Excel file."""
    
def log_user_decisions(decisions: list, output_path: str = "user_decision_log.json"):
    """Log all user choices with timestamps for audit trail."""

def export_unresolved_items(unresolved_entries: list, output_path: str = "unresolved_metadata.xlsx"):
    """Export items flagged as unresolved for future review or expert consultation."""
```

### Integration Benefits
- **User Control**: Users decide when AI extraction or ground truth is more accurate
- **Data Quality**: Builds high-quality corrected dataset through human verification
- **Flexibility**: Supports both individual and batch processing workflows
- **Safety**: Preserves original data while building improved reference dataset
- **Efficiency**: Batch options reduce decision fatigue for multiple discrepancies
- **Conflict Resolution**: Allows flagging of genuinely ambiguous cases for expert review
- **Quality Assurance**: Unresolved items can be routed to domain experts or additional validation

### Usage Scenarios
1. **Research Phase**: Use `--interactive` to carefully review and correct individual documents
2. **Batch Processing**: Use `--auto-extracted` or `--auto-reference` based on data quality assessment
3. **Quality Improvement**: Use corrected metadata to improve ground truth dataset
4. **Audit Requirements**: Full decision trail for regulatory or research compliance

## 7. Automatic Deviation Resolution with Search Grounding ⭐ NEXT ENHANCEMENT

### Current State
- Ground truth validation identifies discrepancies between extracted and reference data
- User must manually resolve conflicts in interactive mode
- No automatic fact-checking or additional evidence gathering
- Conflicts remain unresolved until user intervention

### Enhancement: Three-Tier Validation System
Add an automatic resolution layer using Gemini's search grounding capabilities to resolve discrepancies before requiring user intervention.

**Validation Pipeline:**
1. **Tier 1**: AI extraction from PDF content
2. **Tier 2**: Ground truth comparison with Excel reference data
3. **Tier 3**: Web search grounding to automatically resolve conflicts

### Implementation Strategy

#### Step 1: Single Search for All Conflicts (Rate Limit Optimized)
```python
def resolve_deviations_with_search(discrepancies: dict, pdf_filename: str, 
                                  extracted_metadata: DocumentMetadata) -> dict:
    """Use ONE search to resolve ALL metadata conflicts for this document."""
    
    if not discrepancies:
        return {"resolved": {}, "remaining": {}, "resolution_rate": 1.0}
    
    # Execute single search for all conflicts (Gemini auto-generates queries)
    search_results = query_gemini_with_search(discrepancies, extracted_metadata, pdf_filename)
    
    # Process results for each field
    resolved_conflicts = {}
    remaining_conflicts = {}
    
    for field_name, conflict_data in discrepancies.items():
        field_resolution = search_results.get("resolutions", {}).get(field_name)
        
        if field_resolution and field_resolution.get("confidence", 0) >= 0.8:
            resolved_conflicts[field_name] = field_resolution
            resolved_conflicts[field_name]["search_evidence"] = search_results.get("search_evidence", "")
            resolved_conflicts[field_name]["sources"] = search_results.get("sources", [])
        else:
            remaining_conflicts[field_name] = conflict_data
            if field_resolution:
                remaining_conflicts[field_name]["search_notes"] = field_resolution.get("reasoning", "Inconclusive")
    
    return {
        "resolved": resolved_conflicts,
        "remaining": remaining_conflicts,
        "resolution_rate": len(resolved_conflicts) / len(discrepancies) if discrepancies else 0,
        "search_used": True
    }
```

#### Step 2: Let Gemini Generate Search Queries (Per Google Docs)
Note: Google Search grounding automatically generates optimized search queries based on the context provided. No manual query construction needed.

#### Step 3: Single Search Analysis for All Conflicts
```python
def query_gemini_with_search(discrepancies: dict, extracted_metadata: DocumentMetadata, pdf_filename: str) -> dict:
    """Use ONE search to resolve ALL metadata conflicts for this document."""
    
    # Build conflict summary
    conflict_summary = []
    for field_name, conflict_data in discrepancies.items():
        conflict_summary.append(f"• {field_name}: Extracted='{conflict_data['extracted']}' vs Reference='{conflict_data['reference']}'")
    
    # Extract document context for search
    title = extracted_metadata.title.value or Path(pdf_filename).stem.replace("_", " ")
    country = extracted_metadata.country.value or "unknown country"
    
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
    
    Based on your search results, provide resolutions for each field:
    
    {{
        "resolutions": {{
            "title": {{"resolved_value": "...", "confidence": 0.85, "recommendation": "extracted|reference|alternative|needs_review"}},
            "year": {{"resolved_value": "...", "confidence": 0.90, "recommendation": "reference"}},
            "creator": {{"resolved_value": "...", "confidence": 0.75, "recommendation": "needs_review"}}
        }},
        "search_evidence": "key evidence from search results supporting resolutions",
        "sources": ["relevant URLs or source descriptions"],
        "overall_confidence": 0.82
    }}
    
    **Critical**: Only provide high confidence (>0.8) if search results clearly support one value over another.
    **Rate Limit**: This is our ONE search for this document - be comprehensive.
    """
    
    try:
        from google.genai import types
        
        # Configure Google Search grounding tool (correct syntax per docs)
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[analysis_prompt],
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                tools=[grounding_tool]  # Enable search grounding
            )
        )
        
        return json.loads(response.text)
        
    except Exception as e:
        return {
            "resolutions": {},
            "search_evidence": f"Search analysis failed: {e}",
            "sources": [],
            "overall_confidence": 0.0
        }
```

#### Step 4: Confidence Score Updates Based on Search Resolution
```python
def apply_search_resolution(metadata: DocumentMetadata, resolved_conflicts: dict) -> DocumentMetadata:
    """Update metadata based on search-grounded conflict resolution."""
    
    for field_name, resolution in resolved_conflicts.items():
        field = getattr(metadata, field_name)
        recommendation = resolution["recommendation"]
        
        if recommendation == "extracted":
            # Search supports extracted value
            field.confidence = min(1.0, field.confidence + 0.3)  # Major boost
            field.evidence += f" [Search validated: {resolution['reasoning']}]"
            
        elif recommendation == "reference":
            # Search supports reference value - update field
            field.value = resolution["resolved_value"]
            field.confidence = 0.9  # High confidence from search validation
            field.evidence = f"Search-corrected from reference data: {resolution['reasoning']}"
            
        elif recommendation == "alternative":
            # Search found different value
            field.value = resolution["resolved_value"]
            field.confidence = 0.85  # High confidence for search-found alternative
            field.evidence = f"Search-discovered value: {resolution['reasoning']}"
            field.alternatives.extend([field.value, resolution.get("reference_value", "")])
            
        # Add search sources as evidence
        if resolution.get("sources"):
            field.evidence += f" [Sources: {', '.join(resolution['sources'][:2])}]"
    
    return metadata
```

#### Step 5: Enhanced CLI Integration
```python
# New CLI options for search-grounded resolution
python cli.py docs/sample.pdf --auto-resolve        # Enable automatic search resolution
python cli.py docs/sample.pdf --search-threshold 0.8  # Minimum confidence for auto-resolution
python cli.py docs/sample.pdf --interactive --with-search  # Interactive mode with search evidence
```

#### Step 6: Search Resolution Reporting
```python
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
            report.append(f"    └─ Reasoning: {resolution['reasoning']}")
            if resolution.get('sources'):
                report.append(f"    └─ Sources: {', '.join(resolution['sources'][:1])}")
    
    if remaining:
        report.append("\n⚠️  STILL NEED REVIEW:")
        for field, conflict in remaining.items():
            report.append(f"  • {field}: '{conflict['extracted']}' vs '{conflict['reference']}'")
            if conflict.get('search_evidence'):
                report.append(f"    └─ Search Notes: {conflict['search_evidence']}")
    
    return "\n".join(report)
```

### Integration Benefits

1. **Automatic Resolution**: Resolve 60-80% of conflicts without user intervention
2. **Enhanced Accuracy**: Cross-validate against authoritative web sources  
3. **Confidence Boosting**: Search validation significantly increases metadata reliability
4. **Reduced User Fatigue**: Only prompt users for genuinely ambiguous cases
5. **Source Attribution**: Provide web sources supporting metadata decisions
6. **Quality Assurance**: Identify when both extracted and reference data are incorrect

### Implementation Workflow

```
PDF Processing Pipeline with Search Grounding:

1. Extract metadata with Gemini (Tier 1)
2. Compare with ground truth data (Tier 2)
3. IF conflicts found:
   ├─ Query Gemini with search grounding for each conflict (Tier 3)
   ├─ Auto-resolve high-confidence conflicts (>0.8)
   └─ Flag remaining conflicts for user review
4. Generate comprehensive resolution report
5. Update metadata with search-validated values
6. Continue with user interaction (if needed)
```

### Advanced Search Strategies

#### Field-Specific Search Approaches
- **Title**: Search for exact document titles, official publication records
- **Creator**: Verify organization names, official attributions, institutional websites
- **Year**: Cross-reference publication dates, version histories, official announcements
- **Doc Type**: Validate document classification against official categorizations
- **Country**: Confirm jurisdiction, national vs regional scope
- **Health Topic**: Verify subject matter classification, medical taxonomy

#### Search Result Quality Assessment
```python
def assess_search_quality(sources: list, field_name: str) -> float:
    """Assess the quality of search sources for metadata validation."""
    
    quality_indicators = {
        "government_domains": 0.4,      # .gov, official ministry sites
        "institutional_sources": 0.3,   # WHO, academic institutions  
        "document_databases": 0.2,      # Policy libraries, catalogs
        "multiple_confirmations": 0.3   # Same info from multiple sources
    }
    
    # Calculate composite quality score
    # Implementation would analyze source URLs and content
    return min(1.0, sum(applicable_quality_scores))
```

### Success Metrics for Search Grounding

- **Resolution Rate**: >70% of conflicts automatically resolved
- **Resolution Accuracy**: >95% of search-resolved conflicts validated as correct
- **Source Quality**: Average source quality score >0.7
- **Performance**: <10 seconds additional processing per conflict
- **User Satisfaction**: <30% of auto-resolved conflicts overridden by users

### Important Implementation Notes (Per Google Docs)

#### Correct API Syntax
- Use `google.genai.types.Tool(google_search=types.GoogleSearch())` 
- Configure with `types.GenerateContentConfig(tools=[grounding_tool])`
- Compatible models: Gemini 2.5 Pro, 2.5 Flash, 1.5 Pro

#### Response Structure
```python
# Response includes grounding metadata
response.candidates[0].grounding_metadata.search_entry_point
response.candidates[0].grounding_metadata.grounding_chunks  # Search results
response.candidates[0].grounding_chunks  # Citation information
```

#### Rate Limiting Strategy
- 1,500 searches/day = maximum 1,500 documents with conflicts
- Only use search when discrepancies exist (not for every document)  
- Single comprehensive search per document covers all conflicts
- Fall back to user interaction if search fails or is inconclusive

#### Search Quality Considerations
- Google Search provides "real-time information" and "factual accuracy"
- Results automatically include source citations and URLs
- Search queries are automatically generated by Gemini based on context
- No need to manually craft search queries - Gemini optimizes them

## Implementation Priority

1. **Phase 1 (High Impact, Low Effort)** ✅ COMPLETED
   - Extract internal PDF metadata
   - Add "OTHER" to enums
   - Ground truth validation via Excel

2. **Phase 2 (High Impact, Medium Effort)** ✅ COMPLETED
   - Full confidence scoring system
   - Ground truth validation and deviation tracking
   - Enhanced CLI with validation reports

3. **Phase 3 (High Impact, Medium Effort)** 🔄 IN PROGRESS
   - Interactive metadata resolution system
   - User-corrected dataset building
   - Batch processing options

4. **Phase 4 (Medium Impact, High Effort)**
   - Self-correction mechanism
   - Web search validation (alternative to ground truth)
   - Multi-language support

## Success Metrics

- **Accuracy**: >95% correct metadata extraction
- **Confidence**: Average confidence score >0.8
- **Coverage**: Handle 99% of text-based PDFs
- **Performance**: <30 seconds per document
- **Reliability**: <1% failure rate

## Testing Strategy

1. **Test Dataset**
   - 100 PDFs with known metadata
   - Mix of document types, languages, and formats
   - Include various formatting styles

2. **Validation Methods**
   - Compare against manual extraction
   - Cross-reference with official sources
   - Track confidence score accuracy

3. **Edge Cases**
   - Corrupted PDFs
   - Password-protected documents
   - Multi-language documents
   - Very large files (>100 pages)

## Conclusion

This enhanced approach creates a robust, multi-layered metadata extraction system that combines:
- Internal metadata extraction
- AI-powered content analysis
- External validation
- Confidence scoring
- Error recovery

The result will be a production-ready system capable of handling diverse PDF documents with high accuracy and reliability.