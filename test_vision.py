"""
Test script for llm_vision.py using sample images or direct verification.
"""

import io
import os
import dotenv
from PIL import Image, ImageDraw

dotenv.load_dotenv()
import llm_vision

# Create a sample test receipt image in memory
img = Image.new("RGB", (300, 200), color=(255, 255, 255))
draw = ImageDraw.Draw(img)
draw.text((20, 20), "7-Eleven Thailand", fill=(0, 0, 0))
draw.text((20, 50), "Receipt / ใบเสร็จรับเงิน", fill=(0, 0, 0))
draw.text((20, 80), "Drinking Water: 15 THB", fill=(0, 0, 0))
draw.text((20, 110), "Bread: 25 THB", fill=(0, 0, 0))
draw.text((20, 140), "TOTAL: 40.00 THB", fill=(0, 0, 0))

buf = io.BytesIO()
img.save(buf, format="JPEG")
image_bytes = buf.getvalue()

print("Testing Gemini Vision with synthetic 7-Eleven receipt...")
result = llm_vision.analyze_receipt_image(image_bytes)
print("Result:", result)
assert result is not None, "Expected receipt detection"
assert result["evidence_type"] == "ใบเสร็จรับเงิน", f"Unexpected type: {result['evidence_type']}"
print("Vision test passed successfully! ✅")
