"""
Test script for Google Sheets integration.

Run this AFTER setting up your Google Cloud credentials — it writes a test
row to your sheet and then reads it back to verify everything works.

Usage:
    python test_sheets.py

Before running:
    1. Complete the Google Cloud setup (see README.md)
    2. Make sure these are in your .env:
       - GOOGLE_SHEET_ID
       - GOOGLE_SERVICE_ACCOUNT_FILE (or have credentials.json in project root)
    3. Make sure you've shared the sheet with your service account email
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Pre-flight checks ──────────────────────────────────────────────────
errors = []
if not os.getenv("GOOGLE_SHEET_ID"):
    errors.append("GOOGLE_SHEET_ID not set in .env")

creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
if not os.path.exists(creds_file):
    errors.append(f"Credentials file '{creds_file}' not found")

if errors:
    print("❌ Cannot run Sheets test:")
    for e in errors:
        print(f"   • {e}")
    print("\n   See README.md for Google Cloud setup instructions.")
    sys.exit(1)


from sheets_client import get_next_row, should_write_date, append_expense, _today_str

print("=" * 60)
print("🧪 Testing Google Sheets Integration")
print("=" * 60)

# ── Test 1: Can we connect and read? ───────────────────────────────────
print("\n📊 Test 1: Connecting to Google Sheets...")
try:
    next_row = get_next_row()
    print(f"   ✅ Connected! Next empty row: {next_row}")
except Exception as e:
    print(f"   ❌ Failed to connect: {e}")
    print("\n   Common fixes:")
    print("   • Did you share the sheet with the service account email?")
    print("   • Is the Sheet ID correct?")
    print("   • Is the Google Sheets API enabled in your GCP project?")
    sys.exit(1)

# ── Test 2: Date logic ─────────────────────────────────────────────────
print("\n📅 Test 2: Checking date logic...")
try:
    needs_date = should_write_date(next_row)
    today = _today_str()
    print(f"   Today's date: {today}")
    print(f"   Should write date for row {next_row}: {'YES ✍️' if needs_date else 'NO (same day as previous entry)'}")
    print("   ✅ Date logic works!")
except Exception as e:
    print(f"   ❌ Date check failed: {e}")
    sys.exit(1)

# ── Test 3: Write a test expense ───────────────────────────────────────
print("\n✏️  Test 3: Writing a test expense...")
print("   This will write a row to your actual sheet!")
response = input("   Continue? (y/n): ").strip().lower()

if response in ("y", "yes"):
    try:
        row = append_expense("🧪 ทดสอบระบบ (test entry)", 0)
        print(f"   ✅ Wrote test expense to row {row}")
        print(f"   → Open your Google Sheet and check row {row}")
        print("   → You can delete this test row afterwards")
    except Exception as e:
        print(f"   ❌ Failed to write: {e}")
else:
    print("   ⏭️  Skipped write test")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
