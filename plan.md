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

## 8. Rate Limiting and Throughput Optimization 🚀 CRITICAL IMPLEMENTATION

### Current State Analysis ✅ PARTIALLY IMPLEMENTED
- Rate limiting classes exist in cli.py (lines 41-161)
- `RateLimiter` class: 140 RPM limit, thread-safe tracking
- `SearchQuotaTracker` class: 1500/day search quota with persistence
- **CRITICAL ISSUE**: Global limiters are declared but NEVER initialized 
- **SYNCHRONIZATION PROBLEM**: get_metadata.py calls are not rate limited

### Root Cause Analysis
```python
# In cli.py lines 152-154 - these are NEVER set to actual instances!
GEMINI_RATE_LIMITER = None  # ⚠️ Always None
SEARCH_QUOTA_TRACKER = None # ⚠️ Always None

# In query_gemini_with_search() - tries to use None objects
if GEMINI_RATE_LIMITER:  # This is always False!
    wait_for_rate_limit(GEMINI_RATE_LIMITER, "search grounding")
```

### Implementation Plan

#### Step 1: Fix Global Limiter Initialization
```python
# In cli.py main() function - MUST be first thing after arg parsing
def main():
    # ... arg parsing ...
    
    # CRITICAL: Initialize rate limiters before ANY processing
    global GEMINI_RATE_LIMITER, SEARCH_QUOTA_TRACKER
    GEMINI_RATE_LIMITER = RateLimiter(max_requests_per_minute=140)  # Conservative
    SEARCH_QUOTA_TRACKER = SearchQuotaTracker(max_searches_per_day=1500)
    
    print("🚀 Rate limiting initialized:")
    print(f"   Gemini API: 140 RPM (150 - 10 buffer)")
    quota_status = SEARCH_QUOTA_TRACKER.get_quota_status()
    print(f"   Search quota: {quota_status['remaining']}/{quota_status['max']} remaining today")
```

#### Step 2: Use Dependency Injection (Clean Architecture)
```python
# In get_metadata.py - add rate_limiter parameter to function signature
def get_metadata_from_gemini(client, first_pages, last_pages, rate_limiter=None):
    """
    Extract metadata from PDF pages with optional rate limiting.
    
    Args:
        client: Gemini API client
        first_pages: First pages of PDF
        last_pages: Last pages of PDF  
        rate_limiter: Optional RateLimiter instance for API throttling
    """
    # Apply rate limiting if provided
    if rate_limiter:
        wait_time = rate_limiter.wait_if_needed()
        if wait_time > 0:
            print(f"⏳ Rate limiting: waiting {wait_time:.1f}s for metadata extraction...")
            time.sleep(wait_time)
    
    # Original metadata extraction logic remains unchanged
    if not first_pages:
        print("No uploaded file was provided to the Gemini API.")
        return None

    model_name = 'gemini-2.5-pro'
    # ... rest of existing function unchanged ...
```

```python
# In cli.py - pass rate limiter to the function calls
def process_pdf_with_validation(pdf_path, ground_truth, api_key, rate_limiter, search_quota_tracker, ...):
    """Process PDF with rate-limited API calls."""
    g_client = genai.Client(api_key=api_key)
    
    # Pass rate limiter to metadata extraction
    first_pages, last_pages = prepare_and_upload_pdf_subset(g_client, pdf_path)
    metadata = get_metadata_from_gemini(g_client, first_pages, last_pages, rate_limiter)
    
    # For search grounding - check quota and apply rate limiting
    if discrepancies and enable_search:
        if search_quota_tracker.use_search_quota():
            wait_for_rate_limit(rate_limiter, "search grounding")  
            search_results = query_gemini_with_search(...)
        else:
            print("❌ Search quota exhausted for today")
```

```python
# In batch processing - create limiters once and pass them down
def batch_process_pdfs(excel_path, docs_dir, api_key, workers=4, ...):
    # Initialize rate limiters at batch level
    rate_limiter = RateLimiter(max_requests_per_minute=140)
    search_quota_tracker = SearchQuotaTracker(max_searches_per_day=1500)
    
    print("🚀 Rate limiting initialized:")
    print(f"   Gemini API: 140 RPM")
    quota_status = search_quota_tracker.get_quota_status()
    print(f"   Search quota: {quota_status['remaining']}/{quota_status['max']} remaining")
    
    # Pass limiters to each worker function
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                process_single_pdf_batch, 
                pdf_path, ground_truth, api_key,
                rate_limiter, search_quota_tracker,  # ✅ Pass dependencies
                enable_search, search_threshold, verbose
            )
            for pdf_path in pdf_files
        ]
```

#### Step 3: Throughput Optimization Strategy
```python
def calculate_optimal_workers(current_rpm: int, target_rpm: int = 140) -> int:
    """Calculate optimal worker count based on current throughput."""
    utilization = current_rpm / target_rpm
    
    if utilization < 0.6:  # Under 60% utilization - can increase
        return min(10, max(4, int(target_rpm / 15)))  # More workers
    elif utilization > 0.9:  # Over 90% utilization - reduce load
        return max(2, int(target_rpm / 25))  # Fewer workers
    else:  # 60-90% is optimal range
        return max(4, int(target_rpm / 18))  # Maintain current

# Dynamic worker adjustment in batch processing
def adaptive_batch_processing():
    current_workers = 4
    
    for batch_start in range(0, len(files), 50):
        # Check rate limit utilization every batch
        stats = GEMINI_RATE_LIMITER.get_current_rate()
        optimal = calculate_optimal_workers(stats)
        
        if optimal != current_workers:
            print(f"🔧 Adjusting workers: {current_workers} → {optimal}")
            # Restart ThreadPoolExecutor with new worker count
            current_workers = optimal
```

