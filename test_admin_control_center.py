"""
test_admin_control_center.py
Automated verification script for Step 32: Admin & Weather Report Verification Control Center.
"""

import sys
from database.db import (
    init_db,
    authenticate_user,
    fetch_admin_summary,
    search_weather_reports,
    fetch_admin_report_details,
    update_report_verification,
    fetch_admin_action_history
)

def test_admin_control_center():
    print("1. Testing database schema initialization and user seeding...")
    ok, msg = init_db()
    if not ok:
        print(f"FAILED init_db: {msg}")
        sys.exit(1)
    print(f"SUCCESS: {msg}")

    print("\n2. Testing user authentication & role verification...")
    ok_admin, admin_user = authenticate_user("admin", "admin123")
    if not ok_admin or admin_user.get("role") != "admin":
        print(f"FAILED admin authentication: {admin_user}")
        sys.exit(1)
    print(f"SUCCESS: Authenticated admin account: username='{admin_user['username']}', role='{admin_user['role']}'")

    ok_analyst, analyst_user = authenticate_user("analyst", "analyst123")
    if not ok_analyst or analyst_user.get("role") != "analyst":
        print(f"FAILED analyst authentication: {analyst_user}")
        sys.exit(1)
    print(f"SUCCESS: Authenticated analyst account: username='{analyst_user['username']}', role='{analyst_user['role']}'")

    ok_user, demo_user = authenticate_user("demo_user", "user123")
    if not ok_user or demo_user.get("role") != "user":
        print(f"FAILED demo user authentication: {demo_user}")
        sys.exit(1)
    print(f"SUCCESS: Authenticated standard user account: username='{demo_user['username']}', role='{demo_user['role']}'")

    print("\n3. Testing Admin Summary statistics...")
    ok_sum, summary = fetch_admin_summary()
    if not ok_sum:
        print(f"FAILED fetch_admin_summary: {summary}")
        sys.exit(1)
    print("SUCCESS: Admin Summary counters:")
    for k, v in summary.items():
        print(f" - {k}: {v}")

    print("\n4. Testing Admin Reports fetch & Attention Level calculation...")
    ok_rep, rep_data = search_weather_reports(page=1, per_page=5)
    if not ok_rep or not rep_data['reports']:
        print("FAILED or empty reports list for testing admin review.")
        sys.exit(1)

    target_report = rep_data['reports'][0]
    target_id = target_report['id']
    print(f"Selected target report #{target_id}: Source='{target_report.get('source')}', Event='{target_report.get('event_type')}', Attention='{target_report.get('attention_level')}'")

    print(f"\n5. Testing fetch_admin_report_details({target_id})...")
    ok_dtl, dtl_data = fetch_admin_report_details(target_id)
    if not ok_dtl:
        print(f"FAILED fetch_admin_report_details: {dtl_data}")
        sys.exit(1)
    print(f"SUCCESS: Retrieved report #{target_id} details.")
    print(f" - Latest weather observation evidence: {dtl_data['latest_obs'].get('city') if dtl_data.get('latest_obs') else 'None'}")
    print(f" - Attention Level: {dtl_data['attention_level']}")

    print(f"\n6. Testing manual verification decision update on report #{target_id}...")
    test_reason = "Verified by administrator after comparing with OpenWeather ground observations."
    ok_upd, upd_res = update_report_verification(
        report_id=target_id,
        new_verification="Verified",
        reason=test_reason,
        action_type="Verified",
        performed_by="admin"
    )
    if not ok_upd:
        print(f"FAILED update_report_verification: {upd_res}")
        sys.exit(1)
    print(f"SUCCESS: Updated verification result to '{upd_res['new_verification']}', Recalculated trust score: {upd_res['trust_score']}%")

    print("\n7. Testing admin action audit log retrieval (admin_actions)...")
    ok_hist, hist_data = fetch_admin_action_history(page=1, per_page=5)
    if not ok_hist or not hist_data['actions']:
        print(f"FAILED fetch_admin_action_history: {hist_data}")
        sys.exit(1)
    latest_action = hist_data['actions'][0]
    print(f"SUCCESS: Audit trail record recorded successfully!")
    print(f" - Action ID: #{latest_action['id']}")
    print(f" - Report ID: #{latest_action['report_id']}")
    print(f" - Action Type: '{latest_action['action_type']}'")
    print(f" - Outcome: '{latest_action['new_verification']}'")
    print(f" - Reason: '{latest_action['reason']}'")
    print(f" - Performed By: '{latest_action['performed_by']}'")

    print("\nALL STEP 32 ADMIN CONTROL CENTER TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_admin_control_center()
