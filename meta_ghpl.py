import os
from google import genai
import json
import pikepdf
import tempfile
import pydantic
from enum import Enum
import time
import logging
import traceback
from typing import Optional, List

# Load environment variables (optional - dotenv not required)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Suppress httpx INFO logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)
# Suppress Google GenAI INFO logs
logging.getLogger("google_genai").setLevel(logging.WARNING)

# --- Pydantic Models Based on GHPL Glossary ---

# Import the proper enums and structured models from meta.py
from meta import (
    DocType, Creator, HealthTopic, GovernanceLevel,
    DocumentMetadata, StringFieldMetadata, IntFieldMetadata,
    DocTypeFieldMetadata, CreatorFieldMetadata, HealthTopicFieldMetadata, GovernanceLevelFieldMetadata
)

class RelevanceAssessment(pydantic.BaseModel):
    """Assessment of document relevance to GHPL scope using two boolean values."""
    is_health_policy_related: bool = pydantic.Field(description="True if document relates to health policy, healthcare, public health, or has health impacts")
    fits_ghpl_categories: bool = pydantic.Field(description="True if document fits one of the 6 GHPL categories (Policy, Law, National Health Strategy, National Control Plan, Action Plan, Guideline)")
    health_explanation: str = pydantic.Field(description="Brief explanation of why it is/isn't health policy related")
    category_explanation: str = pydantic.Field(description="Brief explanation of which GHPL category it fits (or why it doesn't fit any)")
    health_confidence: float = pydantic.Field(ge=0.0, le=1.0, description="Confidence in health policy relevance assessment")
    category_confidence: float = pydantic.Field(ge=0.0, le=1.0, description="Confidence in GHPL category fit assessment")

class GHPLMetadataField(pydantic.BaseModel):
    """Metadata field following GHPL standards."""
    value: Optional[str] = pydantic.Field(None, description="The extracted value")
    confidence: float = pydantic.Field(0.0, ge=0.0, le=1.0, description="Confidence score")
    evidence: str = pydantic.Field("", description="Evidence supporting the extraction")
    source_page: Optional[int] = pydantic.Field(None, description="Source page number")
    alternatives: Optional[List[str]] = pydantic.Field(default_factory=list, description="Alternative values considered")

class GHPLDocumentMetadata(pydantic.BaseModel):
    """Enhanced metadata following GHPL glossary definitions."""
    # Core GHPL classification
    document_type: GHPLMetadataField = pydantic.Field(description="Document type according to GHPL glossary")
    health_focus: GHPLMetadataField = pydantic.Field(description="Primary health focus or disease area")
    
    # Administrative metadata
    title: GHPLMetadataField = pydantic.Field(description="Document title")
    country: GHPLMetadataField = pydantic.Field(description="Country of origin")
    year: GHPLMetadataField = pydantic.Field(description="Publication year")
    language: GHPLMetadataField = pydantic.Field(description="Primary language")
    
    # Authority and governance
    issuing_authority: GHPLMetadataField = pydantic.Field(description="Government body that issued/endorsed the document")
    governance_level: GHPLMetadataField = pydantic.Field(description="National, Regional, or Local level")
    
    # GHPL compliance
    officially_endorsed: GHPLMetadataField = pydantic.Field(description="Whether document is officially endorsed by government")
    
    # Quality scores
    overall_confidence: Optional[float] = pydantic.Field(None, ge=0.0, le=1.0)
    metadata_completeness: Optional[float] = pydantic.Field(None, ge=0.0, le=1.0)