#### Step 3.5: Adaptive Worker Scaling ⚡ NEW FEATURE
```python
def calculate_optimal_workers(rate_limiter: RateLimiter, base_workers: int, max_workers: int = 20) -> int:
    """Calculate optimal number of workers based on current rate limit utilization."""
    if not rate_limiter:
        return base_workers
    
    current_rate = rate_limiter.get_current_rate()
    max_rate = rate_limiter.max_requests_per_minute
    utilization = current_rate / max_rate
    
    # Conservative scaling strategy:
    # - If utilization < 25%, can scale up to 200% of base workers (aggressive scaling when safe)
    # - If utilization < 50%, can scale up to 150% of base workers (moderate scaling)
    # - If utilization < 75%, maintain base workers (normal operation)
    # - If utilization > 75%, scale down to 75% of base workers (protective scaling)
    # - If utilization > 90%, scale down to 50% of base workers (emergency scaling)
    
    if utilization < 0.25:
        optimal = min(int(base_workers * 2.0), max_workers)
    elif utilization < 0.5:
        optimal = min(int(base_workers * 1.5), max_workers)
    elif utilization < 0.75:
        optimal = base_workers
    elif utilization < 0.9:
        optimal = max(int(base_workers * 0.75), 1)
    else:
        optimal = max(int(base_workers * 0.5), 1)
    
    return optimal

# Integration with batch processing
def batch_process_pdfs_adaptive(...):
    base_workers = workers
    current_workers = workers
    scaling_check_interval = 10  # Check every 10 files
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for batch_start in range(0, len(file_items), batch_size):
            # Check if we should adjust worker count every N files
            if processed_count % scaling_check_interval == 0 and GEMINI_RATE_LIMITER:
                optimal_workers = calculate_optimal_workers(GEMINI_RATE_LIMITER, base_workers)
                current_rate = GEMINI_RATE_LIMITER.get_current_rate()
                utilization = current_rate / GEMINI_RATE_LIMITER.max_requests_per_minute * 100
                
                if optimal_workers != current_workers:
                    print(f"🔄 Rate limit utilization: {utilization:.1f}% - adjusting workers: {current_workers} → {optimal_workers}")
                    current_workers = optimal_workers
                    # Note: ThreadPoolExecutor can't be resized dynamically
                    # This provides monitoring and guidance for future batches
```

**Benefits of Adaptive Scaling:**
- **Fast when safe**: Scales up to 2x workers when utilization < 25%
- **Protective when busy**: Scales down when approaching limits
- **Real-time feedback**: Shows utilization percentages and scaling decisions
- **Conservative approach**: Maintains safety buffers to avoid hitting limits
- **Monitoring integration**: Provides data for optimizing future runs

#### Step 4: Performance Monitoring
```python
class ThroughputMonitor:
    """Monitor API usage and efficiency."""
    
    def __init__(self):
        self.start_time = time.time()
        self.api_calls = 0
        self.search_calls = 0
        self.wait_time = 0.0
    
    def log_api_call(self, wait_time: float, is_search: bool = False):
        self.api_calls += 1
        if is_search:
            self.search_calls += 1
        self.wait_time += wait_time
    
    def get_throughput_report(self) -> str:
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return "No data available"
        
        actual_rpm = (self.api_calls * 60) / elapsed
        efficiency = 1.0 - (self.wait_time / elapsed)
        
        return f"""
📊 THROUGHPUT ANALYSIS
Actual RPM: {actual_rpm:.1f}/140 ({actual_rpm/140:.1%})
API calls: {self.api_calls} ({self.search_calls} searches)
Efficiency: {efficiency:.1%} (time not waiting for rate limits)
Total wait time: {self.wait_time:.1f}s / {elapsed:.1f}s
        """

# Integration with existing batch processing
monitor = ThroughputMonitor()

# In wait_for_rate_limit function
def wait_for_rate_limit(limiter: RateLimiter, operation: str = "API call") -> None:
    wait_time = limiter.wait_if_needed()
    if wait_time > 0:
        print(f"⏳ Rate limiting: waiting {wait_time:.1f}s for {operation}...")
        time.sleep(wait_time)
    
    # Log for monitoring
    monitor.log_api_call(wait_time, "search" in operation)
```

### Critical Implementation Order

1. **Initialize global limiters in main()** - MUST be first
2. **Import limiters in get_metadata.py** - Ensure synchronization  
3. **Test single file processing** - Verify rate limiting works
4. **Test batch processing** - Verify concurrent rate limiting
5. **Add throughput monitoring** - Optimize worker count
6. **Performance tuning** - Approach 140 RPM safely

### Expected Performance Improvements

**Before Fix:**
- No rate limiting = Risk of 429 errors and API blocking
- Uncontrolled concurrent requests
- No search quota tracking
- Suboptimal throughput

