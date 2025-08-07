#!/usr/bin/env python3
"""
CLI tool for PDF metadata extraction with ground truth validation.
Integrates all existing functions from get_metadata.py and ground_truth_validation.py.
"""

import os
import argparse
import json
import datetime
import time
import threading
import traceback
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from google import genai
from google.genai import types
import pandas as pd
import pydantic
from urllib.parse import urlparse, unquote

def get_filename_from_url(url: str) -> str:
    """
    Extract the expected filename from a URL with proper decoding.
    This ensures consistent filename handling across the system.
    """
    parsed_url = urlparse(url)
    filename = os.path.basename(unquote(parsed_url.path))
    
    # Handle common URL encoding
    filename = filename.replace('%20', ' ')
    filename = filename.replace('%28', '(')
    filename = filename.replace('%29', ')')
    
    return filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cli_errors.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def categorize_error(error_type: str, error_message: str, error_details: Dict = None) -> Dict[str, Any]:
    """Categorize errors for better debugging and resolution with detailed error information."""
    error_msg_lower = error_message.lower()
    
    # Extract additional details if available
    http_status = None
    api_code = None
    
    if error_details:
        http_status = error_details.get('http_status') or error_details.get('status_code')
        api_code = error_details.get('api_code')
    
    # Precise categorization based on HTTP status codes
    if http_status:
        if http_status == 429:
            return {
                'category': 'rate_limit',
                'severity': 'medium',
                'retryable': True,
                'suggestion': 'Rate limit exceeded. Reduce worker count or add delays',
                'http_status': http_status,
                'confidence': 'high'
            }
        elif http_status in [401, 403]:
            return {
                'category': 'authentication', 
                'severity': 'high',
                'retryable': False,
                'suggestion': 'Authentication failed. Check API key and permissions',
                'http_status': http_status,
                'confidence': 'high'
            }
        elif http_status in [503, 502, 504]:
            return {
                'category': 'service_unavailable',
                'severity': 'medium',
                'retryable': True, 
                'suggestion': 'Service temporarily unavailable. Retry should resolve',
                'http_status': http_status,
                'confidence': 'high'
            }
        elif http_status >= 500:
            return {
                'category': 'server_error',
                'severity': 'medium',
                'retryable': True,
                'suggestion': 'Server error occurred. Retry recommended',
                'http_status': http_status,
                'confidence': 'high'
            }
        elif http_status in [400, 422]:
            return {
                'category': 'client_error',
                'severity': 'high',
                'retryable': False,
                'suggestion': 'Request format error. Check input data',
                'http_status': http_status,
                'confidence': 'high'
            }
    
    # Fallback to string-based detection with lower confidence
    
    # API-related errors (fallback detection)
    if any(keyword in error_msg_lower for keyword in ['rate limit', '429', 'quota', 'limit exceeded']):
        return {
            'category': 'rate_limit',
            'severity': 'medium',
            'retryable': True,
            'suggestion': 'Reduce worker count or increase delays between requests',
            'confidence': 'medium'
        }
    
    if any(keyword in error_msg_lower for keyword in ['503', 'service unavailable', 'timeout', 'connection']):
        return {
            'category': 'service_unavailable',
            'severity': 'medium', 
            'retryable': True,
            'suggestion': 'Temporary service issue, retry should resolve',
            'confidence': 'medium'
        }
    
    if any(keyword in error_msg_lower for keyword in ['authentication', 'unauthorized', '401', 'api key']):
        return {
            'category': 'authentication',
            'severity': 'high',
            'retryable': False,
            'suggestion': 'Check API key configuration',
            'confidence': 'medium'
        }
    
    # File-related errors
    if error_type == 'FileNotFoundError' or 'not found' in error_msg_lower:
        return {
            'category': 'file_not_found',
            'severity': 'high',
            'retryable': False,
            'suggestion': 'Verify file paths and ensure files exist'
        }
    
    if any(keyword in error_msg_lower for keyword in ['permission', 'access denied']):
        return {
            'category': 'permission_error',
            'severity': 'high',
            'retryable': False,
            'suggestion': 'Check file permissions and disk space'
        }
    
    # PDF processing errors
    if any(keyword in error_msg_lower for keyword in ['pdf', 'pikepdf', 'corrupt', 'invalid format']):
        return {
            'category': 'pdf_processing',
            'severity': 'medium',
            'retryable': True,
            'suggestion': 'PDF may be corrupted - check file integrity'
        }
    
    # Parsing errors
    if any(keyword in error_msg_lower for keyword in ['json', 'validation', 'pydantic']):
        return {
            'category': 'parsing_error',
            'severity': 'medium',
            'retryable': True,
            'suggestion': 'Response format issue - may resolve with retry'
        }
    
    # Memory/resource errors
    if any(keyword in error_msg_lower for keyword in ['memory', 'out of memory', 'resource']):
        return {
            'category': 'resource_exhaustion',
            'severity': 'high',
            'retryable': False,
            'suggestion': 'Reduce batch size or worker count'
        }
    
    # Unknown error
    return {
        'category': 'unknown',
        'severity': 'medium',
        'retryable': True,
        'suggestion': 'Check logs for more details',
        'confidence': 'low'
    }

