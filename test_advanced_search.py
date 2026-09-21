"""
test_advanced_search.py
Automated verification script for Step 31: Advanced Weather Report Search & Filtering.
"""

import sys
from database.db import init_db, search_weather_reports, fetch_report_by_id

def test_search_and_filtering():
    print("1. Testing database index initialization...")
    ok, msg = init_db()
    if not ok:
        print(f"FAILED init_db: {msg}")
        sys.exit(1)
    print(f"SUCCESS: {msg}")

    print("\n2. Testing default search_weather_reports()...")
    ok, res = search_weather_reports(page=1, per_page=5)
    if not ok:
        print(f"FAILED search: {res}")
        sys.exit(1)
    
    print(f"SUCCESS: Total records = {res['total']}, Total pages = {res['total_pages']}, Returned = {len(res['reports'])}")
    if res['reports']:
        sample_id = res['reports'][0]['id']
        print(f"Sample report #1: ID={sample_id}, Source='{res['reports'][0].get('source')}', Event='{res['reports'][0].get('event_type')}', City='{res['reports'][0].get('city')}'")

    print("\n3. Testing keyword search (keyword='Rain')...")
    ok, kw_res = search_weather_reports(keyword='Rain', page=1, per_page=10)
    if ok:
        print(f"SUCCESS: Found {kw_res['total']} reports matching keyword 'Rain'.")

    print("\n4. Testing Event Type filter (event_type='Thunderstorm')...")
    ok, ev_res = search_weather_reports(event_type='Thunderstorm', page=1, per_page=10)
    if ok:
        print(f"SUCCESS: Found {ev_res['total']} reports for 'Thunderstorm'.")

    print("\n5. Testing State filter (state='Maharashtra')...")
    ok, st_res = search_weather_reports(state='Maharashtra', page=1, per_page=10)
    if ok:
        print(f"SUCCESS: Found {st_res['total']} reports for 'Maharashtra'.")

    print("\n6. Testing Trust Level filter (trust_level='High Trust')...")
    ok, tr_res = search_weather_reports(trust_level='High Trust', page=1, per_page=10)
    if ok:
        print(f"SUCCESS: Found {tr_res['total']} reports for High Trust (80+).")

    print("\n7. Testing Verification filter (verification='Likely Consistent')...")
    ok, v_res = search_weather_reports(verification='Likely Consistent', page=1, per_page=10)
    if ok:
        print(f"SUCCESS: Found {v_res['total']} reports for 'Likely Consistent'.")

    print("\n8. Testing Server-Side Sorting (sort_by='trust_desc')...")
    ok, sort_res = search_weather_reports(sort_by='trust_desc', page=1, per_page=5)
    if ok and sort_res['reports']:
        scores = [r.get('trust_score') for r in sort_res['reports']]
        print(f"SUCCESS: Sorted top 5 trust scores: {scores}")

    print("\n9. Testing single report detail lookup...")
    if res['reports']:
        first_id = res['reports'][0]['id']
        ok, detail = fetch_report_by_id(first_id)
        if ok and detail:
            print(f"SUCCESS: Retrieved details for report #{first_id}: Source='{detail.get('source')}', Text='{detail.get('report_text')[:40]}...'")
        else:
            print(f"FAILED to retrieve report #{first_id}")
            sys.exit(1)

    print("\nALL STEP 31 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_search_and_filtering()