**After Fix:**
- Safe 140 RPM operation (93% of 150 RPM limit)
- Synchronized rate limiting across all API calls
- 1500 search quota properly managed
- Adaptive worker scaling
- **Estimated throughput: 8000+ documents/hour**

### Success Metrics

- Zero rate limit violations (429 errors)
- 90%+ RPM utilization (126+ RPM sustained)
- Search quota matches conflict rate (~30% of documents)
- <5% time spent waiting for rate limits
- Linear scalability with document count

### Integration with Existing Code

The rate limiting classes are already implemented - we just need to:
1. **Initialize them** (1 line in main())
2. **Import in get_metadata.py** (3 lines)  
3. **Add monitoring** (optional enhancement)

This is a **high-impact, low-effort** fix that will immediately enable safe high-throughput processing.

## 9. Rolling Workers Architecture: Eliminating Batch Stalls 🚀 CRITICAL PERFORMANCE FIX

### Current Bottlenecks Analysis ❌

The current batch processing system in `cli.py` has several critical stalls:

#### **1. Discrete Batch Processing (Lines 1921-1924)**
```python
# Current: Process in batches of 50
for batch_start in range(0, len(file_items), batch_size):  # batch_size = 50
    batch_end = min(batch_start + batch_size, len(file_items))
    batch_files = file_items[batch_start:batch_end]
```
**Problem**: Next batch cannot start until ALL 50 files in current batch complete.
**Impact**: Fast workers idle while waiting for slowest worker in each batch.

#### **2. as_completed() Batch Blocking (Lines 1953-2007)**
```python
# Current: Wait for ALL futures in batch before continuing
for future in as_completed(future_to_file):
    # Process result, save progress
    # Next batch starts only after this loop completes
```
**Problem**: Artificial synchronization points every 50 files.
**Impact**: 2-10 second stalls between batches while workers are idle.

#### **3. Excessive Progress Saving (Lines 1985-1986)**
```python
# Current: Save after EVERY single file
progress.save_to_file(progress_file)  # Disk I/O blocking
```
**Problem**: Synchronous disk writes after each file completion.
**Impact**: ~50-100ms I/O latency per file = 5+ seconds per batch in I/O overhead.

#### **4. Memory Pre-loading (Line 1909)**
```python
# Current: Load ALL files into memory at start
file_items = list(pending_files.items())  # 2400+ files in memory
```
**Problem**: Large memory footprint, slow startup for large document sets.

### Rolling Workers Architecture ✅

**Core Concept**: Continuous work queue where workers pull tasks as they become available, eliminating artificial batch boundaries and idle time.

#### **Architecture Overview**
```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   File Queue    │ -> │   Workers    │ -> │ Results Queue   │
│  (Producer)     │    │  (Consumers) │    │  (Collector)    │
├─────────────────┤    ├──────────────┤    ├─────────────────┤
│ • PDF files     │    │ • 4-8 workers│    │ • Completed     │
│ • Lazy loading  │    │ • No batching│    │ • Failed items  │
│ • Rate limiting │    │ • Continuous │    │ • Statistics    │
│ • Priority      │    │ • Pull model │    │ • Progress      │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

#### **Key Components**

**1. Producer Thread (File Discovery)**
```python
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

class FileProducer(threading.Thread):
    """Continuously feed PDF files to worker queue."""
    
    def __init__(self, docs_dir: str, excel_data: pd.DataFrame, 
                 work_queue: queue.Queue, progress: BatchProgress):
        super().__init__(name="FileProducer")
        self.docs_dir = docs_dir
        self.excel_data = excel_data
        self.work_queue = work_queue
        self.progress = progress
        self.daemon = True
    
    def run(self):
        """Stream PDF files into work queue (lazy loading)."""
        pdf_count = 0
        
        # Stream files instead of loading all at once
        for pdf_file in self._discover_pdfs_lazily():
            if pdf_file not in self.progress.completed:
                self.work_queue.put(pdf_file)
                pdf_count += 1
        
        # Signal completion to workers
        for _ in range(8):  # Number of workers
            self.work_queue.put(None)  # Poison pill
            
        print(f"📁 Producer: Queued {pdf_count} files for processing")
    
    def _discover_pdfs_lazily(self):
        """Yield PDF files one at a time instead of loading all."""
        for root, dirs, files in os.walk(self.docs_dir):
            for file in files:
                if file.lower().endswith('.pdf'):
                    yield os.path.join(root, file)
