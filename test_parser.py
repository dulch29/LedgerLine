"""
Test script for the LLM expense parser.

Run this BEFORE testing the full bot — it verifies that Gemini can parse
your messages correctly without needing LINE or Google Sheets.

Usage:
    python test_parser.py

Before running:
    1. Make sure GEMINI_API_KEY is set in your .env file
    2. pip install -r requirements.txt
"""

import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

# Quick check: is the API key set?
if not os.getenv("GEMINI_API_KEY"):
    print("❌ GEMINI_API_KEY not found in .env")
    print("   Get a free key at: https://aistudio.google.com/apikey")
    print("   Then add this line to your .env file:")
    print("   GEMINI_API_KEY=your_key_here")
    sys.exit(1)

from llm_parser import parse_expense

# ── Test messages ────────────────────────────────────────────────────────
test_messages = [
    # (input_message, should_be_expense)
    ("7am breakfast 150 baht", True),
    ("taxi 200", True),
    ("กาแฟ 65 บาท", True),
    ("coffee and cake 180", True),
    ("lunch at street stall 80 baht around noon", True),
    ("hello", False),
    ("thanks!", False),
    ("what's the weather?", False),
    ("ข้าวผัด 60", True),
    ("BTS 50 baht", True),
]

print("=" * 60)
print("🧪 Testing LLM Expense Parser (Gemini)")
print("=" * 60)

passed = 0
failed = 0

for message, should_be_expense in test_messages:
    result = parse_expense(message)

    if should_be_expense:
        if result is not None:
            print(f"\n✅ PASS: '{message}'", flush=True)
            print(f"   → description: {result['description']}", flush=True)
            print(f"   → amount: ฿{result['amount']:,.0f}", flush=True)
            print(f"   → time: {result.get('time', 'N/A')}", flush=True)
            passed += 1
        else:
            print(f"\n❌ FAIL: '{message}' — expected expense, got None", flush=True)
            failed += 1
    else:
        if result is None:
            print(f"\n✅ PASS: '{message}' → correctly ignored (not an expense)", flush=True)
            passed += 1
        else:
            print(f"\n❌ FAIL: '{message}' — expected None, got {result}", flush=True)
            failed += 1

print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed, {len(test_messages)} total")
print("=" * 60)

if failed > 0:
    print("\n⚠️  Some tests failed — LLM output can vary slightly between runs.")
    print("   If the descriptions are reasonable Thai translations, that's OK.")
    print("   Re-run to see if it was a fluke.")
