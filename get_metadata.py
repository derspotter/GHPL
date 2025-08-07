import os
from google import genai
import json
import pikepdf
import tempfile
import pydantic
from enum import Enum
import subprocess
import time
import threading
import logging
import traceback
from typing import Optional, Union, List
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)

# --- Pydantic Models for Structured Output ---

class DocType(str, Enum):
    """Enumeration for the document types."""
    POLICY = "Policy"
    LAW = "Law"
    NATIONAL_HEALTH_STRATEGY = "National Health Strategy"
    NATIONAL_CONTROL_PLAN = "National Control Plan"
    ACTION_PLAN = "Action Plan"   
    HEALTH_GUIDELINE = "Health Guideline"
    
class Creator(str, Enum):
    PARLIAMENT = "Parliament"
    MINISTRY = "Ministry"
    AGENCY = "Agency"
    FOUNDATION = "Foundation"
    ASSOCIATION = "Association"
    SOCIETY = "Society"

class HealthTopic(str, Enum):
    """Enumeration for primary health topics."""
    CANCER = "Cancer"
    NON_COMMUNICABLE_DISEASE = "Non-Communicable Disease"
    CARDIOVASCULAR_HEALTH = "Cardiovascular Health"

class GovernanceLevel(str, Enum):
    """Enumeration for governance levels."""
    NATIONAL = "National"
    REGIONAL = "Regional"

class ConfidenceLevel(str, Enum):
    """Confidence level categories for metadata extraction."""
    HIGH = "high"          # >= 0.8
    MEDIUM = "medium"      # >= 0.6
    LOW = "low"           # >= 0.4
    VERY_LOW = "very_low" # < 0.4