```

**2. Worker Pool (Continuous Processing)**
```python
class RollingWorker(threading.Thread):
    """Worker that continuously pulls from work queue."""
    
    def __init__(self, worker_id: int, work_queue: queue.Queue, 
                 results_queue: queue.Queue, ground_truth: dict, api_key: str, 
                 rate_limiter, search_quota_tracker, **options):
        super().__init__(name=f"Worker-{worker_id}")
        self.worker_id = worker_id
        self.work_queue = work_queue
        self.results_queue = results_queue
        self.ground_truth = ground_truth
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.search_quota_tracker = search_quota_tracker
        self.options = options
        self.daemon = True
        self.files_processed = 0
    
    def run(self):
        """Continuously process files from queue until poison pill."""
        while True:
            try:
                # Get next file (blocks until available)
                pdf_path = self.work_queue.get(timeout=30)
                
                if pdf_path is None:  # Poison pill - shutdown
                    print(f"[{self.name}] Shutting down after {self.files_processed} files")
                    break
                
                # Process PDF (same logic as current system)
                result = self._process_single_pdf(pdf_path)
                
                # Send result to collector
                self.results_queue.put({
                    'pdf_path': pdf_path,
                    'result': result,
                    'worker_id': self.worker_id,
                    'success': result is not None
                })
                
                self.files_processed += 1
                self.work_queue.task_done()
                
            except queue.Empty:
                print(f"[{self.name}] No work available, continuing...")
            except Exception as e:
                print(f"[{self.name}] Error processing file: {e}")
                self.results_queue.put({
                    'pdf_path': pdf_path if 'pdf_path' in locals() else 'unknown',
                    'result': None,
                    'worker_id': self.worker_id,
                    'success': False,
                    'error': str(e)
                })
                if 'pdf_path' in locals():
                    self.work_queue.task_done()
    
    def _process_single_pdf(self, pdf_path: str):
        """Process single PDF (reuse existing logic)."""
        return process_single_pdf_batch(
            pdf_path, self.ground_truth, self.api_key,
            None, None,  # Progress tracking handled by collector
            **self.options
        )
```

**3. Results Collector (Async Progress Tracking)**
```python
class ResultsCollector(threading.Thread):
    """Collect results and handle progress tracking asynchronously."""
    
    def __init__(self, results_queue: queue.Queue, progress: BatchProgress,
                 progress_file: str, total_files: int):
        super().__init__(name="ResultsCollector")
        self.results_queue = results_queue
        self.progress = progress
        self.progress_file = progress_file
        self.total_files = total_files
        self.daemon = True
        
        # Optimized progress saving
        self.save_interval = 25  # Save every 25 files instead of every file
        self.last_save_time = time.time()
        self.unsaved_changes = 0
    
    def run(self):
        """Continuously collect results and update progress."""
        start_time = time.time()
        processed_count = len(self.progress.completed)
        
        while processed_count < self.total_files:
            try:
                # Get next result (timeout to allow checking completion)
                result_data = self.results_queue.get(timeout=5)
                
                if result_data is None:  # Shutdown signal
                    break
                
                # Update progress
                filename = Path(result_data['pdf_path']).name
                if result_data['success']:
                    self.progress.completed.append(filename)
                else:
                    self.progress.failed.append({
                        'filename': filename,
                        'timestamp': datetime.datetime.now().isoformat(),
                        'error': result_data.get('error', 'Processing failed'),
                        'worker_id': result_data['worker_id']
                    })
                
                # Remove from pending (safe)
                if filename in self.progress.pending:
                    self.progress.pending.remove(filename)
                
                processed_count += 1
                self.unsaved_changes += 1
                
                # Print progress (no I/O overhead)
                self._print_progress(processed_count, start_time)
                
                # Optimized progress saving (every 25 files OR every 60 seconds)
                self._maybe_save_progress()
                
                self.results_queue.task_done()
                
            except queue.Empty:
                # Timeout - check if we should save progress anyway
                self._maybe_save_progress(force_time_check=True)
                continue
        
        # Final save
        self._save_progress()
        print(f"📊 ResultsCollector: Final save completed")
    
    def _print_progress(self, processed_count: int, start_time: float):
        """Print progress without I/O overhead."""
        if processed_count % 5 == 0:  # Print every 5 files (reduced frequency)
            elapsed = time.time() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            eta = (self.total_files - processed_count) / rate if rate > 0 else 0
            
            print(f"[{processed_count:4d}/{self.total_files}] "
                  f"Rate: {rate:.1f}/sec | ETA: {eta/60:.1f}min | "
                  f"Success: {len(self.progress.completed)}")
    
    def _maybe_save_progress(self, force_time_check: bool = False):
        """Save progress only when needed (every 25 files or 60 seconds)."""
        now = time.time()
        time_since_save = now - self.last_save_time
        
        should_save = (
            self.unsaved_changes >= self.save_interval or  # Every 25 files
            (force_time_check and time_since_save >= 60) or  # Every 60 seconds
            self.unsaved_changes > 0 and time_since_save >= 300  # Every 5 minutes if any changes
        )
        
        if should_save:
            self._save_progress()
    
    def _save_progress(self):
        """Save progress to file (atomic operation)."""
        self.progress.last_checkpoint = datetime.datetime.now().isoformat()
        self.progress.save_to_file(self.progress_file)
        self.last_save_time = time.time()
        self.unsaved_changes = 0