def generate_failure_analysis(failed_items: List[Dict], verbose: bool = False) -> None:
    """Generate comprehensive failure analysis with actionable recommendations."""
    if not failed_items:
        return
    
    logger.info("Generating failure analysis...")
    print(f"\n📊 FAILURE ANALYSIS")
    print(f"{'='*50}")
    
    # Categorize all failures
    error_categories = {}
    error_suggestions = set()
    
    for failure in failed_items:
        if isinstance(failure, dict):
            error_type = failure.get('error', failure.get('error_type', 'Unknown'))
            error_msg = failure.get('error_message', str(failure))
            # Extract detailed error info if available
            detailed_info = failure.get('detailed_error_info', {})
        else:
            error_type = 'Unknown'
            error_msg = str(failure)
            detailed_info = {}
        
        category_info = categorize_error(error_type, error_msg, detailed_info)
        category = category_info['category']
        
        if category not in error_categories:
            error_categories[category] = {
                'count': 0,
                'examples': [],
                'info': category_info
            }
        
        error_categories[category]['count'] += 1
        if len(error_categories[category]['examples']) < 3:
            filename = failure.get('filename', 'unknown') if isinstance(failure, dict) else 'unknown'
            
            # Enhanced example with HTTP status if available
            error_display = f"{error_type}: {error_msg[:100]}..."
            if detailed_info.get('http_status'):
                error_display = f"HTTP {detailed_info['http_status']}: {error_display}"
            
            error_categories[category]['examples'].append({
                'filename': filename,
                'error': error_display,
                'http_status': detailed_info.get('http_status'),
                'confidence': category_info.get('confidence', 'unknown')
            })
        
        error_suggestions.add(category_info['suggestion'])
    
    print(f"Total failed files: {len(failed_items)}")
    print(f"Error categories found: {len(error_categories)}")
    
    # Display categories by frequency
    sorted_categories = sorted(error_categories.items(), key=lambda x: x[1]['count'], reverse=True)
    
    print(f"\n🔍 ERROR BREAKDOWN")
    print(f"{'-'*50}")
    
    for category, data in sorted_categories:
        count = data['count']
        percentage = (count / len(failed_items)) * 100
        severity = data['info']['severity']
        retryable = data['info']['retryable']
        
        severity_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}[severity]
        retry_emoji = '🔄' if retryable else '⛔'
        confidence = data['info'].get('confidence', 'unknown')
        confidence_emoji = {'high': '🎯', 'medium': '🔍', 'low': '❓', 'unknown': '❓'}[confidence]
        
        print(f"{severity_emoji} {category.replace('_', ' ').title()}: {count} ({percentage:.1f}%) {retry_emoji} {confidence_emoji}")
        
        if verbose and data['examples']:
            for example in data['examples']:
                status_info = f" [HTTP {example['http_status']}]" if example.get('http_status') else ""
                confidence_info = f" (confidence: {example.get('confidence', 'unknown')})"
                print(f"    • {example['filename']}: {example['error']}{status_info}{confidence_info}")
    
    print(f"\n💡 RECOMMENDED ACTIONS")
    print(f"{'-'*50}")
    
    for i, suggestion in enumerate(error_suggestions, 1):
        print(f"{i}. {suggestion}")
    
    # Specific retry recommendations
    retryable_count = sum(data['count'] for data in error_categories.values() if data['info']['retryable'])
    if retryable_count > 0:
        print(f"\n🔄 RETRY RECOMMENDATION")
        print(f"{'-'*30}")
        print(f"{retryable_count} of {len(failed_items)} failures appear retryable.")
        print(f"Consider running: python cli.py --batch --retry-failed --max-retries 5")
    
    # Save detailed report to file
    try:
        report_file = f"failure_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': datetime.datetime.now().isoformat(),
                'total_failures': len(failed_items),
                'categories': error_categories,
                'suggestions': list(error_suggestions),
                'retryable_count': retryable_count,
                'analysis_version': '2.0',
                'features': ['http_status_detection', 'confidence_scoring', 'detailed_error_capture']
            }, f, indent=2)
        print(f"\n📄 Detailed analysis saved to: {report_file}")
    except Exception as e:
        logger.error(f"Failed to save failure analysis: {e}")

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

# Rate limiting classes for Gemini API
@dataclass
class RateLimiter:
    """Thread-safe rate limiter for API calls."""
    max_requests_per_minute: int
    _requests: List[float] = None
    _lock: threading.Lock = None
    
    def __post_init__(self):
        self._requests = []
        self._lock = threading.Lock()
    
    def wait_if_needed(self) -> float:
        """Wait if we're approaching rate limit. Returns wait time in seconds."""
        with self._lock:
            now = time.time()
            
            # Remove requests older than 1 minute
            cutoff = now - 60.0
            self._requests = [req_time for req_time in self._requests if req_time > cutoff]
            
            # Check if we need to wait
            if len(self._requests) >= self.max_requests_per_minute:
                # Calculate wait time until oldest request is > 1 minute old
                oldest_request = min(self._requests)
                wait_time = 60.0 - (now - oldest_request) + 0.1  # Add small buffer
                if wait_time > 0:
                    return wait_time
            
            # Record this request
            self._requests.append(now)
            return 0.0
    
    def get_current_rate(self) -> float:
        """Get current requests per minute."""
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            recent_requests = [req_time for req_time in self._requests if req_time > cutoff]
            return len(recent_requests)