class StringFieldMetadata(pydantic.BaseModel):
    """Metadata for free-text fields that can contain any string."""
    value: Optional[str] = pydantic.Field(None, description="The extracted string value")
    confidence: float = pydantic.Field(0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: str = pydantic.Field("", description="Justification or source of the extraction")
    source_page: Optional[int] = pydantic.Field(None, description="Page number where value was found")
    alternatives: Optional[List[str]] = pydantic.Field(default_factory=list, description="Alternative values found")

class IntFieldMetadata(pydantic.BaseModel):
    """Metadata for integer fields like year."""
    value: Optional[int] = pydantic.Field(None, description="The extracted integer value")
    confidence: float = pydantic.Field(0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: str = pydantic.Field("", description="Justification or source of the extraction")
    source_page: Optional[int] = pydantic.Field(None, description="Page number where value was found")
    alternatives: Optional[List[str]] = pydantic.Field(default_factory=list, description="Alternative values found")

class DocTypeFieldMetadata(pydantic.BaseModel):
    """Metadata for document type field - ONLY accepts DocType enum values."""
    value: Optional[DocType] = pydantic.Field(None, description="The document type - must be from DocType enum")
    confidence: float = pydantic.Field(0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: str = pydantic.Field("", description="Justification or source of the extraction")
    source_page: Optional[int] = pydantic.Field(None, description="Page number where value was found")
    alternatives: Optional[List[str]] = pydantic.Field(default_factory=list, description="Alternative values found")

class CreatorFieldMetadata(pydantic.BaseModel):
    """Metadata for creator field - ONLY accepts Creator enum values."""
    value: Optional[Creator] = pydantic.Field(None, description="The creator type - must be from Creator enum")
    confidence: float = pydantic.Field(0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: str = pydantic.Field("", description="Justification or source of the extraction")
    source_page: Optional[int] = pydantic.Field(None, description="Page number where value was found")
    alternatives: Optional[List[str]] = pydantic.Field(default_factory=list, description="Alternative values found")

class HealthTopicFieldMetadata(pydantic.BaseModel):
    """Metadata for health topic field - ONLY accepts HealthTopic enum values."""
    value: Optional[HealthTopic] = pydantic.Field(None, description="The health topic - must be from HealthTopic enum")
    confidence: float = pydantic.Field(0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: str = pydantic.Field("", description="Justification or source of the extraction")
    source_page: Optional[int] = pydantic.Field(None, description="Page number where value was found")
    alternatives: Optional[List[str]] = pydantic.Field(default_factory=list, description="Alternative values found")

class GovernanceLevelFieldMetadata(pydantic.BaseModel):
    """Metadata for governance level field - ONLY accepts GovernanceLevel enum values."""
    value: Optional[GovernanceLevel] = pydantic.Field(None, description="The governance level - must be from GovernanceLevel enum")
    confidence: float = pydantic.Field(0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: str = pydantic.Field("", description="Justification or source of the extraction")
    source_page: Optional[int] = pydantic.Field(None, description="Page number where value was found")
    alternatives: Optional[List[str]] = pydantic.Field(default_factory=list, description="Alternative values found")

class DocumentMetadata(pydantic.BaseModel):
    """Enhanced document metadata with confidence scoring and strict enum enforcement."""
    # Enum fields - ONLY accept enum values
    doc_type: DocTypeFieldMetadata = pydantic.Field(description="The document type - must be from DocType enum.")
    health_topic: HealthTopicFieldMetadata = pydantic.Field(description="The primary health topic - must be from HealthTopic enum.")
    creator: CreatorFieldMetadata = pydantic.Field(description="The creating entity - must be from Creator enum.")
    level: GovernanceLevelFieldMetadata = pydantic.Field(description="The governance level - must be from GovernanceLevel enum.")
    
    # Free-text fields - accept any string
    title: StringFieldMetadata = pydantic.Field(description="The document title.")
    country: StringFieldMetadata = pydantic.Field(description="The country name.")
    language: StringFieldMetadata = pydantic.Field(description="The primary language.")
    
    # Integer field
    year: IntFieldMetadata = pydantic.Field(description="The publication year.")
    
    # Overall metadata quality scores
    overall_confidence: Optional[float] = pydantic.Field(None, ge=0.0, le=1.0, description="Overall confidence score")
    metadata_completeness: Optional[float] = pydantic.Field(None, ge=0.0, le=1.0, description="Completeness of metadata")


def repair_pdf_with_qpdf(damaged_path, repaired_path):
    """Repairs a damaged PDF using the qpdf command-line tool."""
    print(f"Attempting to repair PDF with qpdf: {damaged_path}")
    try:
        subprocess.run(
            ['qpdf', damaged_path, repaired_path],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"PDF repaired and saved to: {repaired_path}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"qpdf repair failed. Error: {e}")
        if isinstance(e, subprocess.CalledProcessError):
            print(f"qpdf stderr: {e.stderr}")
        return False

def prepare_and_upload_pdf_subset(client, pdf_path, first_pages=3, last_pages=2, max_retries=3):
    """
    Uses pikepdf to select the first few and last few pages of a PDF, saves them to
    temporary files, and uploads them using the provided client.
    Includes a fallback to qpdf for repair.

    Args:
        client (genai.Client): The initialized Google GenAI client.
        pdf_path (str): The path to the source PDF file.
        first_pages (int): The number of pages from the beginning to process.
        last_pages (int): The number of pages from the end to process.

    Returns:
        tuple: A tuple of (first_pages_file, last_pages_file) uploaded file objects, or (None, None) if an error occurs.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file '{pdf_path}' was not found.")

    uploaded_first = None
    uploaded_last = None
    temp_first_path = None
    temp_last_path = None
    
    try:
        # 1. Create temporary files for both subsets
        with tempfile.NamedTemporaryFile(delete=False, suffix="_first.pdf") as temp_f:
            temp_first_path = temp_f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix="_last.pdf") as temp_f:
            temp_last_path = temp_f.name

        # 2. Try to process with pikepdf, with qpdf as a fallback
        try:
            print(f"Using pikepdf to extract first {first_pages} and last {last_pages} pages...")
            with pikepdf.open(pdf_path) as source_pdf:
                total_pages = len(source_pdf.pages)
                if total_pages == 0:
                    print("Error: PDF has 0 pages.")
                    return None, None
                
                # Create first pages PDF
                first_pdf = pikepdf.Pdf.new()
                pages_to_extract = min(total_pages, first_pages)
                for i in range(pages_to_extract):
                    first_pdf.pages.append(source_pdf.pages[i])
                first_pdf.save(temp_first_path)
                
                # Create last pages PDF
                last_pdf = pikepdf.Pdf.new()
                if total_pages > first_pages:  # Only extract last pages if document is long enough
                    start_index = max(0, total_pages - last_pages)
                    for i in range(start_index, total_pages):
                        last_pdf.pages.append(source_pdf.pages[i])
                    last_pdf.save(temp_last_path)
                else:
                    # If document is too short, just use the same as first pages
                    last_pdf = None
                    temp_last_path = None

        except pikepdf.PdfError as e:
            print(f"pikepdf failed: {e}. Trying to repair with qpdf.")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as repaired_temp_f:
                repaired_pdf_path = repaired_temp_f.name
            
            if repair_pdf_with_qpdf(pdf_path, repaired_pdf_path):
                # Retry with the repaired PDF
                with pikepdf.open(repaired_pdf_path) as source_pdf:
                    total_pages = len(source_pdf.pages)
                    
                    # Create first pages PDF
                    first_pdf = pikepdf.Pdf.new()
                    pages_to_extract = min(total_pages, first_pages)
                    for i in range(pages_to_extract):
                        first_pdf.pages.append(source_pdf.pages[i])
                    first_pdf.save(temp_first_path)
                    
                    # Create last pages PDF
                    if total_pages > first_pages:
                        last_pdf = pikepdf.Pdf.new()
                        start_index = max(0, total_pages - last_pages)
                        for i in range(start_index, total_pages):
                            last_pdf.pages.append(source_pdf.pages[i])
                        last_pdf.save(temp_last_path)
                    else:
                        temp_last_path = None
                        
                os.remove(repaired_pdf_path)
            else:
                return None, None # Repair failed

        print(f"Temporary PDF subsets created")

        # 3. Upload both files using the client with retry logic
        print("Uploading PDF subsets to Gemini...")
        display_name = os.path.basename(pdf_path)
        
        # Upload first pages with retry
        for retry in range(max_retries + 1):
            try:
                if retry > 0:
                    backoff_time = (2 ** retry) * 2
                    logger.info(f"Retrying upload of first pages (attempt {retry + 1}/{max_retries + 1}) after {backoff_time}s")
                    print(f"Retrying upload after {backoff_time}s...")
                    time.sleep(backoff_time)
                
                uploaded_first = client.files.upload(file=temp_first_path)
                print(f"Successfully uploaded first pages: {uploaded_first.name}")
                break
            except Exception as e:
                logger.error(f"Upload failed (attempt {retry + 1}/{max_retries + 1}): {e}")
                if retry >= max_retries:
                    raise Exception(f"Failed to upload first pages after {max_retries + 1} attempts: {e}")
        
        # Upload last pages with retry
        if temp_last_path:
            for retry in range(max_retries + 1):
                try:
                    if retry > 0:
                        backoff_time = (2 ** retry) * 2
                        logger.info(f"Retrying upload of last pages (attempt {retry + 1}/{max_retries + 1}) after {backoff_time}s")
                        print(f"Retrying upload after {backoff_time}s...")
                        time.sleep(backoff_time)
                    
                    uploaded_last = client.files.upload(file=temp_last_path)
                    print(f"Successfully uploaded last pages: {uploaded_last.name}")
                    break
                except Exception as e:
                    logger.error(f"Upload failed (attempt {retry + 1}/{max_retries + 1}): {e}")
                    if retry >= max_retries:
                        # Clean up first upload if second fails
                        if uploaded_first:
                            try:
                                client.files.delete(name=uploaded_first.name)
                            except:
                                pass
                        raise Exception(f"Failed to upload last pages after {max_retries + 1} attempts: {e}")

    except Exception as e:
        print(f"An error occurred during PDF processing or upload: {e}")
        if uploaded_first:
            client.files.delete(name=uploaded_first.name)
        if uploaded_last:
            client.files.delete(name=uploaded_last.name)
        return None, None
    finally:
        # 4. Clean up the temporary files from the local disk
        if temp_first_path and os.path.exists(temp_first_path):
            os.remove(temp_first_path)
        if temp_last_path and os.path.exists(temp_last_path):
            os.remove(temp_last_path)
        print(f"Cleaned up temporary files")
            
    return uploaded_first, uploaded_last


def get_confidence_level(score: float) -> ConfidenceLevel:
    """Map confidence score to confidence level."""
    if score >= 0.8:
        return ConfidenceLevel.HIGH
    elif score >= 0.6:
        return ConfidenceLevel.MEDIUM
    elif score >= 0.4:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.VERY_LOW

def calculate_overall_confidence(metadata: DocumentMetadata) -> float:
    """Calculate overall document metadata confidence."""
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

def calculate_metadata_completeness(metadata: DocumentMetadata) -> float:
    """Calculate how complete the metadata extraction was."""
    fields = ['title', 'creator', 'year', 'doc_type', 'country', 'health_topic', 'language', 'level']
    fields_found = sum(1 for f in fields if getattr(metadata, f).value is not None)
    return round(fields_found / len(fields), 3)

def recommend_action(metadata: DocumentMetadata) -> dict:
    """Recommend actions based on confidence scores."""
    recommendations = []
    
    for field_name in ['title', 'creator', 'year', 'doc_type']:
        field = getattr(metadata, field_name)
        if field.value is None:
            recommendations.append({
                'field': field_name,
                'action': 'manual_extraction',
                'reason': 'Field not found'
            })
        else:
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

def get_metadata_from_gemini(client, first_pages_file, last_pages_file, rate_limiter=None, max_retries=3):
    """
    Uses the Gemini API with structured output to extract metadata from PDF pages.

    Args:
        client (genai.Client): The initialized Google GenAI client.
        first_pages_file (genai.files.File): The uploaded file object for first pages.
        last_pages_file (genai.files.File): The uploaded file object for last pages (can be None).
        rate_limiter (RateLimiter, optional): Rate limiter for API calls.

    Returns:
        DocumentMetadata: A Pydantic object with the extracted metadata, or None.
    """
    if not first_pages_file:
        print("No uploaded file was provided to the Gemini API.")
        return None

    model_name = 'gemini-2.5-flash'
    pdf_filename = first_pages_file.display_name
    
    # Build contents list based on available files
    contents = []
    
    confidence_prompt_template = """
    For each metadata field, provide the appropriate field type with:
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
    5. **alternatives**: Other possible values you considered (as a list)

    ⚠️ CRITICAL ENUM REQUIREMENTS - THESE MUST BE FOLLOWED EXACTLY:
    
    **doc_type** MUST be EXACTLY one of these values (no other values allowed):
    - "Policy"
    - "Law" 
    - "National Health Strategy"
    - "National Control Plan"
    - "Action Plan"
    - "Health Guideline"
    
    **health_topic** MUST be EXACTLY one of these values (no other values allowed):
    - "Cancer": for cancer-related documents (oncology, cancer screening, cancer treatment)
    - "Cardiovascular Health": for heart and blood vessel diseases (hypertension, heart disease, stroke, etc.)
    - "Non-Communicable Disease": ONLY if the document covers BOTH cancer AND cardiovascular diseases together
    
    **creator** MUST be EXACTLY one of these values (no other values allowed):
    - "Parliament"
    - "Ministry"
    - "Agency"
    - "Foundation"
    - "Association"
    - "Society"
    
    **level** MUST be EXACTLY one of these values (no other values allowed):
    - "National"
    - "Regional"
    
    If you cannot determine which enum value applies, set the value to null rather than guessing or creating new values.
    
    Other fields (title, country, language, year) can contain any appropriate values.
    
    ⚠️ TITLE FORMATTING REQUIREMENT:
    For the **title** field, convert ALL CAPS text to proper title case. For example:
    - "UPDATED MANAGEMENT OF HYPERTENSION IN ADULTS" → "Updated Management of Hypertension in Adults"
    - "NATIONAL HEALTH STRATEGY FOR CANCER" → "National Health Strategy for Cancer"
    Extract the meaningful title content, not just formatting artifacts.

    Return the complete DocumentMetadata object using the correct field types.
    Include overall_confidence and metadata_completeness calculations.
    """
    
    if last_pages_file:
        prompt = f"""
        I'm providing you with two PDF files from the same document:
        1. {first_pages_file.name}: The first 3 pages of the document
        2. {last_pages_file.name}: The last 2 pages of the document
        
        {confidence_prompt_template}
        """
        contents = [prompt, first_pages_file, last_pages_file]
    else:
        prompt = f"""
        The name of the source file is '{pdf_filename}'.
        
        {confidence_prompt_template}
        """
        contents = [prompt, first_pages_file]

    # Retry logic for Gemini API calls
    for retry in range(max_retries + 1):
        try:
            if retry > 0:
                backoff_time = (2 ** retry) * 2
                logger.info(f"Retrying Gemini API call (attempt {retry + 1}/{max_retries + 1}) after {backoff_time}s")
                print(f"⏳ Retrying API call after {backoff_time}s...")
                time.sleep(backoff_time)
            
            print(f"Sending uploaded PDFs to '{model_name}' for structured metadata extraction (attempt {retry + 1}/{max_retries + 1})...")
            
            # Apply rate limiting if provided
            if rate_limiter:
                wait_time = rate_limiter.wait_if_needed()
                if wait_time > 0:
                    print(f"⏳ Rate limiting: waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
            
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': DocumentMetadata,
                }
            )
            
            # Parse the JSON response into our Pydantic model
            metadata = DocumentMetadata.model_validate_json(response.text)
            
            # Calculate overall scores
            metadata.overall_confidence = calculate_overall_confidence(metadata)
            metadata.metadata_completeness = calculate_metadata_completeness(metadata)
            
            if retry > 0:
                logger.info(f"Successfully extracted metadata after {retry} retries")
                print(f"✅ Successfully extracted metadata after {retry} retries")
            
            # Clean up uploaded files before returning successful result
            try:
                print(f"Deleting uploaded files from server...")
                client.files.delete(name=first_pages_file.name)
                if last_pages_file:
                    client.files.delete(name=last_pages_file.name)
                print("Files deleted.")
            except Exception as cleanup_error:
                logger.warning(f"Warning: Error during successful cleanup: {cleanup_error}")
            
            return metadata
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini API error (attempt {retry + 1}/{max_retries + 1}): {type(e).__name__}: {error_msg}")
            logger.debug(f"Full traceback:\n{traceback.format_exc()}")
            
            # Check if error is retryable
            retryable_errors = [
                'rate limit', 'quota', 'timeout', '503', '429',
                'connection', 'temporary', 'unavailable'
            ]
            
            should_retry = any(err in error_msg.lower() for err in retryable_errors)
            
            if not should_retry or retry >= max_retries:
                print(f"❌ Failed after {retry + 1} attempts: {type(e).__name__}: {e}")
                return None
            
            print(f"⚠️ Attempt {retry + 1} failed: {e}")
    
    # Should never reach here - clean up files and return None
    try:
        print(f"Deleting uploaded files from server...")
        client.files.delete(name=first_pages_file.name)
        if last_pages_file:
            client.files.delete(name=last_pages_file.name)
        print("Files deleted.")
    except Exception as cleanup_error:
        logger.error(f"Error during file cleanup: {cleanup_error}")
    
    return None


if __name__ == "__main__":
    # --- Configuration ---
    # IMPORTANT: You need to install pydantic: pip install pydantic
    # IMPORTANT: Set your Gemini API key as an environment variable or replace below
    import os
    API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE"))


    # --- PDF File ---
    PDF_FILE_PATH = "/home/justus/Nextcloud/GHPL/docs/ZAF_D1_Hypertension_Guideline_December_2006.pdf"  # Path to the PDF file to be processed

    # --- Processing ---
    if  not API_KEY:
        print("Please set the GEMINI_API_KEY environment variable or replace 'YOUR_API_KEY' with your actual Gemini API key.")
    elif not os.path.exists(PDF_FILE_PATH):
         print(f"Please provide a valid file path. '{PDF_FILE_PATH}' not found.")
    else:
        try:
            # Initialize the client once with the API key
            g_client = genai.Client(api_key=API_KEY)

            first_pages, last_pages = prepare_and_upload_pdf_subset(g_client, PDF_FILE_PATH)

            if first_pages:
                metadata = get_metadata_from_gemini(g_client, first_pages, last_pages)

                if metadata:
                    print("\n--- Extracted Metadata with Confidence Scores ---")
                    print(f"Overall Confidence: {metadata.overall_confidence:.2f} ({get_confidence_level(metadata.overall_confidence or 0.0).value})")
                    print(f"Metadata Completeness: {metadata.metadata_completeness:.1%}")
                    print("-" * 50)
                    
                    # Display each field with confidence
                    def display_field(name: str, field):
                        if field.value is not None:
                            confidence_level = get_confidence_level(field.confidence)
                            print(f"{name}: {field.value}")
                            print(f"  ├─ Confidence: {field.confidence:.2f} ({confidence_level.value})")
                            if field.evidence:
                                print(f"  ├─ Evidence: {field.evidence}")
                            if field.source_page:
                                print(f"  ├─ Source: Page {field.source_page}")
                            if field.alternatives:
                                print(f"  └─ Alternatives: {', '.join(field.alternatives)}")
                        else:
                            print(f"{name}: Not found")
                            if field.evidence:
                                print(f"  └─ Note: {field.evidence}")
                        print()
                    
                    display_field("Title", metadata.title)
                    display_field("Document Type", metadata.doc_type)
                    display_field("Health Topic", metadata.health_topic)
                    display_field("Creator", metadata.creator)
                    display_field("Year", metadata.year)
                    display_field("Country", metadata.country)
                    display_field("Language", metadata.language)
                    display_field("Governance Level", metadata.level)
                    
                    # Show recommendations
                    print("-" * 50)
                    recommendations = recommend_action(metadata)
                    if recommendations['requires_review']:
                        print("⚠️  Manual Review Recommended:")
                        for rec in recommendations['recommendations']:
                            print(f"  • {rec['field']}: {rec['reason']}")
                            if 'alternatives' in rec:
                                print(f"    Alternatives: {', '.join(rec['alternatives'])}")
                    else:
                        print("✅ All fields extracted with acceptable confidence")
                    print("-" * 50)

        except FileNotFoundError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