```

**4. Dynamic Worker Scaling Manager**
```python
class DynamicWorkerManager:
    """Manages worker scaling based on rate limit utilization."""
    
    def __init__(self, rate_limiter, min_workers: int = 4, max_workers: int = 50):
        self.rate_limiter = rate_limiter
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.current_workers = min_workers
        self.active_workers = []
        self.scaling_lock = threading.Lock()
        self.last_scale_time = time.time()
        self.scale_cooldown = 30  # Don't scale more than once per 30 seconds
    
    def should_scale_up(self) -> bool:
        """Check if we should add more workers."""
        if len(self.active_workers) >= self.max_workers:
            return False
        
        if time.time() - self.last_scale_time < self.scale_cooldown:
            return False
        
        current_rate = self.rate_limiter.get_current_rate()
        target_rate = self.rate_limiter.max_requests_per_minute
        utilization = current_rate / target_rate
        
        # Scale up if utilization < 70% (more aggressive scaling)
        return utilization < 0.7
    
    def should_scale_down(self) -> bool:
        """Check if we should remove workers."""
        if len(self.active_workers) <= self.min_workers:
            return False
        
        if time.time() - self.last_scale_time < self.scale_cooldown:
            return False
        
        current_rate = self.rate_limiter.get_current_rate()
        target_rate = self.rate_limiter.max_requests_per_minute
        utilization = current_rate / target_rate
        
        # Scale down if utilization > 90% (only when really needed)
        return utilization > 0.90
    
    def add_worker(self, work_queue: queue.Queue, results_queue: queue.Queue, 
                   ground_truth: dict, api_key: str, search_quota_tracker, **options) -> bool:
        """Add a new worker if needed."""
        with self.scaling_lock:
            if not self.should_scale_up():
                return False
            
            worker_id = len(self.active_workers)
            worker = RollingWorker(
                worker_id=worker_id,
                work_queue=work_queue,
                results_queue=results_queue,
                ground_truth=ground_truth,
                api_key=api_key,
                rate_limiter=self.rate_limiter,
                search_quota_tracker=search_quota_tracker,
                **options
            )
            worker.start()
            self.active_workers.append(worker)
            self.last_scale_time = time.time()
            
            current_rate = self.rate_limiter.get_current_rate()
            utilization = current_rate / self.rate_limiter.max_requests_per_minute
            print(f"🔼 SCALED UP: Added Worker-{worker_id} | "
                  f"Total workers: {len(self.active_workers)} | "
                  f"Rate utilization: {utilization:.1%}")
            return True
    
    def remove_worker(self) -> bool:
        """Remove a worker if needed."""
        with self.scaling_lock:
            if not self.should_scale_down():
                return False
            
            if not self.active_workers:
                return False
            
            # Send poison pill to one worker to shut it down gracefully
            # Worker will remove itself from active_workers list when it shuts down
            # This is a graceful shutdown approach
            worker_to_remove = self.active_workers[-1]  # Remove newest worker
            # Note: Actual implementation would need coordination with work_queue
            # to send targeted shutdown signal
            
            self.last_scale_time = time.time()
            current_rate = self.rate_limiter.get_current_rate()
            utilization = current_rate / self.rate_limiter.max_requests_per_minute
            print(f"🔽 SCALED DOWN: Removing worker | "
                  f"Total workers: {len(self.active_workers)-1} | "
                  f"Rate utilization: {utilization:.1%}")
            return True
    
    def monitor_and_scale(self, work_queue: queue.Queue, results_queue: queue.Queue,
                         ground_truth: dict, api_key: str, search_quota_tracker, **options):
        """Periodically check if scaling is needed."""
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            # Try to scale up first (more aggressive when safe)
            if self.add_worker(work_queue, results_queue, ground_truth, 
                             api_key, search_quota_tracker, **options):
                continue
            
            # If can't scale up, check if should scale down
            self.remove_worker()