def upload_pdf_subset(client, pdf_path, first_pages=10, last_pages=5, max_retries=3):
    """Extract and upload a subset of PDF pages to Gemini."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file '{pdf_path}' was not found.")
    
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


def process_document_with_chat(client, first_pages_file, last_pages_file, pdf_path, max_retries=3):
    """
    Multi-turn chat conversation to assess and extract metadata from document.
    """
    model_name = 'gemini-2.5-flash'
    pdf_filename = os.path.basename(pdf_path)
    
    try:
        # Create initial chat with document context
        print(f"🔍 Starting multi-turn conversation about document: {pdf_filename}")
        
        # Create chat session
        chat = client.chats.create(model=model_name)
        
        # Send initial message with documents
        if last_pages_file:
            initial_message = f"I'm going to ask you to analyze this document: {pdf_filename}. I'm providing the first pages and last pages of the document for analysis."
            response = chat.send_message([initial_message, first_pages_file, last_pages_file])
        else:
            initial_message = f"I'm going to ask you to analyze this document: {pdf_filename}. I'm providing pages from this document for analysis."
            response = chat.send_message([initial_message, first_pages_file])
        
        print(f"📄 Document uploaded, model responded: {response.text[:100]}...")
        
        # QUESTION 1: Health policy relevance and GHPL category fit
        print("❓ Question 1: Assessing health policy relevance...")
        
        question_1 = """
        I need you to answer two separate boolean questions about this document:

        **Question A: Is this document health policy related?**
        - TRUE if: Document relates to health, healthcare, public health, or has other health policy focus.
        - Examples that DON'T qualify: purely administrative documents, financial reports, infrastructure projects.

        **Question B: Does it fit into any of the 6 GHPL document categories?**
        
        1. **Policy**: Formal government statement defining goals/priorities for societal need
        
        2. **Law**: Rules governing behavior 
           - Alternative terms: statutes, acts, decrees, regulations, bylaws, binding legal precedent
        
        3. **National Health Strategy**: Model of intended future with programme of action for health sector
           - Alternative terms: National Health Plan, National Health Strategic Plan
        
        4. **National Control Plan**: Strategic plan for disease/health problem control at national level
           - Alternative terms: National [Disease] Strategy, National [Disease] Strategic Plan, National [Disease] Programme
        
        5. **Action Plan**: Specific steps by government agencies to implement policy
        
        6. **Guideline**: Evidence-based advisory statements for health interventions
           - Alternative terms: Protocol, Best Practice, Consensus, Statement, Expert Committee, Recommendation, Integrated Care, Pathway

        **Important distinctions:**
        - A notice ABOUT a policy is NOT the policy itself
        - A research agenda is NOT a strategy unless it contains implementation plans
        - An announcement is NOT a guideline unless it contains clinical/public health recommendations
        - A research paper is typically not a health policy document unless it includes specific policy recommendations from an official entity.

        **Government endorsement requirement**: Document must likely be "adopted or otherwise officially and publicly endorsed by the government" to qualify.

        Return your assessment using the RelevanceAssessment schema.
        """
        
        response_1 = chat.send_message(question_1, config={'response_mime_type': 'application/json', 'response_schema': RelevanceAssessment})
        
        # Track token usage for Question 1
        q1_tokens = {
            'prompt_tokens': 0,
            'output_tokens': 0,
            'thinking_tokens': 0,
            'total_tokens': 0,
            'cost': 0.0
        }
        
        if hasattr(response_1, 'usage_metadata') and response_1.usage_metadata:
            usage = response_1.usage_metadata
            q1_tokens['prompt_tokens'] = getattr(usage, 'prompt_token_count', 0)
            q1_tokens['output_tokens'] = getattr(usage, 'candidates_token_count', 0)
            q1_tokens['thinking_tokens'] = getattr(usage, 'thoughts_token_count', 0)
            q1_tokens['total_tokens'] = getattr(usage, 'total_token_count', 0)
            
            # Calculate cost (Gemini 2.5 Flash pricing)
            input_cost = (q1_tokens['prompt_tokens'] / 1_000_000) * 0.30
            output_cost = ((q1_tokens['output_tokens'] + q1_tokens['thinking_tokens']) / 1_000_000) * 2.50
            q1_tokens['cost'] = input_cost + output_cost
            
            print(f"\n📊 Question 1 Token Usage:")
            print(f"  ├─ Input tokens: {q1_tokens['prompt_tokens']:,}")
            print(f"  ├─ Output tokens: {q1_tokens['output_tokens']:,}")
            if q1_tokens['thinking_tokens'] > 0:
                print(f"  ├─ Thinking tokens: {q1_tokens['thinking_tokens']:,}")
            print(f"  ├─ Total tokens: {q1_tokens['total_tokens']:,}")
            print(f"  └─ Cost: ${q1_tokens['cost']:.6f}")
        
        # Parse structured response
        try:
            assessment = RelevanceAssessment.model_validate_json(response_1.text)
            
            print("🔍 Response to Question 1:")
            print(f"  ├─ Health Policy Related: {'✅ YES' if assessment.is_health_policy_related else '❌ NO'}")
            print(f"  │  └─ {assessment.health_explanation} (confidence: {assessment.health_confidence:.2f})")
            print(f"  ├─ Fits GHPL Categories: {'✅ YES' if assessment.fits_ghpl_categories else '❌ NO'}")
            print(f"  │  └─ {assessment.category_explanation} (confidence: {assessment.category_confidence:.2f})")
            
            # Both must be TRUE to proceed
            if not assessment.is_health_policy_related or not assessment.fits_ghpl_categories:
                print("\n" + "=" * 60)
                print("🚫 DOCUMENT NOT SUITABLE FOR GHPL PROCESSING")
                print("=" * 60)
                if not assessment.is_health_policy_related:
                    print("Reason: Not health policy related")
                elif not assessment.fits_ghpl_categories:
                    print("Reason: Health policy related but doesn't fit GHPL categories")
                print("No metadata extraction will be performed.")
                return None, f"Health related: {assessment.is_health_policy_related}, GHPL category fit: {assessment.fits_ghpl_categories}"
                
        except Exception as e:
            print(f"❌ Failed to parse structured response: {e}")
            print(f"Raw response: {response_1.text}")
            return None, response_1.text
        
        # QUESTION 2: Extract detailed metadata
        print("\n❓ Question 2: Extracting detailed metadata...")
        
        question_2 = f"""
        Great! Since this document is health policy related and fits GHPL categories, please extract detailed metadata using the proper enum-based structure.

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
        - "Global"
        
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
        
        response_2 = chat.send_message(question_2, config={
            'response_mime_type': 'application/json',
            'response_schema': DocumentMetadata,
            'temperature': 0.1
        })
        
        # Track token usage for Question 2
        q2_tokens = {
            'prompt_tokens': 0,
            'output_tokens': 0,
            'thinking_tokens': 0,
            'total_tokens': 0,
            'cost': 0.0
        }
        
        if hasattr(response_2, 'usage_metadata') and response_2.usage_metadata:
            usage = response_2.usage_metadata
            q2_tokens['prompt_tokens'] = getattr(usage, 'prompt_token_count', 0)
            q2_tokens['output_tokens'] = getattr(usage, 'candidates_token_count', 0)
            q2_tokens['thinking_tokens'] = getattr(usage, 'thoughts_token_count', 0)
            q2_tokens['total_tokens'] = getattr(usage, 'total_token_count', 0)
            
            # Calculate cost (Gemini 2.5 Flash pricing)
            input_cost = (q2_tokens['prompt_tokens'] / 1_000_000) * 0.30
            output_cost = ((q2_tokens['output_tokens'] + q2_tokens['thinking_tokens']) / 1_000_000) * 2.50
            q2_tokens['cost'] = input_cost + output_cost
            
            print(f"\n📊 Question 2 Token Usage:")
            print(f"  ├─ Input tokens: {q2_tokens['prompt_tokens']:,}")
            print(f"  ├─ Output tokens: {q2_tokens['output_tokens']:,}")
            if q2_tokens['thinking_tokens'] > 0:
                print(f"  ├─ Thinking tokens: {q2_tokens['thinking_tokens']:,}")
            print(f"  ├─ Total tokens: {q2_tokens['total_tokens']:,}")
            print(f"  └─ Cost: ${q2_tokens['cost']:.6f}")
        
        # Calculate and display combined totals
        combined_tokens = {
            'prompt_tokens': q1_tokens['prompt_tokens'] + q2_tokens['prompt_tokens'],
            'output_tokens': q1_tokens['output_tokens'] + q2_tokens['output_tokens'],
            'thinking_tokens': q1_tokens['thinking_tokens'] + q2_tokens['thinking_tokens'],
            'total_tokens': q1_tokens['total_tokens'] + q2_tokens['total_tokens'],
            'cost': q1_tokens['cost'] + q2_tokens['cost']
        }
        
        print(f"\n📊 Combined Total Usage:")
        print(f"  ├─ Input tokens: {combined_tokens['prompt_tokens']:,}")
        print(f"  ├─ Output tokens: {combined_tokens['output_tokens']:,}")
        if combined_tokens['thinking_tokens'] > 0:
            print(f"  ├─ Thinking tokens: {combined_tokens['thinking_tokens']:,}")
        print(f"  ├─ Total tokens: {combined_tokens['total_tokens']:,}")
        print(f"  ├─ Total cost: ${combined_tokens['cost']:.6f}")
        print(f"  └─ (~{combined_tokens['cost'] * 100:.2f} cents)")
        
        # Parse metadata using Pydantic model validation
        try:
            metadata = DocumentMetadata.model_validate_json(response_2.text)
            print("\n✅ Successfully extracted structured metadata")
            
            # Calculate overall scores
            from meta import calculate_overall_confidence, calculate_metadata_completeness
            metadata.overall_confidence = calculate_overall_confidence(metadata)
            metadata.metadata_completeness = calculate_metadata_completeness(metadata)
            
            return metadata, response_1.text
        except Exception as e:
            print(f"\n❌ Failed to parse structured metadata: {e}")
            print(f"Raw response: {response_2.text[:500]}...")
            return None, response_1.text
            
    except Exception as e:
        print(f"❌ Error in multi-turn conversation: {e}")
        logger.error(f"Chat processing error: {traceback.format_exc()}")
        return None, None


