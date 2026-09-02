"""
Test script for verifying mobile banking transfer slips with Gemini Vision.
"""

import io
import dotenv
from PIL import Image, ImageDraw

dotenv.load_dotenv()
import llm_vision

# Create a sample KBank transfer slip image
img = Image.new("RGB", (350, 300), color=(240, 248, 240))
draw = ImageDraw.Draw(img)
draw.text((20, 20), "KBANK / ธนาคารกสิกรไทย", fill=(0, 100, 0))
draw.text((20, 50), "โอนเงินสำเร็จ (Transfer Successful)", fill=(0, 0, 0))
draw.text((20, 80), "จาก: นายสมชาย (From)", fill=(50, 50, 50))
draw.text((20, 110), "ไปยัง: ร้านอาหารตามสั่ง (To)", fill=(50, 50, 50))
draw.text((20, 150), "จำนวนเงิน: 180.00 บาท", fill=(0, 0, 0))
draw.text((20, 180), "วันที่: 01 ก.ย. 2569 12:30 น.", fill=(100, 100, 100))
draw.text((20, 210), "เลขที่อ้างอิง: 20260901KBANK8899", fill=(100, 100, 100))

buf = io.BytesIO()
img.save(buf, format="JPEG")
image_bytes = buf.getvalue()

print("Testing Gemini Vision with synthetic KBank transfer slip...")
result = llm_vision.analyze_receipt_image(image_bytes)
print("Result:", result)
assert result is not None, "Expected slip detection"
assert result["evidence_type"] == "สลิปโอน", f"Expected สลิปโอน, got {result['evidence_type']}"
print("Bank slip test passed successfully! ✅")