```

**5. Enhanced Rolling Processing Function with Auto-Scaling**
```python
def rolling_batch_process_pdfs(excel_path: str, docs_dir: str, api_key: str,
                              workers: int = 8, max_workers: int = 50,
                              enable_search: bool = False, search_threshold: float = 0.8, 
                              resume: bool = False, progress_file: str = "batch_progress.json",
                              verbose: bool = False, limit: Optional[int] = None,
                              auto_scale: bool = True) -> BatchResults:
    """Process PDFs using rolling workers with dynamic scaling."""
    
    print(f"🚀 Starting ROLLING processing with {workers}-{max_workers} workers (auto-scaling: {auto_scale})")
    print(f"🎯 Target: 70-90% rate utilization (up to {max_workers} workers for maximum throughput)")
    print(f"📊 Excel file: {excel_path}")
    print(f"📁 Docs directory: {docs_dir}")
    
    # Load ground truth data
    print("Loading ground truth data...")
    ground_truth = load_ground_truth_metadata(excel_path)
    excel_data = pd.read_excel(excel_path)
    print_ground_truth_stats(ground_truth)
    
    # Initialize or load progress
    progress = BatchProgress.load_from_file(progress_file) if resume else None
    if not progress:
        # We'll count files lazily, set initial estimate
        progress = BatchProgress(
            total_files=0,  # Will be updated as we discover files
            completed=[],
            failed=[],
            pending=[],
            start_time=datetime.datetime.now().isoformat(),
            last_checkpoint=datetime.datetime.now().isoformat()
        )
    
    # Initialize rate limiting
    rate_limiter = RateLimiter(max_requests_per_minute=140)
    search_quota_tracker = SearchQuotaTracker(max_searches_per_day=1500)
    
    print("🚀 Rate limiting initialized:")
    print(f"   Gemini API: 140 RPM (target utilization: 70-90% = 98-126 RPM)")
    quota_status = search_quota_tracker.get_quota_status()
    print(f"   Search quota: {quota_status['remaining']}/{quota_status['max']} remaining")
    
    # Initialize dynamic scaling manager
    scaling_manager = None
    if auto_scale:
        scaling_manager = DynamicWorkerManager(
            rate_limiter=rate_limiter,
            min_workers=workers,
            max_workers=max_workers
        )
        print(f"🎛️  Auto-scaling enabled: {workers}-{max_workers} workers (target: 70-90% utilization)")
    
    # Create queues
    work_queue = queue.Queue(maxsize=100)  # Larger queue for auto-scaling
    results_queue = queue.Queue()
    
    # Count total files for progress tracking
    print("📁 Counting PDF files...")
    total_files = sum(1 for f in discover_pdfs_lazily(docs_dir, excel_data) 
                     if Path(f).name not in progress.completed)
    progress.total_files = min(total_files, limit) if limit else total_files
    print(f"Found {progress.total_files} files to process")
    
    if progress.total_files == 0:
        print("✅ All files already processed!")
        return BatchResults()
    
    # Start producer thread
    producer = FileProducer(docs_dir, excel_data, work_queue, progress)
    producer.start()
    
    # Start results collector
    collector = ResultsCollector(results_queue, progress, progress_file, progress.total_files)
    collector.start()
    
    # Start initial worker threads
    initial_workers = []
    for i in range(workers):
        worker = RollingWorker(
            worker_id=i,
            work_queue=work_queue,
            results_queue=results_queue,
            ground_truth=ground_truth,
            api_key=api_key,
            rate_limiter=rate_limiter,
            search_quota_tracker=search_quota_tracker,
            enable_search=enable_search,
            search_threshold=search_threshold,
            verbose=verbose
        )
        worker.start()
        initial_workers.append(worker)
    
    # Register initial workers with scaling manager
    if scaling_manager:
        scaling_manager.active_workers = initial_workers
        # Start scaling monitor thread
        scaling_thread = threading.Thread(
            target=scaling_manager.monitor_and_scale,
            args=(work_queue, results_queue, ground_truth, api_key, search_quota_tracker),
            kwargs={
                'enable_search': enable_search,
                'search_threshold': search_threshold,
                'verbose': verbose
            },
            name="ScalingMonitor",
            daemon=True
        )
        scaling_thread.start()
        print("📈 Dynamic scaling monitor started")
    
    # Wait for completion
    print(f"🏃‍♂️ {workers} workers started - processing continuously...")
    if auto_scale:
        print("📊 Monitoring rate utilization for auto-scaling...")
    
    try:
        # Wait for producer to finish
        producer.join()
        print("📁 Producer finished - all files queued")
        
        # Wait for all work to be processed
        work_queue.join()
        print("✅ All work completed")
        
        # Wait for all workers to shutdown (including dynamically added ones)
        all_workers = scaling_manager.active_workers if scaling_manager else initial_workers
        for worker in all_workers:
            worker.join(timeout=30)
        
        if scaling_manager:
            final_worker_count = len(scaling_manager.active_workers)
            print(f"📊 Final worker count: {final_worker_count} (started with {workers})")
        
        # Signal collector to shutdown and wait
        results_queue.put(None)
        collector.join(timeout=30)
        
    except KeyboardInterrupt:
        print("❌ Interrupted by user")
    
    # Generate final results
    results_collector = BatchResults()
    # ... populate from progress ...
    
    return results_collector
```

### Performance Benefits ⚡

#### **Eliminated Stalls**
- **No batch boundaries**: Workers start next file immediately when available
- **No as_completed() blocking**: Continuous processing pipeline  
- **Reduced I/O overhead**: Progress saved every 25 files (95% reduction)
- **Lazy file loading**: Memory usage scales with workers, not total files

#### **Expected Performance Improvements**
- **25-40% faster processing**: Elimination of idle time between batches
- **90% reduction in I/O overhead**: From 2400+ saves to ~100 saves for 2400 files
- **Better resource utilization**: Workers stay busy continuously
- **Smoother progress reporting**: No artificial pauses in output

#### **Throughput Calculations**
```
Current System:
- 50 files/batch × 2-10s stall between batches = 2-10% idle time
- Progress save per file: 50-100ms × 2400 files = 2-4 minutes total I/O overhead
- Estimated throughput: 6000-7000 files/hour

Rolling System:  
- Zero idle time between files
- Progress save every 25 files: 50-100ms × 96 saves = 5-10 seconds total I/O overhead
- Estimated throughput: 8500-9500 files/hour (25-40% improvement)
```

### Implementation Strategy

#### **Phase 1: Core Rolling Architecture**
1. Create `RollingWorker` class in new `rolling_batch.py` module
2. Implement `FileProducer` for lazy file discovery  
3. Create `ResultsCollector` with optimized progress saving
4. Add `rolling_batch_process_pdfs()` main function

#### **Phase 2: CLI Integration with Auto-Scaling** 
```bash
# Add new CLI flags for rolling mode with auto-scaling
python cli.py --batch --rolling --workers 6 --max-workers 20 --docs-dir docs_correct
python cli.py --batch --rolling --workers 4 --max-workers 15 --auto-scale --limit 100 --verbose  # Testing
python cli.py --batch --rolling --workers 8 --max-workers 8 --no-auto-scale  # Fixed worker count
```

#### **Phase 3: Migration Strategy**
1. Keep existing batch processing as default (backward compatibility)
2. Add `--rolling` flag to enable new system
3. Performance testing with both approaches
4. Make rolling the default after validation

#### **Phase 4: Advanced Optimizations**
- **Dynamic worker scaling based on rate utilization**
- Priority queue for retry-failed files  
- Memory-mapped progress files for ultra-fast saves
- Worker health monitoring and auto-restart

### Testing Plan

#### **Performance Comparison**
```bash
# Test current system
time python cli.py --batch --workers 4 --limit 100 --verbose