def calculate_overall_confidence(metadata: GHPLDocumentMetadata) -> float:
    """Calculate overall confidence for GHPL metadata."""
    # Weight different fields by importance for health policy classification
    weights = {
        'document_type': 0.30,  # Most important for GHPL classification
        'title': 0.20,
        'issuing_authority': 0.15,
        'officially_endorsed': 0.15,
        'health_focus': 0.10,
        'country': 0.05,
        'year': 0.05
    }
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for field_name, weight in weights.items():
        field = getattr(metadata, field_name)
        if field.value is not None:
            weighted_sum += field.confidence * weight
            total_weight += weight
    
    # Calculate completeness
    fields_found = sum(1 for f in weights.keys() if getattr(metadata, f).value is not None)
    completeness = fields_found / len(weights)
    
    # Overall confidence adjusted by completeness
    if total_weight > 0:
        confidence = (weighted_sum / total_weight) * (0.7 + 0.3 * completeness)
    else:
        confidence = 0.0
    
    return round(confidence, 3)


def calculate_metadata_completeness(metadata: GHPLDocumentMetadata) -> float:
    """Calculate metadata completeness for GHPL standards."""
    fields = ['document_type', 'title', 'country', 'year', 'issuing_authority', 
             'officially_endorsed', 'governance_level', 'health_focus', 'language']
    fields_found = sum(1 for f in fields if getattr(metadata, f).value is not None)
    return round(fields_found / len(fields), 3)


