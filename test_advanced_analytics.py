"""
test_advanced_analytics.py
Test script to verify fetch_advanced_analytics DB query function and PostgreSQL aggregations.
"""

import sys
from database.db import fetch_advanced_analytics

def test_analytics():
    print("Testing fetch_advanced_analytics()...")
    success, result = fetch_advanced_analytics()
    if not success:
        print(f"FAILED: {result}")
        sys.exit(1)
    
    print("SUCCESS! Returned analytics keys:")
    for k in result.keys():
        print(f" - {k}: {type(result[k])}")
    
    summary = result.get('overall_summary', {})
    print("\nSummary metrics:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    
    print("\nSample array items:")
    print("  events_by_type:", [dict(r) for r in result.get('events_by_type', [])[:3]])
    print("  events_by_state:", [dict(r) for r in result.get('events_by_state', [])[:3]])
    print("  reports_over_time:", [dict(r) for r in result.get('reports_over_time', [])[:3]])
    print("  source_distribution:", [dict(r) for r in result.get('source_distribution', [])[:3]])
    print("  verification_distribution:", [dict(r) for r in result.get('verification_distribution', [])[:3]])
    print("  trust_score_distribution:", result.get('trust_score_distribution', []))
    print("  top_cities:", [dict(r) for r in result.get('top_cities', [])[:3]])
    print("  top_sources:", [dict(r) for r in result.get('top_sources', [])[:3]])
    
    # Test filters
    print("\nTesting with filters (event_type='Heavy Rain')...")
    success_filtered, result_filtered = fetch_advanced_analytics(event_type='Heavy Rain')
    if success_filtered:
        print("Filter test SUCCESS! Total reports with Heavy Rain filter:", result_filtered['overall_summary']['total_reports'])
    else:
        print(f"Filter test FAILED: {result_filtered}")

if __name__ == "__main__":
    test_analytics()