# Test rolling system  
time python cli.py --batch --rolling --workers 4 --limit 100 --verbose

# Compare: Total time, idle time, I/O overhead, throughput
```

#### **Reliability Testing**
- Interrupt and resume testing
- Worker failure recovery
- Progress tracking accuracy
- Memory usage monitoring

### Success Metrics

- **25%+ faster processing** compared to current batching system
- **Zero artificial stalls** between file processing
- **90%+ reduction in progress save frequency** 
- **Identical accuracy and reliability** to current system
- **Smooth progress reporting** without batch-related pauses

This rolling workers approach will eliminate the stalling issues and provide much smoother, more efficient batch processing.

## 10. JSON Parsing Error Recovery with Smart Retries 🔄 CRITICAL RELIABILITY FIX

### Current Problem Analysis ❌

When Gemini returns malformed JSON or the response doesn't match the expected schema, the current system fails immediately without retry, losing the entire PDF processing attempt.

#### **Common JSON Parsing Failures:**
1. **Incomplete JSON** - Response truncated mid-object
2. **Invalid JSON syntax** - Missing quotes, commas, brackets
3. **Schema mismatch** - Fields don't match Pydantic model
4. **Nested quotes** - Unescaped quotes in string values
5. **Unicode issues** - Invalid characters in response

### Smart Retry Strategy ✅

#### **1. Retry with JSON Repair**
```python
import json
from json import JSONDecodeError
from typing import Optional, Dict, Any

class JSONRepairStrategy:
    """Attempts to repair common JSON issues before parsing."""
    
    @staticmethod
    def repair_json(raw_text: str) -> str:
        """Try to fix common JSON formatting issues."""
        # Remove any text before first { or [
        start_idx = min(
            raw_text.find('{') if '{' in raw_text else len(raw_text),
            raw_text.find('[') if '[' in raw_text else len(raw_text)
        )
        if start_idx == len(raw_text):
            return raw_text
        
        json_text = raw_text[start_idx:]
        
        # Fix common issues
        repairs = [
            # Fix trailing commas
            (r',\s*}', '}'),
            (r',\s*]', ']'),
            # Fix single quotes (careful not to break apostrophes in text)
            (r"(?<=[{\[,:])\s*'([^']*)'(?=\s*[,}\]]))", r'"\1"'),
            # Fix missing quotes on keys
            (r'(\w+):', r'"\1":'),
            # Fix None to null
            (r'\bNone\b', 'null'),
            # Fix True/False to true/false
            (r'\bTrue\b', 'true'),
            (r'\bFalse\b', 'false'),
        ]
        
        import re
        for pattern, replacement in repairs:
            json_text = re.sub(pattern, replacement, json_text)
        
        return json_text
    
    @staticmethod
    def extract_json_from_markdown(text: str) -> str:
        """Extract JSON from markdown code blocks."""
        # Try to extract from ```json blocks
        import re
        json_pattern = r'```(?:json)?\s*\n?(.*?)```'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text
```

#### **2. Retry with Fallback Prompt**
```python
def get_metadata_with_retry(client, first_pages, last_pages, rate_limiter=None, max_retries: int = 3):
    """Extract metadata with JSON parsing retry logic."""
    
    last_error = None
    retry_strategies = [
        "standard",      # Original prompt
        "simplified",    # Simpler schema, more explicit instructions
        "guided"         # Step-by-step extraction with examples
    ]
    
    for attempt in range(max_retries):
        try:
            # Apply rate limiting
            if rate_limiter:
                wait_time = rate_limiter.wait_if_needed()
                if wait_time > 0:
                    print(f"⏳ Rate limiting: waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
            
            # Select strategy based on attempt number
            strategy = retry_strategies[min(attempt, len(retry_strategies)-1)]
            
            # Get prompt based on strategy
            if strategy == "standard":
                prompt = get_standard_prompt()
            elif strategy == "simplified":
                prompt = get_simplified_prompt()  # Simpler schema
            else:
                prompt = get_guided_prompt()  # More explicit JSON examples
            
            # Call Gemini API
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=[prompt, first_pages, last_pages],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=DocumentMetadata if strategy == "standard" else None
                )
            )
            
            # Try to parse response
            raw_text = response.text
            
            # Attempt JSON repair if needed
            if attempt > 0:
                json_repairer = JSONRepairStrategy()
                raw_text = json_repairer.extract_json_from_markdown(raw_text)
                raw_text = json_repairer.repair_json(raw_text)
            
            # Parse JSON
            try:
                metadata_dict = json.loads(raw_text)
            except JSONDecodeError as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ JSON parsing failed (attempt {attempt+1}/{max_retries}): {e}")
                    print(f"   Trying with {retry_strategies[attempt+1]} strategy...")
                    last_error = e
                    continue
                else:
                    raise
            
            # Validate against Pydantic model
            metadata = DocumentMetadata(**metadata_dict)
            
            if attempt > 0:
                print(f"✅ Successfully parsed JSON after {attempt+1} attempts")
            
            return metadata
            
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                # Exponential backoff: 2, 4, 8 seconds
                backoff = 2 ** (attempt + 1)
                print(f"❌ Attempt {attempt+1}/{max_retries} failed: {type(e).__name__}")
                print(f"   Retrying in {backoff}s with {retry_strategies[attempt+1]} strategy...")
                time.sleep(backoff)
            else:
                print(f"❌ All {max_retries} attempts failed. Last error: {e}")
                raise
    
    # Should never reach here
    raise Exception(f"JSON parsing failed after {max_retries} attempts: {last_error}")