def display_ghpl_field(name: str, field):
    """Display a GHPL metadata field with its confidence and evidence."""
    if field.value is not None:
        print(f"{name}: {field.value}")
        print(f"  ├─ Confidence: {field.confidence:.2f}")
        if field.evidence:
            print(f"  ├─ Evidence: {field.evidence[:100]}...")
        if field.source_page:
            print(f"  ├─ Source: Page {field.source_page}")
        if field.alternatives:
            print(f"  └─ Alternatives: {', '.join(field.alternatives[:3])}")
    else:
        print(f"{name}: Not found")
        if field.evidence:
            print(f"  └─ Note: {field.evidence}")
    print()


def main():
    """Main function implementing the GHPL two-stage approach."""
    # Get API key from environment
    API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not API_KEY:
        print("❌ Please set the GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        return
    
    # Get PDF path
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "docs_correct/2017-27762.pdf"  # Default test file
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return
    
    try:
        # Initialize client
        print("🔧 Initializing Gemini client...")
        client = genai.Client(api_key=API_KEY)
        
        # Stage 1: Upload PDF subsets
        first_pages_file, last_pages_file = upload_pdf_subset(client, pdf_path)
        
        if not first_pages_file:
            print("❌ Failed to upload PDF subsets")
            return
        
        # Multi-turn chat conversation
        metadata, relevance_response = process_document_with_chat(client, first_pages_file, last_pages_file, pdf_path)
        
        if metadata:
            print("\n" + "=" * 60)
            print("📋 GHPL METADATA EXTRACTION RESULTS")
            print("=" * 60)
            print(f"Overall Confidence: {metadata.overall_confidence:.2f}")
            print(f"Metadata Completeness: {metadata.metadata_completeness:.1%}")
            print("-" * 60)
            
            # Import display function from meta.py
            from meta import display_field
            
            # Display each field using the structured display function
            display_field("Title", metadata.title)
            display_field("Document Type", metadata.doc_type)
            display_field("Health Topic", metadata.health_topic)
            display_field("Creator", metadata.creator)
            display_field("Year", metadata.year)
            display_field("Country", metadata.country)
            display_field("Language", metadata.language)
            display_field("Governance Level", metadata.level)
            
            print("-" * 60)
            
            # Recommendations based on confidence
            if metadata.overall_confidence > 0.8:
                print("✅ High confidence GHPL classification")
            elif metadata.overall_confidence > 0.6:
                print("⚠️ Medium confidence - review recommended") 
            else:
                print("❌ Low confidence - manual review required")
                
        else:
            if relevance_response:
                print("\n" + "=" * 60)
                print("📋 RELEVANCE ASSESSMENT RESPONSE")
                print("=" * 60)
                print(relevance_response)
        
        # Cleanup uploaded files
        try:
            print("\n🗑️ Cleaning up uploaded files...")
            if first_pages_file:
                client.files.delete(name=first_pages_file.name)
                print("✅ Deleted first pages file")
            if last_pages_file:
                client.files.delete(name=last_pages_file.name)
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