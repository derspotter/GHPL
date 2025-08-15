import os
from google import genai
import json
import pydantic
from enum import Enum
import time
import logging
import traceback
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Suppress httpx INFO logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)
# Suppress Google GenAI INFO logs
logging.getLogger("google_genai").setLevel(logging.WARNING)

# --- Pydantic Models for Structured Output (from get_metadata.py) ---

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
    INTERNATIONAL = "International"

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


def upload_pdf_subset(client, pdf_path, first_pages=10, last_pages=5, max_retries=3):
    """
    Extract and upload a subset of PDF pages to Gemini.
    
    Args:
        client (genai.Client): The initialized Google GenAI client.
        pdf_path (str): The path to the PDF file.
        first_pages (int): Number of pages from the beginning.
        last_pages (int): Number of pages from the end.
        max_retries (int): Maximum number of retry attempts.
    
    Returns:
        tuple: (first_pages_file, last_pages_file) or (None, None) if failed.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file '{pdf_path}' was not found.")
    
    import pikepdf
    import tempfile
    
    # Get file size for logging
    file_size = os.path.getsize(pdf_path)
    file_size_mb = file_size / (1024 * 1024)
    print(f"📁 Extracting subset from PDF: {os.path.basename(pdf_path)} ({file_size_mb:.2f} MB)")
    print(f"   Taking first {first_pages} and last {last_pages} pages...")
    
    temp_first_path = None
    temp_last_path = None
    uploaded_first = None
    uploaded_last = None
    
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix="_first.pdf") as temp_f:
            temp_first_path = temp_f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix="_last.pdf") as temp_f:
            temp_last_path = temp_f.name
        
        # Extract pages using pikepdf
        with pikepdf.open(pdf_path) as source_pdf:
            total_pages = len(source_pdf.pages)
            print(f"   Total pages in PDF: {total_pages}")
            
            if total_pages == 0:
                print("❌ PDF has 0 pages")
                return None, None
            
            # Create first pages PDF
            first_pdf = pikepdf.Pdf.new()
            pages_to_extract = min(total_pages, first_pages)
            for i in range(pages_to_extract):
                first_pdf.pages.append(source_pdf.pages[i])
            first_pdf.save(temp_first_path)
            print(f"   ✅ Extracted first {pages_to_extract} pages")
            
            # Create last pages PDF (if document is long enough)
            last_pdf = pikepdf.Pdf.new()
            if total_pages > first_pages:
                start_index = max(first_pages, total_pages - last_pages)  # Avoid overlap
                pages_extracted = 0
                for i in range(start_index, total_pages):
                    last_pdf.pages.append(source_pdf.pages[i])
                    pages_extracted += 1
                last_pdf.save(temp_last_path)
                print(f"   ✅ Extracted last {pages_extracted} pages")
            else:
                # Document too short - no separate last pages needed
                temp_last_path = None
                print(f"   📝 Document too short - using only first pages")
        
        # Upload both files
        print("📤 Uploading PDF subsets to Gemini...")
        
        for retry in range(max_retries + 1):
            try:
                if retry > 0:
                    backoff_time = (2 ** retry) * 2
                    print(f"⏳ Retrying upload after {backoff_time}s...")
                    time.sleep(backoff_time)
                
                # Upload first pages
                uploaded_first = client.files.upload(file=temp_first_path)
                print(f"✅ Uploaded first pages: {uploaded_first.name}")
                
                # Upload last pages if exists
                if temp_last_path:
                    uploaded_last = client.files.upload(file=temp_last_path)
                    print(f"✅ Uploaded last pages: {uploaded_last.name}")
                
                break
                
            except Exception as e:
                logger.error(f"Upload failed (attempt {retry + 1}/{max_retries + 1}): {e}")
                if retry >= max_retries:
                    print(f"❌ Failed to upload PDF subsets after {max_retries + 1} attempts: {e}")
                    return None, None
        
        return uploaded_first, uploaded_last
        
    except Exception as e:
        print(f"❌ Error during PDF processing: {e}")
        logger.error(f"PDF processing error: {e}")
        return None, None
        
    finally:
        # Cleanup temporary files
        if temp_first_path and os.path.exists(temp_first_path):
            os.remove(temp_first_path)
        if temp_last_path and os.path.exists(temp_last_path):
            os.remove(temp_last_path)


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


def extract_metadata_from_pdf_subset(client, first_pages_file, last_pages_file, pdf_path, max_retries=3):
    """
    Extract metadata from PDF subsets using Gemini.
    
    Args:
        client (genai.Client): The initialized Google GenAI client.
        first_pages_file (genai.files.File): The uploaded first pages file object.
        last_pages_file (genai.files.File): The uploaded last pages file object (can be None).
        pdf_path (str): Original path to the PDF (for filename reference).
        max_retries (int): Maximum number of retry attempts.
    
    Returns:
        tuple: (DocumentMetadata, first_pages_file, last_pages_file) or (None, None, None) if failed.
    """
    if not first_pages_file:
        print("No uploaded file was provided to the Gemini API.")
        return None, None, None
    
    model_name = 'gemini-2.5-flash'  # Using gemini 2.5 flash
    pdf_filename = os.path.basename(pdf_path)
    
    # Build contents based on available files
    if last_pages_file:
        prompt = f"""
        I'm providing you with two PDF files from the same document:
        1. {first_pages_file.name}: The first 10 pages of the document
        2. {last_pages_file.name}: The last 5 pages of the document
        
        Extract metadata from these PDF subsets representing the complete document.
        
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
        4. **source_page**: Which page contained this information
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
        - "International"
        
        If you cannot determine which enum value applies, set the value to null rather than guessing or creating new values.
        
        Other fields (title, country, language, year) can contain any appropriate values.
        
        ⚠️ TITLE FORMATTING REQUIREMENT:
        For the **title** field, convert ALL CAPS text to proper title case. For example:
        - "UPDATED MANAGEMENT OF HYPERTENSION IN ADULTS" → "Updated Management of Hypertension in Adults"
        - "NATIONAL HEALTH STRATEGY FOR CANCER" → "National Health Strategy for Cancer"
        Extract the meaningful title content, not just formatting artifacts.

        The source filename is: {pdf_filename}
        
        Return the complete DocumentMetadata object using the correct field types.
        """
        contents = [prompt, first_pages_file, last_pages_file]
    else:
        prompt = f"""
        Extract metadata from this PDF subset representing the document.
        
        The source filename is: {pdf_filename}
        
        For each metadata field, provide the appropriate field type with confidence scores and evidence.
        Follow the exact enum requirements for doc_type, health_topic, creator, and level fields.
        
        Return the complete DocumentMetadata object using the correct field types.
        """
        contents = [prompt, first_pages_file]
    
    # Retry logic for Gemini API calls
    for retry in range(max_retries + 1):
        try:
            if retry > 0:
                backoff_time = (2 ** retry) * 3
                logger.info(f"Retrying Gemini API call (attempt {retry + 1}/{max_retries + 1}) after {backoff_time}s")
                print(f"⏳ Retrying API call after {backoff_time}s...")
                time.sleep(backoff_time)
            
            print(f"🤖 Sending PDF subsets to '{model_name}' for metadata extraction (attempt {retry + 1}/{max_retries + 1})...")
            
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': DocumentMetadata,
                    'temperature': 0.1
                }
            )
            
            # Log detailed token usage if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                output_tokens = getattr(usage, 'candidates_token_count', 0)
                thinking_tokens = getattr(usage, 'thoughts_token_count', 0)
                total_tokens = getattr(usage, 'total_token_count', 0)
                
                print(f"📊 Token Usage:")
                print(f"  ├─ Input tokens: {prompt_tokens:,}")
                print(f"  ├─ Output tokens: {output_tokens:,}")
                
                if thinking_tokens > 0:
                    print(f"  ├─ Thinking tokens: {thinking_tokens:,}")
                    print(f"  ├─ Sum (I+O+T): {prompt_tokens + output_tokens + thinking_tokens:,}")
                else:
                    print(f"  ├─ Sum (I+O): {prompt_tokens + output_tokens:,}")
                
                print(f"  ├─ Total reported: {total_tokens:,}")
                
                # Calculate actual cost (Gemini 2.5 Flash pricing as of 2025)
                # Source: https://ai.google.dev/gemini-api/docs/pricing
                # Input: $0.30 per 1M tokens, Output: $2.50 per 1M tokens
                input_cost = (prompt_tokens / 1_000_000) * 0.30
                output_cost = ((output_tokens + thinking_tokens) / 1_000_000) * 2.50
                total_cost = input_cost + output_cost
                
                print(f"  ├─ Cost estimate:")
                print(f"  │  ├─ Input: ${input_cost:.6f}")
                print(f"  │  ├─ Output+Thinking: ${output_cost:.6f}")
                print(f"  │  └─ Total: ${total_cost:.6f}")
                
                # Check for any remaining discrepancy
                expected_total = prompt_tokens + output_tokens + thinking_tokens
                if total_tokens > expected_total:
                    other_tokens = total_tokens - expected_total
                    print(f"  └─ Other tokens: {other_tokens:,} (system overhead)")
                else:
                    print(f"  └─ All tokens accounted for")
            
            # Parse the JSON response into our Pydantic model
            metadata = DocumentMetadata.model_validate_json(response.text)
            
            # Calculate overall scores
            metadata.overall_confidence = calculate_overall_confidence(metadata)
            metadata.metadata_completeness = calculate_metadata_completeness(metadata)
            
            if retry > 0:
                logger.info(f"Successfully extracted metadata after {retry} retries")
                print(f"✅ Successfully extracted metadata after {retry} retries")
            else:
                print(f"✅ Successfully extracted metadata")
            
            return metadata, first_pages_file, last_pages_file
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini API error (attempt {retry + 1}/{max_retries + 1}): {type(e).__name__}: {error_msg}")
            logger.debug(f"Full traceback:\n{traceback.format_exc()}")
            
            # Try to extract more detailed error information
            print(f"🔍 Detailed Error Analysis:")
            print(f"   Error Type: {type(e).__name__}")
            print(f"   Error Message: {error_msg}")
            
            # Check if it's a Google API error with more details
            if hasattr(e, 'details'):
                print(f"   Error Details: {e.details}")
            if hasattr(e, 'code'):
                print(f"   Error Code: {e.code}")
            if hasattr(e, 'message'):
                print(f"   Error Message: {e.message}")
            if hasattr(e, 'response'):
                print(f"   Response: {e.response}")
                if hasattr(e.response, 'text'):
                    print(f"   Response Text: {e.response.text}")
                if hasattr(e.response, 'headers'):
                    print(f"   Response Headers: {dict(e.response.headers)}")
                if hasattr(e.response, 'content'):
                    print(f"   Response Content: {e.response.content}")
                if hasattr(e.response, 'json'):
                    try:
                        json_data = e.response.json()
                        print(f"   Response JSON: {json_data}")
                    except:
                        pass
            if hasattr(e, 'reason'):
                print(f"   Reason: {e.reason}")
                
            # Print all available attributes of the error
            print(f"   Available Error Attributes: {[attr for attr in dir(e) if not attr.startswith('_')]}")
            
            # Check for specific error conditions
            if "INVALID_ARGUMENT" in error_msg:
                print(f"   Analysis: INVALID_ARGUMENT typically means:")
                print(f"     • Request format is incorrect")
                print(f"     • Model doesn't support this operation")
                print(f"     • Content violates policies")
                print(f"     • Input exceeds processing limits")
            
            # Check if error is retryable
            retryable_errors = [
                'rate limit', 'quota', 'timeout', '503', '429',
                'connection', 'temporary', 'unavailable'
            ]
            
            should_retry = any(err in error_msg.lower() for err in retryable_errors)
            
            if not should_retry or retry >= max_retries:
                print(f"❌ Failed after {retry + 1} attempts: {type(e).__name__}: {e}")
                # Clean up files on failure
                try:
                    print(f"🗑️ Deleting uploaded files from server...")
                    if first_pages_file:
                        client.files.delete(name=first_pages_file.name)
                    if last_pages_file:
                        client.files.delete(name=last_pages_file.name)
                    print("Files deleted.")
                except Exception as cleanup_error:
                    logger.warning(f"Warning: Error during cleanup: {cleanup_error}")
                return None, None, None
            
            print(f"⚠️ Attempt {retry + 1} failed: {e}")
    
    # Should never reach here - clean up files and return None
    try:
        print(f"🗑️ Deleting uploaded files from server...")
        if first_pages_file:
            client.files.delete(name=first_pages_file.name)
        if last_pages_file:
            client.files.delete(name=last_pages_file.name)
        print("Files deleted.")
    except Exception as cleanup_error:
        logger.error(f"Error during file cleanup: {cleanup_error}")
    
    return None, None, None


def display_field(name: str, field):
    """Display a metadata field with its confidence and evidence."""
    if field.value is not None:
        confidence_level = get_confidence_level(field.confidence)
        
        # Display the actual value - use .value for enums to show clean string
        if hasattr(field.value, 'value'):
            display_value = field.value.value  # For enum fields
        else:
            display_value = field.value  # For regular string/int fields
        
        print(f"{name}: {display_value}")
        print(f"  ├─ Confidence: {field.confidence:.2f} ({confidence_level.value})")
        if field.evidence:
            print(f"  ├─ Evidence: {field.evidence}")  # Show full evidence
        if field.source_page:
            print(f"  ├─ Source: Page {field.source_page}")
        if field.alternatives:
            print(f"  └─ Alternatives: {', '.join(field.alternatives[:3])}")  # Show first 3 alternatives
    else:
        print(f"{name}: Not found")
        if field.evidence:
            print(f"  └─ Note: {field.evidence}")
    print()


def main():
    """Main function to run the metadata extraction."""
    # Get API key from environment
    API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not API_KEY:
        print("❌ Please set the GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        print("   You can also create a .env file with: GOOGLE_API_KEY=your-api-key")
        return
    
    # Example PDF path - change this to your target PDF
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default test file
        pdf_path = "docs_correct/2017-27762.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return
    
    try:
        # Initialize the client
        print("🔧 Initializing Gemini client...")
        client = genai.Client(api_key=API_KEY)
        
        # Upload PDF subsets (first 10 + last 5 pages)
        first_pages_file, last_pages_file = upload_pdf_subset(client, pdf_path)
        
        if not first_pages_file:
            print("❌ Failed to upload PDF subsets")
            return
        
        # Extract metadata from subsets
        metadata, first_file, last_file = extract_metadata_from_pdf_subset(client, first_pages_file, last_pages_file, pdf_path)
        
        if metadata:
            print("\n" + "=" * 60)
            print("📊 EXTRACTED METADATA WITH CONFIDENCE SCORES")
            print("=" * 60)
            print(f"Overall Confidence: {metadata.overall_confidence:.2f} ({get_confidence_level(metadata.overall_confidence or 0.0).value})")
            print(f"Metadata Completeness: {metadata.metadata_completeness:.1%}")
            print("-" * 60)
            
            # Display each field
            display_field("Title", metadata.title)
            display_field("Document Type", metadata.doc_type)
            display_field("Health Topic", metadata.health_topic)
            display_field("Creator", metadata.creator)
            display_field("Year", metadata.year)
            display_field("Country", metadata.country)
            display_field("Language", metadata.language)
            display_field("Governance Level", metadata.level)
            
            print("-" * 60)
            
            # Recommendations
            if metadata.overall_confidence and metadata.overall_confidence < 0.7:
                print("⚠️ Low overall confidence - manual review recommended")
            elif metadata.metadata_completeness and metadata.metadata_completeness < 0.8:
                print("⚠️ Incomplete metadata - some fields missing")
            else:
                print("✅ High confidence extraction complete")
        
        # Clean up uploaded files
        try:
            print("\n🗑️ Cleaning up uploaded files...")
            if first_file:
                client.files.delete(name=first_file.name)
                print("✅ Deleted first pages file")
            if last_file:
                client.files.delete(name=last_file.name)
                print("✅ Deleted last pages file")
            print("✅ Cleanup complete")
        except Exception as e:
            logger.warning(f"Warning: Could not clean up uploaded files: {e}")
                
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"Full error: {traceback.format_exc()}")


if __name__ == "__main__":
    main()