```

#### **3. Simplified Fallback Schema**
```python
class SimplifiedDocumentMetadata(BaseModel):
    """Fallback schema with fewer required fields and more flexibility."""
    title: Optional[str] = None
    creator: Optional[str] = None
    year: Optional[int] = None
    doc_type: Optional[str] = None
    country: Optional[str] = None
    
    # Make everything optional for maximum flexibility
    class Config:
        extra = "allow"  # Allow extra fields
        str_strip_whitespace = True  # Auto-strip whitespace

def get_simplified_prompt() -> str:
    """Simpler prompt with explicit JSON formatting instructions."""
    return '''
Extract metadata from this PDF and return ONLY valid JSON (no markdown, no explanation).

Example of expected JSON format:
{
    "title": "Document Title Here",
    "creator": "Organization Name",
    "year": 2024,
    "doc_type": "Policy",
    "country": "Country Name"
}

Rules:
1. Return ONLY the JSON object, nothing else
2. Use null for missing values, not empty strings
3. Ensure all strings are properly quoted
4. No trailing commas
5. Year must be a number or null
'''
```

#### **4. Integration with Batch Processing**
```python
def process_single_pdf_batch(pdf_path: str, ground_truth: dict, api_key: str, 
                            progress: BatchProgress, results_collector: BatchResults,
                            enable_search: bool = False, search_threshold: float = 0.8,
                            verbose: bool = False, rate_limiter=None, search_quota_tracker=None,
                            max_retries: int = 3) -> bool:
    """Process a single PDF with JSON parsing retry logic."""
    
    filename = Path(pdf_path).name
    thread_name = threading.current_thread().name
    
    # Main retry loop for entire PDF processing
    for pdf_retry in range(max_retries):
        try:
            # Process PDF with JSON parsing retries
            g_client = genai.Client(api_key=api_key)
            first_pages, last_pages = prepare_and_upload_pdf_subset(g_client, pdf_path)
            
            # This function now has its own JSON parsing retry logic
            metadata = get_metadata_with_retry(
                g_client, first_pages, last_pages, 
                rate_limiter, max_retries=3
            )
            
            # Continue with validation, search grounding, etc.
            # ... rest of processing logic ...
            
            return True
            
        except JSONDecodeError as e:
            if pdf_retry < max_retries - 1:
                print(f"[{thread_name}] JSON error for {filename}, retrying entire PDF processing...")
                time.sleep(2 ** (pdf_retry + 1))  # Exponential backoff
            else:
                print(f"[{thread_name}] ❌ Persistent JSON errors for {filename} after {max_retries} attempts")
                results_collector.add_result(pdf_path, {
                    'error_type': 'JSONDecodeError',
                    'error_message': str(e),
                    'metadata': None,
                    'retry_count': pdf_retry
                })
                return False
        
        except Exception as e:
            # Handle other errors as before
            # ...
```

### Benefits of Smart JSON Retry Strategy

1. **Higher Success Rate**: Recovers from ~90% of JSON parsing failures
2. **Progressive Strategies**: Tries increasingly simpler approaches
3. **JSON Repair**: Fixes common formatting issues automatically
4. **Exponential Backoff**: Avoids overwhelming the API
5. **Detailed Logging**: Tracks which strategy succeeded for analysis
6. **Schema Flexibility**: Falls back to simpler schema when needed

### Expected Impact

**Before:**
- JSON parsing failures = complete PDF processing failure
- ~5-10% of PDFs fail due to JSON issues
- Manual intervention required

**After:**
- 3x retry attempts with different strategies
- JSON repair attempts to fix malformed responses
- <1% failure rate for JSON issues
- Automatic recovery without manual intervention

### Testing the JSON Retry Logic

```python
# Test with intentionally malformed JSON
test_cases = [
    '{"title": "Test", "year": 2024,}',  # Trailing comma
    "{'title': 'Test', 'year': 2024}",   # Single quotes
    '{title: "Test", year: 2024}',       # Unquoted keys
    '```json\n{"title": "Test"}\n```',   # Markdown wrapped
    '{"title": "Test", "year": None}',   # Python None instead of null
]

repairer = JSONRepairStrategy()
for test in test_cases:
    repaired = repairer.repair_json(test)
    try:
        parsed = json.loads(repaired)
        print(f"✅ Successfully repaired and parsed")
    except:
        print(f"❌ Failed to repair: {test}")
```

This comprehensive JSON retry strategy will significantly improve reliability and reduce processing failures!

## Conclusion

This enhanced approach creates a robust, multi-layered metadata extraction system that combines:
- Internal metadata extraction
- AI-powered content analysis
- External validation
- Confidence scoring
- Error recovery with JSON retry logic
- **Intelligent rate limiting and throughput optimization**
- **Rolling workers architecture for maximum performance**
- **Smart JSON parsing with automatic repair and retry**

The result will be a production-ready system capable of handling diverse PDF documents with high accuracy, reliability, and maximum performance within API constraints.