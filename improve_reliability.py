#!/usr/bin/env python3
"""Improvements for meta_ghpl.py reliability."""

# IMPROVEMENT 1: Add uncertainty-based flagging
def should_flag_for_review(relevance_data):
    """Flag documents with uncertain decisions for human review."""
    q1a_conf = relevance_data.get('health_confidence', 0)
    q1b_conf = relevance_data.get('category_confidence', 0)
    
    # Flag if any confidence is in the "uncertain zone" (0.7-0.9)
    if 0.7 <= q1a_conf <= 0.9 or 0.7 <= q1b_conf <= 0.9:
        return True, "Medium confidence - review recommended"
    
    # Flag if confidences disagree (one high, one low)
    if abs(q1a_conf - q1b_conf) > 0.3:
        return True, "Conflicting confidence levels"
    
    # Flag edge cases where one is true with low confidence
    q1a = relevance_data.get('is_health_policy_related', False)
    q1b = relevance_data.get('fits_ghpl_categories', False)
    
    if (q1a and q1a_conf < 0.8) or (q1b and q1b_conf < 0.8):
        return True, "Positive decision with low confidence"
    
    return False, "High confidence decision"

# IMPROVEMENT 2: Multi-pass validation for uncertain cases
def validate_with_multiple_attempts(client, pdf_path, max_attempts=3):
    """Run multiple assessment attempts for uncertain cases."""
    results = []
    
    for attempt in range(max_attempts):
        # Run assessment (simplified - would use actual process_document_with_chat)
        result = process_document_with_chat(client, first_pages, last_pages, pdf_path)
        results.append(result)
        
        # Check consistency
        if attempt > 0:
            # Compare with previous results
            if all_results_agree(results):
                return aggregate_results(results), "consistent"
    
    # If inconsistent, return aggregated result with uncertainty flag
    return aggregate_results(results), "inconsistent"

# IMPROVEMENT 3: Enhanced prompting for edge cases
EDGE_CASE_PROMPTS = {
    'educational_material': """
    For educational materials, apply these specific criteria:
    - If from government health agency AND contains official recommendations: TRUE
    - If from NGO/foundation without government endorsement: FALSE
    - Patient education from hospitals/clinics: Generally FALSE unless part of national program
    """,
    
    'assessment_report': """
    For assessment/evaluation reports:
    - If it CONTAINS the actual policy/strategy: TRUE for fits_ghpl_categories
    - If it only ANALYZES or REPORTS ON a policy: FALSE for fits_ghpl_categories
    - Input documents for future policy development: FALSE
    """,
    
    'research_paper': """
    For research papers and editorials:
    - Pure research without policy recommendations: FALSE
    - Research commissioned by government with policy recommendations: Consider TRUE
    - Editorial discussing policy implications: Generally FALSE unless from official source
    """
}

# IMPROVEMENT 4: Ensemble approach for high-stakes decisions
def ensemble_decision(client, pdf_path, models=['gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-1.5-pro']):
    """Use multiple models and take majority vote for critical decisions."""
    decisions = []
    
    for model in models:
        result = process_with_model(client, pdf_path, model)
        decisions.append(result)
    
    # Majority voting
    q1a_votes = [d['is_health_policy_related'] for d in decisions]
    q1b_votes = [d['fits_ghpl_categories'] for d in decisions]
    
    final_q1a = sum(q1a_votes) > len(q1a_votes) / 2
    final_q1b = sum(q1b_votes) > len(q1b_votes) / 2
    
    # Calculate ensemble confidence
    q1a_agreement = sum(q1a_votes) / len(q1a_votes)
    q1b_agreement = sum(q1b_votes) / len(q1b_votes)
    
    ensemble_confidence = {
        'q1a_ensemble_conf': max(q1a_agreement, 1 - q1a_agreement),
        'q1b_ensemble_conf': max(q1b_agreement, 1 - q1b_agreement),
        'model_agreement': min(q1a_agreement, q1b_agreement)
    }
    
    return final_q1a, final_q1b, ensemble_confidence

# IMPROVEMENT 5: Add explicit uncertainty categories
def categorize_uncertainty(confidence):
    """Categorize confidence into clear uncertainty levels."""
    if confidence >= 0.95:
        return "very_certain"
    elif confidence >= 0.85:
        return "certain"
    elif confidence >= 0.70:
        return "uncertain"
    elif confidence >= 0.50:
        return "very_uncertain"
    else:
        return "guess"

# IMPROVEMENT 6: Track and learn from corrections
def save_correction(filename, original_decision, corrected_decision, reason):
    """Save human corrections to improve future prompts."""
    import json
    
    correction = {
        'filename': filename,
        'original': original_decision,
        'corrected': corrected_decision,
        'reason': reason,
        'timestamp': datetime.now().isoformat()
    }
    
    # Append to corrections log
    with open('corrections_log.json', 'a') as f:
        json.dump(correction, f)
        f.write('\n')
    
    # Could be used to fine-tune prompts or identify problem patterns

# IMPROVEMENT 7: Implement retrieval-augmented generation (RAG)
def get_similar_documents(filename, metadata, previous_decisions_db):
    """Find similar previously-decided documents for consistency."""
    # Search for documents with similar:
    # - Titles (fuzzy match)
    # - Document types
    # - Issuing organizations
    # - Years (nearby)
    
    similar = []
    for prev_doc in previous_decisions_db:
        similarity = calculate_similarity(metadata, prev_doc)
        if similarity > 0.8:
            similar.append(prev_doc)
    
    return similar

def enhanced_prompt_with_examples(base_prompt, similar_docs):
    """Add examples of similar documents to improve consistency."""
    examples = "\n\nHere are similar documents and their classifications:\n"
    for doc in similar_docs[:3]:  # Top 3 most similar
        examples += f"- {doc['title']}: Q1A={doc['q1a']}, Q1B={doc['q1b']}\n"
        examples += f"  Reason: {doc['explanation']}\n"
    
    return base_prompt + examples