@dataclass
class SearchQuotaTracker:
    """Track daily search quota usage."""
    max_searches_per_day: int
    quota_file: str = "search_quota.json"
    _searches_today: int = 0
    _date_today: str = ""
    _lock: threading.Lock = None
    
    def __post_init__(self):
        self._lock = threading.Lock()
        self._load_quota()
    
    def _load_quota(self):
        """Load today's quota usage from file."""
        today = datetime.date.today().isoformat()
        
        if os.path.exists(self.quota_file):
            try:
                with open(self.quota_file, 'r') as f:
                    data = json.load(f)
                    if data.get('date') == today:
                        self._searches_today = data.get('count', 0)
                        self._date_today = today
                        return
            except:
                pass
        
        # Reset for new day
        self._searches_today = 0
        self._date_today = today
        self._save_quota()
    
    def _save_quota(self):
        """Save quota to file."""
        try:
            data = {
                'date': self._date_today,
                'count': self._searches_today,
                'max_searches': self.max_searches_per_day
            }
            with open(self.quota_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Warning: Could not save search quota to file: {e}")
            # Continue anyway - don't let file I/O block the search
    
    def can_use_search(self) -> bool:
        """Check if we can use search quota."""
        # NOTE: This method should only be called from within use_search_quota() which already holds the lock
        today = datetime.date.today().isoformat()
        if today != self._date_today:
            self._load_quota()  # Reload for new day
        
        return self._searches_today < self.max_searches_per_day
    
    def use_search_quota(self) -> bool:
        """Use one search quota. Returns True if successful, False if quota exhausted."""
        with self._lock:
            if self.can_use_search():
                self._searches_today += 1
                self._save_quota()
                return True
            return False
    
    def get_quota_status(self) -> Dict[str, Any]:
        """Get current quota status."""
        with self._lock:
            return {
                'used': self._searches_today,
                'max': self.max_searches_per_day,
                'remaining': self.max_searches_per_day - self._searches_today,
                'date': self._date_today
            }

# Global rate limiters (initialized in main)
GEMINI_RATE_LIMITER = None
SEARCH_QUOTA_TRACKER = None

def calculate_optimal_workers(rate_limiter: RateLimiter, base_workers: int, max_workers: int = 20) -> int:
    """Calculate optimal number of workers based on current rate limit utilization."""
    if not rate_limiter:
        return base_workers
    
    current_rate = rate_limiter.get_current_rate()
    max_rate = rate_limiter.max_requests_per_minute
    utilization = current_rate / max_rate
    
    # Conservative scaling:
    # - If utilization < 50%, can scale up to 150% of base workers
    # - If utilization < 25%, can scale up to 200% of base workers  
    # - If utilization > 75%, scale down to 75% of base workers
    # - If utilization > 90%, scale down to 50% of base workers
    
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

def wait_for_rate_limit(limiter: RateLimiter, operation: str = "API call") -> None:
    """Wait for rate limiter and show progress."""
    wait_time = limiter.wait_if_needed()
    if wait_time > 0:
        current_rate = limiter.get_current_rate()
        print(f"⏳ Rate limiting: {current_rate}/140 RPM - waiting {wait_time:.1f}s for {operation}...")
        time.sleep(wait_time)
        print(f"✅ Rate limit wait complete, proceeding with {operation}")

# Batch processing state management
@dataclass
class BatchProgress:
    """Track batch processing progress and state."""
    total_files: int
    completed: List[str]
    failed: List[Dict[str, Any]]
    pending: List[str]
    start_time: str
    last_checkpoint: str
    # Export file paths for resume continuity
    export_results_path: Optional[str] = None
    export_deviations_path: Optional[str] = None
    export_ground_truth_path: Optional[str] = None
    
    def save_to_file(self, filepath: str):
        """Save progress to JSON file."""
        data = {
            'total_files': self.total_files,
            'completed': self.completed,
            'failed': self.failed,
            'pending': self.pending,
            'start_time': self.start_time,
            'last_checkpoint': self.last_checkpoint,
            'completion_rate': len(self.completed) / self.total_files if self.total_files > 0 else 0.0,
            # Export paths for resume continuity
            'export_results_path': self.export_results_path,
            'export_deviations_path': self.export_deviations_path,
            'export_ground_truth_path': self.export_ground_truth_path
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> Optional['BatchProgress']:
        """Load progress from JSON file."""
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return cls(
                total_files=data['total_files'],
                completed=data['completed'],
                failed=data['failed'],
                pending=data['pending'],
                start_time=data['start_time'],
                last_checkpoint=data['last_checkpoint'],
                # Load export paths (with backwards compatibility)
                export_results_path=data.get('export_results_path'),
                export_deviations_path=data.get('export_deviations_path'),
                export_ground_truth_path=data.get('export_ground_truth_path')
            )
        except Exception as e:
            print(f"Warning: Could not load progress file {filepath}: {e}")
            return None

class BatchResults:
    """Thread-safe collector for batch processing results."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.results = []
        self.deviation_log = []
        self.summary_stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'avg_confidence': 0.0,
            'avg_accuracy': 0.0,
            'total_discrepancies': 0,
            'search_resolutions': 0
        }
    
    def add_result(self, pdf_path: str, result_data: Dict[str, Any]):
        """Thread-safe method to add processing result."""
        with self._lock:
            self.results.append({
                'pdf_path': pdf_path,
                'filename': Path(pdf_path).name,
                'timestamp': datetime.datetime.now().isoformat(),
                **result_data
            })
            
            # Update summary statistics
            self.summary_stats['total_processed'] += 1
            if result_data.get('metadata'):
                self.summary_stats['successful'] += 1
                metadata = result_data['metadata']
                if hasattr(metadata, 'overall_confidence') and metadata.overall_confidence:
                    self.summary_stats['avg_confidence'] += metadata.overall_confidence
                
                comparison_results = result_data.get('comparison_results', {})
                if comparison_results.get('overall_accuracy'):
                    self.summary_stats['avg_accuracy'] += comparison_results['overall_accuracy']
                
                discrepancies = comparison_results.get('discrepancies', {})
                self.summary_stats['total_discrepancies'] += len(discrepancies)
                
                if result_data.get('search_resolution_results', {}).get('resolved'):
                    self.summary_stats['search_resolutions'] += len(result_data['search_resolution_results']['resolved'])
            else:
                self.summary_stats['failed'] += 1
            
            # Add deviation entry if available
            if result_data.get('deviation_entry', {}).get('status') != 'no_tracking':
                self.deviation_log.append(result_data['deviation_entry'])
    
    def get_summary(self) -> Dict[str, Any]:
        """Get current summary statistics."""
        with self._lock:
            stats = self.summary_stats.copy()
            if stats['successful'] > 0:
                stats['avg_confidence'] /= stats['successful']
                stats['avg_accuracy'] /= stats['successful']
            return stats
    
    def export_results(self, output_path: str, append_mode: bool = False):
        """Export all results to Excel file.
        
        Args:
            output_path: Path to Excel file
            append_mode: If True, append to existing file instead of overwriting
        """
        with self._lock:
            if not self.results:
                print("No results to export")
                return None
            
            # Prepare data for export
            export_data = []
            for result in self.results:
                metadata = result.get('metadata')
                comparison = result.get('comparison_results') or {}
                search_results = result.get('search_resolution_results') or {}
                
                discrepancies = comparison.get('discrepancies') or {}
                
                row = {
                    'filename': result['filename'],
                    'pdf_path': result['pdf_path'],
                    'timestamp': result['timestamp'],
                    'success': metadata is not None,
                    'overall_confidence': metadata.overall_confidence if metadata else None,
                    'metadata_completeness': metadata.metadata_completeness if metadata else None,
                    'ground_truth_accuracy': comparison.get('overall_accuracy'),
                    'discrepancies_count': len(discrepancies),
                    'search_resolutions': len(search_results.get('resolved') or {}),
                    'search_resolution_rate': search_results.get('resolution_rate', 0.0) if search_results else 0.0,
                }
                
                # Add error information for failed files
                if not metadata:
                    row['error_type'] = result.get('error_type', '')
                    row['error_message'] = result.get('error_message', '')[:500]  # Truncate long error messages
                
                # Add metadata fields if available, including search resolution info
                if metadata:
                    for field_name in ['title', 'doc_type', 'health_topic', 'creator', 'year', 'country', 'language', 'level']:
                        field = getattr(metadata, field_name, None)
                        if field and hasattr(field, 'value'):
                            value = field.value.value if hasattr(field.value, 'value') else field.value
                            row[f'{field_name}_extracted'] = value
                            row[f'{field_name}_confidence'] = field.confidence
                            
                            # Add ground truth value and detailed info ONLY for conflicting fields
                            if field_name in discrepancies:
                                discrepancy = discrepancies[field_name]
                                row[f'{field_name}_ground_truth'] = discrepancy.get('reference', '')
                                row[f'{field_name}_evidence'] = field.evidence[:200] if field.evidence else ''  # Truncate
                                row[f'{field_name}_source_page'] = field.source_page
                            
                            # Add search resolution info if this field was resolved
                            if search_results and search_results.get('resolved') and field_name in search_results['resolved']:
                                resolution = search_results['resolved'][field_name]
                                row[f'{field_name}_search_resolved'] = resolution.get('resolved_value', '')
                                row[f'{field_name}_search_confidence'] = resolution.get('confidence', 0.0)
                                row[f'{field_name}_search_recommendation'] = resolution.get('recommendation', '')
                                row[f'{field_name}_resolution_reason'] = resolution.get('reasoning', '')[:200]  # Truncate long reasons
                
                export_data.append(row)
            
            # Create DataFrame with new data
            new_df = pd.DataFrame(export_data)
            
            if append_mode and os.path.exists(output_path):
                # Append mode - load existing data and combine
                try:
                    existing_df = pd.read_excel(output_path)
                    # Combine DataFrames, avoiding duplicates based on filename + timestamp
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    # Remove duplicates based on filename and timestamp
                    combined_df = combined_df.drop_duplicates(subset=['filename', 'timestamp'], keep='last')
                    combined_df.to_excel(output_path, index=False)
                    print(f"Batch results appended to existing file: {output_path}")
                    print(f"   • Previous entries: {len(existing_df)}")
                    print(f"   • New entries: {len(new_df)}")  
                    print(f"   • Total entries: {len(combined_df)}")
                except Exception as e:
                    print(f"Warning: Could not append to existing file, overwriting: {e}")
                    new_df.to_excel(output_path, index=False)
                    print(f"Batch results exported to: {output_path}")
            else:
                # Normal mode - overwrite file
                new_df.to_excel(output_path, index=False)
                print(f"Batch results exported to: {output_path}")
            
            return output_path
    
    def export_updated_ground_truth(self, output_path: str, ground_truth_path: str = "documents-info.xlsx"):
        """Export results in the exact format of documents-info.xlsx with updated values."""
        with self._lock:
            if not self.results:
                print("No results to export")
                return None
            
            # Load the original ground truth Excel file
            try:
                original_df = pd.read_excel(ground_truth_path)
                print(f"Loaded ground truth file with {len(original_df)} rows")
            except Exception as e:
                print(f"Error loading ground truth file: {e}")
                return None
            
            # Create a copy to update
            updated_df = original_df.copy()
            
            # Add new columns for tracking changes
            updated_df['flagged_for_review'] = False
            updated_df['updated'] = False
            updated_df['updated_fields'] = ''
            updated_df['flagged_fields'] = ''
            
            # Create lookup dict from results by filename
            results_by_filename = {}
            for result in self.results:
                # Extract just the filename without path
                filename = Path(result['filename']).name
                results_by_filename[filename] = result
            
            # Update each row with extracted/resolved values
            for idx, row in updated_df.iterrows():
                # Try to match by URL filename (handle docx→pdf conversions)
                if pd.notna(row['public_file_url']):
                    url_filename = get_filename_from_url(row['public_file_url'])
                    url_stem = Path(url_filename).stem
                    
                    # First try exact match
                    matched_filename = None
                    if url_filename in results_by_filename:
                        matched_filename = url_filename
                    else:
                        # Try stem match (for docx→pdf conversions)
                        for result_filename in results_by_filename.keys():
                            if Path(result_filename).stem == url_stem:
                                matched_filename = result_filename
                                break
                    
                    if matched_filename:
                        result = results_by_filename[matched_filename]
                        metadata = result.get('metadata')
                        comparison = result.get('comparison_results') or {}
                        search_results = result.get('search_resolution_results') or {}
                        discrepancies = comparison.get('discrepancies') or {}
                        
                        if metadata:
                            # Update fields with extracted or search-resolved values
                            fields_to_update = {
                                'doc_type': metadata.doc_type,
                                'health_topic': metadata.health_topic,
                                'creator': metadata.creator,
                                'year': metadata.year,
                                'country': metadata.country,
                                'language': metadata.language,
                                'title': metadata.title
                            }
                            
                            flagged = False
                            updated = False
                            updated_fields = []
                            flagged_fields = []
                            
                            for field_name, field in fields_to_update.items():
                                if field and hasattr(field, 'value'):
                                    # Get original value from Excel for comparison
                                    original_value = row.get(field_name)
                                    
                                    # Check if this field was resolved by search
                                    if search_results and search_results.get('resolved') and field_name in search_results['resolved']:
                                        resolution = search_results['resolved'][field_name]
                                        # Use search-resolved value if confidence is high
                                        if resolution.get('confidence', 0) >= 0.8:
                                            value = resolution.get('resolved_value')
                                            if value:
                                                # Handle year as integer
                                                if field_name == 'year':
                                                    try:
                                                        new_value = int(value)
                                                    except:
                                                        new_value = value
                                                else:
                                                    # Handle enum values
                                                    new_value = value.value if hasattr(value, 'value') else str(value)
                                                
                                                # Check if value actually changed
                                                if str(original_value) != str(new_value):
                                                    updated_df.at[idx, field_name] = new_value
                                                    updated = True
                                                    updated_fields.append(field_name)
                                        else:
                                            # Flag for review if search confidence is low
                                            flagged = True
                                            flagged_fields.append(field_name)
                                    elif field_name not in discrepancies:
                                        # Use extracted value if it matches ground truth or no ground truth exists
                                        value = field.value.value if hasattr(field.value, 'value') else field.value
                                        if value:
                                            # Handle year as integer
                                            if field_name == 'year':
                                                try:
                                                    new_value = int(value)
                                                except:
                                                    new_value = value
                                            else:
                                                # Handle enum values
                                                new_value = value.value if hasattr(value, 'value') else str(value)
                                            
                                            # Check if value actually changed
                                            if str(original_value) != str(new_value):
                                                updated_df.at[idx, field_name] = new_value
                                                updated = True
                                                updated_fields.append(field_name)
                                    else:
                                        # Field has unresolved discrepancy
                                        flagged = True
                                        flagged_fields.append(field_name)
                            
                            # Set flags and field lists
                            updated_df.at[idx, 'flagged_for_review'] = flagged
                            updated_df.at[idx, 'updated'] = updated
                            updated_df.at[idx, 'updated_fields'] = ', '.join(updated_fields) if updated_fields else ''
                            updated_df.at[idx, 'flagged_fields'] = ', '.join(flagged_fields) if flagged_fields else ''
            
            # Save the updated Excel file
            updated_df.to_excel(output_path, index=False)
            
            # Count statistics
            total_processed = sum(1 for f in results_by_filename.keys() if f in [Path(u).name for u in updated_df['public_file_url'].dropna()])
            flagged_count = updated_df['flagged_for_review'].sum()
            updated_count = updated_df['updated'].sum()
            
            print(f"\n📊 Ground truth format export complete:")
            print(f"  • Original rows: {len(original_df)}")
            print(f"  • Files processed: {total_processed}")
            print(f"  • Rows with updates: {updated_count}")
            print(f"  • Flagged for review: {flagged_count}")
            print(f"  • Output saved to: {output_path}")
            
            return output_path

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
            print("Model: gemini-2.5-flash")
            print("Search tool: Google Search grounding enabled")
        
        # Check and consume search quota before proceeding
        global SEARCH_QUOTA_TRACKER
        if SEARCH_QUOTA_TRACKER:
            try:
                quota_available = SEARCH_QUOTA_TRACKER.use_search_quota()
            except Exception as e:
                print(f"❌ ERROR in search quota tracking: {e}")
                return {
                    "resolutions": {},
                    "search_evidence": f"Error accessing search quota: {e}",
                    "sources": [],
                    "overall_confidence": 0.0
                }
            
            if not quota_available:
                quota_status = SEARCH_QUOTA_TRACKER.get_quota_status()
                print(f"❌ Search quota exhausted: {quota_status['used']}/{quota_status['max']} searches used today")
                return {
                    "resolutions": {},
                    "search_evidence": "Search quota exhausted for today",
                    "sources": [],
                    "overall_confidence": 0.0
                }
            else:
                quota_status = SEARCH_QUOTA_TRACKER.get_quota_status()
                print(f"🔍 Using search quota: {quota_status['used']}/{quota_status['max']} searches used today")
        else:
            print("⚠️  WARNING: SEARCH_QUOTA_TRACKER not initialized - proceeding without quota tracking")
        
        # Apply rate limiting for search grounding
        global GEMINI_RATE_LIMITER
        if GEMINI_RATE_LIMITER:
            current_rate = GEMINI_RATE_LIMITER.get_current_rate()
            if verbose and current_rate > 100:  # Show when approaching limit
                print(f"⚡ Current API rate: {current_rate}/140 RPM ({current_rate/140:.1%})")
            wait_for_rate_limit(GEMINI_RATE_LIMITER, "search grounding")
        
        # Configure Google Search grounding tool (correct syntax per docs)
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        print(f"🔍 Sending search grounding request to Gemini...")
        start_time = time.time()
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[analysis_prompt],
            config=types.GenerateContentConfig(
                tools=[grounding_tool]  # Enable search grounding
                # Note: response_mime_type='application/json' is incompatible with tools
            )
        )
        
        elapsed_time = time.time() - start_time
        print(f"✅ Search grounding completed in {elapsed_time:.1f}s")
        
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
            if hasattr(field, 'alternatives') and field.alternatives is not None:
                field.alternatives.extend([str(field.value), resolution.get("reference_value", "")])
            elif hasattr(field, 'alternatives'):
                # Initialize alternatives list if it's None
                field.alternatives = [str(field.value), resolution.get("reference_value", "")]
            
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
                               search_threshold: float = 0.8, rate_limiter=None, search_quota_tracker=None,
                               max_retries: int = 3):
    """Process a single PDF with validation and optional interactive resolution."""
    print(f"\nProcessing: {Path(pdf_path).name}")
    print("="*50)
    
    # Initialize client
    g_client = genai.Client(api_key=api_key)
    
    # Extract metadata using existing function with retry logic
    first_pages, last_pages = prepare_and_upload_pdf_subset(g_client, pdf_path, max_retries=max_retries)
    if not first_pages:
        print("Failed to prepare PDF subsets")
        return None
    
    metadata = get_metadata_from_gemini(g_client, first_pages, last_pages, rate_limiter, max_retries)
    if not metadata:
        print("Failed to extract metadata")
        return None
    
    # Compare with ground truth
    comparison_results = compare_with_ground_truth(metadata, ground_truth, pdf_path)
    
    # Initialize tracking variables
    user_decisions = []
    unresolved_items = []
    search_resolution_results = {"resolved": {}, "remaining": {}, "resolution_rate": 0.0}
    
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
        filename_tried = comparison_results.get('filename_tried', [])
        actual_filename = Path(pdf_path).name
        print(f"⚠️  No ground truth match found for: {actual_filename}")
        if filename_tried:
            print(f"   Tried variants: {filename_tried}")
    
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

def process_single_pdf_batch(pdf_path: str, ground_truth: dict, api_key: str, 
                            progress: BatchProgress, results_collector: BatchResults,
                            enable_search: bool = False, search_threshold: float = 0.8,
                            verbose: bool = False, rate_limiter=None, search_quota_tracker=None,
                            max_retries: int = 3) -> bool:
    """Process a single PDF in batch mode with error handling, retry logic, and progress tracking."""
    filename = Path(pdf_path).name
    thread_name = threading.current_thread().name
    
    # Retry logic with exponential backoff
    retry_count = 0
    last_error = None
    
    while retry_count <= max_retries:
        try:
            if retry_count > 0:
                # Exponential backoff: 2^retry * 2 seconds (2s, 4s, 8s, 16s...)
                backoff_time = (2 ** retry_count) * 2
                logger.info(f"[{thread_name}] Retry {retry_count}/{max_retries} for {filename} after {backoff_time}s")
                if verbose:
                    print(f"[{thread_name}] 🔄 Retry {retry_count}/{max_retries} for {filename} after {backoff_time}s backoff")
                time.sleep(backoff_time)
            
            if verbose:
                print(f"\n[{thread_name}] Processing: {filename} (attempt {retry_count + 1}/{max_retries + 1})")
            
            # Check if file exists
            if not os.path.exists(pdf_path):
                error_data = {
                    'error_type': 'file_not_found', 
                    'error_message': f"File not found: {pdf_path}",
                    'metadata': None,
                    'comparison_results': {},
                    'deviation_entry': {'status': 'error'},
                    'user_decisions': [],
                    'unresolved_items': [],
                    'search_resolution_results': None,
                    'retry_count': retry_count,
                    'stacktrace': None,
                    'detailed_error_info': {
                        'error_type': 'FileNotFoundError',
                        'file_path': pdf_path,
                        'operation': 'file_access'
                    }
                }
                logger.error(f"[{thread_name}] File not found: {pdf_path}")
                results_collector.add_result(pdf_path, error_data)
                return False  # Don't retry for file not found
            
            # Process PDF (non-interactive mode for batch processing)
            result = process_pdf_with_validation(
                pdf_path, ground_truth, api_key, 
                interactive_mode="none", 
                enable_search=enable_search, 
                search_threshold=search_threshold,
                rate_limiter=rate_limiter,
                search_quota_tracker=search_quota_tracker,
                max_retries=max_retries
            )
            
            if result:
                # Add retry count to successful result
                result['retry_count'] = retry_count
                results_collector.add_result(pdf_path, result)
                
                if verbose:
                    metadata = result['metadata']
                    confidence = metadata.overall_confidence if metadata else 0.0
                    comparison_results = result.get('comparison_results', {})
                    accuracy = comparison_results.get('overall_accuracy', 0.0) if comparison_results else 0.0
                    
                    success_msg = f"[{thread_name}] ✅ {filename}: confidence={confidence:.2f}, accuracy={accuracy:.2f}"
                    if retry_count > 0:
                        success_msg += f" (succeeded after {retry_count} retries)"
                    print(success_msg)
                    logger.info(success_msg)
                    
                    # Print discrepancies if any
                    if comparison_results and comparison_results.get('discrepancies'):
                        discrepancies = comparison_results['discrepancies']
                        print(f"[{thread_name}] 🔍 Found {len(discrepancies)} discrepancies:")
                        for field, details in discrepancies.items():
                            extracted = details.get('extracted', 'N/A')
                            reference = details.get('reference', 'N/A')
                            print(f"[{thread_name}]   • {field}: '{extracted}' ≠ '{reference}'")
                    else:
                        print(f"[{thread_name}] ✨ No discrepancies found")
                return True
            else:
                # Result was None, will retry
                raise Exception("PDF processing returned no result")
                
        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            error_msg = str(e)
            full_traceback = traceback.format_exc()
            
            # Log detailed error information
            logger.error(f"[{thread_name}] Error processing {filename} (attempt {retry_count + 1}/{max_retries + 1}): {error_type}: {error_msg}")
            logger.debug(f"[{thread_name}] Full traceback:\n{full_traceback}")
            
            if verbose:
                print(f"[{thread_name}] ❌ {filename}: {error_type}: {error_msg}")
                if retry_count == 0:  # Only print full traceback on first failure
                    print(f"Full traceback:\n{full_traceback}")
            
            # Check if error is retryable
            non_retryable_errors = [
                'FileNotFoundError',
                'PermissionError',
                'JSONDecodeError',  # Usually indicates a structural problem
            ]
            
            # Check for specific error messages that indicate we should retry
            retryable_messages = [
                'rate limit',
                'quota exceeded',
                'timeout',
                '503',
                '429',
                'connection',
                'temporary',
                'unavailable'
            ]
            
            should_retry = (
                error_type not in non_retryable_errors and 
                (any(msg in error_msg.lower() for msg in retryable_messages) or retry_count < max_retries)
            )
            
            if not should_retry or retry_count >= max_retries:
                # Final failure - save detailed error data
                error_data = {
                    'error_type': error_type,
                    'error_message': error_msg,
                    'metadata': None,
                    'comparison_results': {},
                    'deviation_entry': {'status': 'error'},
                    'user_decisions': [],
                    'unresolved_items': [],
                    'search_resolution_results': None,
                    'retry_count': retry_count,
                    'stacktrace': full_traceback,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
                # Capture detailed error info if available
                if hasattr(last_error, '_detailed_info'):
                    error_data['detailed_error_info'] = last_error._detailed_info
                    if verbose:
                        print(f"[{thread_name}] 🔍 Detailed error info: {json.dumps(last_error._detailed_info, indent=2)}")
                
                logger.error(f"[{thread_name}] Final failure for {filename} after {retry_count} retries: {error_type}: {error_msg}")
                results_collector.add_result(pdf_path, error_data)
                return False
            
            retry_count += 1
            # Will retry in next iteration
    
    # Should never reach here, but just in case
    logger.error(f"[{thread_name}] Unexpected exit from retry loop for {filename}")
    return False

def find_pdf_files(docs_dir: str, excel_data: pd.DataFrame) -> Dict[str, str]:
    """Find PDF files based on downloaded files and match them to Excel data."""
    pdf_files = {}
    docs_path = Path(docs_dir)
    
    # Get all actual PDF files in the docs directory
    actual_pdf_files = []
    try:
        for pdf_file in docs_path.glob('*.pdf'):
            if pdf_file.is_file():
                actual_pdf_files.append(pdf_file.name)
    except Exception as e:
        print(f"Error scanning docs directory: {e}")
        return {}
    
    print(f"Found {len(actual_pdf_files)} PDF files in {docs_dir}")
    
    # For batch processing, we'll process all available PDF files
    # and match them back to Excel data during processing
    for filename in actual_pdf_files:
        pdf_path = docs_path / filename
        if pdf_path.exists():
            pdf_files[filename] = str(pdf_path)
    
    return pdf_files

def batch_process_pdfs(excel_path: str, docs_dir: str, api_key: str,
                      workers: int = 4, batch_size: int = 50,
                      enable_search: bool = False, search_threshold: float = 0.8,
                      resume: bool = False, progress_file: str = "batch_progress.json",
                      verbose: bool = False, limit: Optional[int] = None, 
                      retry_failed: bool = False, max_retries: int = 3) -> BatchResults:
    """Process multiple PDFs concurrently with progress tracking and resume capability."""
    
    print(f"🚀 Starting batch processing with {workers} workers")
    print(f"📊 Excel file: {excel_path}")
    print(f"📁 Docs directory: {docs_dir}")
    
    # Load ground truth data once
    print("Loading ground truth data...")
    ground_truth = load_ground_truth_metadata(excel_path)
    excel_data = pd.read_excel(excel_path)
    print_ground_truth_stats(ground_truth)
    
    # Find PDF files
    print("\nDiscovering PDF files...")
    pdf_files = find_pdf_files(docs_dir, excel_data)
    print(f"Found {len(pdf_files)} PDF files to process")
    
    if not pdf_files:
        print("❌ No PDF files found matching Excel data")
        return BatchResults()
    
    # Initialize or load progress
    progress = None
    if resume or retry_failed:
        progress = BatchProgress.load_from_file(progress_file)
        if progress:
            if retry_failed:
                print(f"🔄 Retrying {len(progress.failed)} failed files from checkpoint")
            else:
                print(f"📈 Resuming from checkpoint: {len(progress.completed)}/{progress.total_files} completed")
    
    if not progress:
        if retry_failed:
            print(f"❌ No progress file found at {progress_file}. Cannot retry failed files.")
            return BatchResults()
        
        # Backup existing progress file before creating new one
        if os.path.exists(progress_file):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = progress_file.replace('.json', f'_backup_{timestamp}.json')
            try:
                import shutil
                shutil.copy2(progress_file, backup_file)
                print(f"💾 Existing progress backed up to: {backup_file}")
            except Exception as e:
                print(f"⚠️  Warning: Could not backup existing progress file: {e}")
        
        # Create new progress tracker
        progress = BatchProgress(
            total_files=len(pdf_files),
            completed=[],
            failed=[],
            pending=list(pdf_files.keys()),
            start_time=datetime.datetime.now().isoformat(),
            last_checkpoint=datetime.datetime.now().isoformat()
        )
        print(f"📋 Starting fresh batch processing of {len(pdf_files)} files")
    
    # Filter files based on mode
    if retry_failed:
        # Extract filenames from failed entries (they might be dicts with 'filename' key)
        failed_filenames = []
        for item in progress.failed:
            if isinstance(item, dict):
                failed_filenames.append(item.get('filename', item))
            else:
                failed_filenames.append(item)
        
        # Only process previously failed files
        pending_files = {k: v for k, v in pdf_files.items() if k in failed_filenames}
        if not pending_files:
            print("✅ No failed files to retry!")
            return BatchResults()
        print(f"🔄 Retrying {len(pending_files)} failed files")
        # Note: We don't clear progress.failed here - only remove files that are successfully processed
    else:
        # Filter out already completed files and rebuild pending list
        pending_files = {k: v for k, v in pdf_files.items() if k not in progress.completed}
        progress.pending = list(pending_files.keys())  # Rebuild pending list to match current files
        print(f"📝 Processing {len(pending_files)} remaining files")
    
    # Apply limit if specified (for testing) - AFTER filtering for retry_failed
    if limit and limit < len(pending_files):
        pending_files_list = list(pending_files.items())[:limit]
        pending_files = dict(pending_files_list)
        print(f"Limited to first {limit} files for testing")
    
    if not pending_files:
        print("✅ All files already processed!")
        return BatchResults()
    
    # Initialize results collector
    results_collector = BatchResults()
    
    # Process files in batches with concurrent execution
    file_items = list(pending_files.items())
    processed_count = len(progress.completed)
    start_time = time.time()
    
    # Adaptive worker scaling based on rate limit utilization
    base_workers = workers
    current_workers = workers
    scaling_check_interval = 10  # Check every 10 files
    
    # Create thread pool and process files
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Process in batches to manage memory
        for batch_start in range(0, len(file_items), batch_size):
            batch_end = min(batch_start + batch_size, len(file_items))
            batch_files = file_items[batch_start:batch_end]
            
            # Check if we should adjust worker count
            if processed_count % scaling_check_interval == 0 and GEMINI_RATE_LIMITER:
                optimal_workers = calculate_optimal_workers(GEMINI_RATE_LIMITER, base_workers)
                current_rate = GEMINI_RATE_LIMITER.get_current_rate()
                utilization = current_rate / GEMINI_RATE_LIMITER.max_requests_per_minute * 100
                
                if optimal_workers != current_workers:
                    print(f"🔄 Rate limit utilization: {utilization:.1f}% - adjusting workers: {current_workers} → {optimal_workers}")
                    current_workers = optimal_workers
                    # Note: We can't dynamically resize ThreadPoolExecutor, so this is informational
                    # In a real implementation, we'd need to restart the executor or use a different approach
                elif verbose and processed_count % (scaling_check_interval * 2) == 0:
                    print(f"📊 Rate limit utilization: {utilization:.1f}% - workers: {current_workers}")
            
            print(f"\n📦 Processing batch {batch_start//batch_size + 1}: files {batch_start+1}-{batch_end}")
            
            # Submit batch to thread pool (limited by current batch size for memory management)
            batch_workers = min(current_workers, len(batch_files))
            future_to_file = {
                executor.submit(
                    process_single_pdf_batch,
                    pdf_path, ground_truth, api_key, progress, results_collector,
                    enable_search, search_threshold, verbose, GEMINI_RATE_LIMITER, SEARCH_QUOTA_TRACKER
                ): filename
                for filename, pdf_path in batch_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                filename = future_to_file[future]
                processed_count += 1
                
                try:
                    success = future.result()
                    if success:
                        progress.completed.append(filename)
                        # If this is retry mode, remove from failed list
                        if retry_failed:
                            progress.failed = [item for item in progress.failed 
                                             if (isinstance(item, dict) and item.get('filename') != filename) or 
                                                (isinstance(item, str) and item != filename)]
                    else:
                        progress.failed.append({
                            'filename': filename,
                            'timestamp': datetime.datetime.now().isoformat(),
                            'error': 'Processing failed'
                        })
                    
                    # Update progress (safe removal)
                    if filename in progress.pending:
                        progress.pending.remove(filename)
                    progress.last_checkpoint = datetime.datetime.now().isoformat()
                    
                    # Print progress
                    elapsed = time.time() - start_time
                    rate = processed_count / elapsed if elapsed > 0 else 0
                    eta = (progress.total_files - processed_count) / rate if rate > 0 else 0
                    
                    print(f"[{processed_count:4d}/{progress.total_files}] {filename} | Rate: {rate:.2f} files/sec | ETA: {eta/60:.1f}min")
                    
                    # Save progress after EVERY completion
                    progress.save_to_file(progress_file)
                    
                    # Show summary every 10 files
                    if processed_count % 10 == 0:
                        summary = results_collector.get_summary()
                        print(f"  📊 Success rate: {summary['successful']}/{summary['total_processed']} ({summary['successful']/summary['total_processed']:.1%})")
                
                except Exception as e:
                    print(f"❌ Unexpected error processing {filename}: {e}")
                    progress.failed.append({
                        'filename': filename,
                        'timestamp': datetime.datetime.now().isoformat(),
                        'error': str(e)
                    })
                    # Safe removal from pending
                    if filename in progress.pending:
                        progress.pending.remove(filename)
                    progress.last_checkpoint = datetime.datetime.now().isoformat()
                    
                    # Save progress immediately after error too
                    progress.save_to_file(progress_file)
    
    # Save final progress
    progress.save_to_file(progress_file)
    
    # Print final summary
    total_time = time.time() - start_time
    summary = results_collector.get_summary()
    
    print(f"\n🎉 BATCH PROCESSING COMPLETE")
    print(f"{'='*50}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Files processed: {summary['total_processed']}")
    print(f"Success rate: {summary['successful']}/{summary['total_processed']} ({summary['successful']/summary['total_processed']:.1%})")
    print(f"Average confidence: {summary['avg_confidence']:.2f}")
    print(f"Average accuracy: {summary['avg_accuracy']:.1%}")
    print(f"Total discrepancies: {summary['total_discrepancies']}")
    print(f"Search resolutions: {summary['search_resolutions']}")
    
    if progress.failed:
        print(f"\n❌ Failed files ({len(progress.failed)}):")
        for failure in progress.failed[-10:]:  # Show last 10 failures
            try:
                filename = failure.get('filename', 'unknown file') if isinstance(failure, dict) else str(failure)
                error = failure.get('error', 'unknown error') if isinstance(failure, dict) else 'unknown error'
                retry_count = failure.get('retry_count', 0) if isinstance(failure, dict) else 0
                retry_info = f" (after {retry_count} retries)" if retry_count > 0 else ""
                print(f"  • {filename}: {error}{retry_info}")
            except Exception as e:
                print(f"  • [Error displaying failure]: {e}")
                print(f"    Raw failure data: {failure}")
        
        print(f"\nRun with --verbose for detailed failure analysis")
    
    # Generate failure analysis report
    if progress.failed:
        generate_failure_analysis(progress.failed, verbose=verbose)
    
    return results_collector

def main():
    parser = argparse.ArgumentParser(description='PDF metadata extraction with ground truth validation and interactive resolution')
    parser.add_argument('pdf_path', nargs='?', help='Path to PDF file to process (not required for batch mode)')
    parser.add_argument('--excel', default='documents-info.xlsx', 
                       help='Path to Excel file with ground truth data')
    parser.add_argument('--api-key', 
                       default=os.environ.get('GOOGLE_API_KEY', os.environ.get('GEMINI_API_KEY', '')),
                       help='Gemini API key (defaults to GOOGLE_API_KEY or GEMINI_API_KEY env var)')
    parser.add_argument('--export-deviations', help='Export deviations to Excel file')
    parser.add_argument('--stats-only', action='store_true', help='Only show ground truth statistics')
    
    # Interactive resolution options
    parser.add_argument('--interactive', action='store_true', help='Enable interactive resolution of discrepancies')
    parser.add_argument('--auto-reference', action='store_true', help='Automatically use reference values for all discrepancies')
    parser.add_argument('--auto-extracted', action='store_true', help='Automatically use extracted values for all discrepancies')
    
    # Search grounding options
    parser.add_argument('--auto-resolve', action='store_true', default=True, help='Enable automatic search resolution of conflicts (default: True)')
    parser.add_argument('--no-auto-resolve', action='store_false', dest='auto_resolve', help='Disable automatic search resolution of conflicts')
    parser.add_argument('--with-search', action='store_true', help='Use search grounding with interactive mode')
    parser.add_argument('--search-threshold', type=float, default=0.8, help='Minimum confidence for auto-resolution (default: 0.8)')
    
    # Export options for interactive results
    parser.add_argument('--export-corrections', help='Export user corrections to Excel file')
    parser.add_argument('--export-unresolved', help='Export unresolved items to Excel file')
    parser.add_argument('--log-decisions', help='Log all user decisions to JSON file')
    
    # Batch processing options
    parser.add_argument('--batch', action='store_true', help='Enable batch processing mode')
    parser.add_argument('--docs-dir', default='docs', help='Directory containing PDF files (default: docs)')
    parser.add_argument('--workers', type=int, default=4, help='Number of concurrent workers (default: 4)')
    parser.add_argument('--batch-size', type=int, default=50, help='Process files in batches of this size (default: 50)')
    parser.add_argument('--resume', action='store_true', help='Resume batch processing from last checkpoint')
    parser.add_argument('--retry-failed', action='store_true', help='Retry only failed files from batch_progress.json')
    parser.add_argument('--progress-file', default='batch_progress.json', help='Progress tracking file (default: batch_progress.json)')
    
    # Batch output options
    parser.add_argument('--batch-results', help='Export all batch results to Excel file')
    parser.add_argument('--batch-deviations', help='Export batch deviations to Excel file')
    parser.add_argument('--batch-ground-truth', help='Export updated ground truth in original format to Excel file')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output for batch processing')
    parser.add_argument('--limit', type=int, help='Limit number of files to process (for testing)')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum number of retries for failed operations (default: 3)')
    
    args = parser.parse_args()
    
    # Validate inputs for single file mode
    if not args.batch and not args.pdf_path:
        print("Error: PDF file path required for single file mode")
        return 1
    
    if not args.batch and not os.path.exists(args.pdf_path):
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
    
    # Validate batch mode options
    if args.batch:
        if not os.path.exists(args.docs_dir):
            print(f"Error: Docs directory not found: {args.docs_dir}")
            return 1
        
        if args.workers <= 0 or args.workers > 20:
            print("Error: Number of workers must be between 1 and 20")
            return 1
        
        if hasattr(args, 'max_retries') and (args.max_retries < 0 or args.max_retries > 10):
            print("Error: Max retries must be between 0 and 10")
            return 1
        
        if args.batch_size <= 0:
            print("Error: Batch size must be greater than 0")
            return 1
        
        # Interactive modes are not compatible with batch processing
        if interactive_options > 0:
            print("Error: Interactive modes are not supported in batch processing")
            return 1
    
    # Validate search threshold
    if not (0.0 <= args.search_threshold <= 1.0):
        print("Error: Search threshold must be between 0.0 and 1.0")
        return 1
    
    try:
        # Initialize rate limiters
        print("Initializing rate limiters...")
        global GEMINI_RATE_LIMITER, SEARCH_QUOTA_TRACKER
        GEMINI_RATE_LIMITER = RateLimiter(max_requests_per_minute=140)  # 140 RPM (10 RPM buffer)
        SEARCH_QUOTA_TRACKER = SearchQuotaTracker(max_searches_per_day=1500)
        print(f"📈 Rate limiter initialized: 140 RPM limit")
        
        # Show search quota status
        quota_status = SEARCH_QUOTA_TRACKER.get_quota_status()
        print(f"🔍 Search quota status: {quota_status['used']}/{quota_status['max']} searches used today")
        
        # Load ground truth
        print("Loading ground truth data...")
        ground_truth = load_ground_truth_metadata(args.excel)
        print_ground_truth_stats(ground_truth)
        
        if args.stats_only:
            return 0
        
        # Branch to batch or single file processing
        if args.batch:
            # Batch processing mode
            print(f"\n🚀 BATCH PROCESSING MODE")
            print(f"{'='*50}")
            
            batch_results = batch_process_pdfs(
                excel_path=args.excel,
                docs_dir=args.docs_dir,
                api_key=args.api_key,
                workers=args.workers,
                batch_size=args.batch_size,
                enable_search=enable_search,
                search_threshold=args.search_threshold,
                resume=args.resume,
                progress_file=args.progress_file,
                verbose=args.verbose,
                retry_failed=args.retry_failed,
                limit=args.limit,
                max_retries=getattr(args, 'max_retries', 3)  # Use getattr for backwards compatibility
            )
            
            # ALWAYS export all batch results automatically (unless explicitly disabled)
            if batch_results:
                # Determine export paths - use saved paths from progress if resuming, otherwise generate new ones
                if args.resume and hasattr(batch_results, 'progress') and batch_results.progress:
                    # Check if progress has saved export paths from previous run
                    progress_obj = batch_results.progress if hasattr(batch_results, 'progress') else None
                else:
                    progress_obj = None
                
                # Try to get progress object from somewhere (we need to pass it to get saved paths)
                # For now, we'll determine if this is a resume by checking if saved export paths exist
                if args.resume and 'progress' in locals() and hasattr(progress, 'export_results_path') and progress.export_results_path:
                    # Resume mode - use saved export paths
                    results_path = args.batch_results if args.batch_results else progress.export_results_path
                    deviations_path = args.batch_deviations if args.batch_deviations else progress.export_deviations_path
                    ground_truth_path = args.batch_ground_truth if args.batch_ground_truth else progress.export_ground_truth_path
                    print(f"🔄 RESUMING: Using existing export files from previous run")
                else:
                    # New run - generate new filenames with timestamp
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    results_path = args.batch_results if args.batch_results else f"batch_results_{timestamp}.xlsx"
                    deviations_path = args.batch_deviations if args.batch_deviations else f"batch_deviations_{timestamp}.xlsx"
                    ground_truth_path = args.batch_ground_truth if args.batch_ground_truth else f"batch_ground_truth_{timestamp}.xlsx"
                    
                    # Save export paths to progress for future resume
                    if 'progress' in locals():
                        progress.export_results_path = results_path
                        progress.export_deviations_path = deviations_path
                        progress.export_ground_truth_path = ground_truth_path
                        progress.save_to_file(args.progress_file)
                
                # Determine if we should append (resume mode with existing export paths)
                is_resuming = args.resume and 'progress' in locals() and hasattr(progress, 'export_results_path') and progress.export_results_path
                
                # 1. Export results
                try:
                    batch_results.export_results(results_path, append_mode=is_resuming)
                    if not is_resuming:
                        print(f"\n📊 Batch results exported to: {results_path}")
                except Exception as e:
                    print(f"❌ Error exporting batch results: {e}")
                
                # 2. Export deviations (always if any exist)
                if batch_results.deviation_log:
                    try:
                        export_path = export_deviations_to_excel(batch_results.deviation_log, deviations_path, append_mode=is_resuming)
                        if export_path and not is_resuming:
                            print(f"📊 Batch deviations exported to: {export_path}")
                            print(f"   • Total deviations tracked: {len(batch_results.deviation_log)}")
                    except Exception as e:
                        print(f"❌ Error exporting batch deviations: {e}")
                else:
                    print(f"✅ No deviations to export (perfect match with ground truth)")
                
                # 3. Export updated ground truth
                try:
                    # Use the same file as both input and output for true search & replace
                    input_file = ground_truth_path if (is_resuming and os.path.exists(ground_truth_path)) else "documents-info.xlsx"
                    batch_results.export_updated_ground_truth(ground_truth_path, input_file)
                    if input_file != "documents-info.xlsx":
                        print(f"📊 Updated ground truth (search & replace): {ground_truth_path}")
                        print(f"   • Input: {input_file} → Output: {ground_truth_path}")
                    else:
                        print(f"📊 Updated ground truth exported to: {ground_truth_path}")
                except Exception as e:
                    print(f"❌ Error exporting updated ground truth: {e}")
                
                # Print summary of all exports
                print(f"\n{'='*50}")
                print(f"📁 ALL BATCH EXPORTS COMPLETED:")
                print(f"   • Results: {results_path}")
                if batch_results.deviation_log:
                    print(f"   • Deviations: {deviations_path}")
                print(f"   • Ground Truth: {ground_truth_path}")
                if not args.resume or not ('progress' in locals() and progress.export_results_path):
                    print(f"   • Timestamp: {timestamp}")
                else:
                    print(f"   • Mode: Resume (appending to existing files)")
                print(f"{'='*50}")
            
            return 0
        
        else:
            # Single file processing mode
            print(f"\n🔍 SINGLE FILE PROCESSING MODE")
            print(f"{'='*50}")
            
            # Process PDF with interactive mode and search options
            results = process_pdf_with_validation(
                args.pdf_path, ground_truth, args.api_key, interactive_mode, 
                enable_search, args.search_threshold, GEMINI_RATE_LIMITER, 
                SEARCH_QUOTA_TRACKER, getattr(args, 'max_retries', 3)
            )
        
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