"""
Multimodal Vision Classifier using Google Gemini Vision.

AGENTIC AI CONCEPT: "Multimodal Tool Use"
────────────────────────────────────────
In agentic AI, tools aren't limited to text. A multimodal tool can process
images, audio, or video. Here, Gemini Vision acts as our visual perception
engine: it inspects receipts and mobile banking slips and extracts structured
data directly from pixels.

It classifies images into 3 exact categories matching the Google Sheet dropdown:
  1. "สลิปโอน"       (Mobile banking transfer slip: KBank, SCB, PromptPay, etc.)
  2. "ใบเสร็จรับเงิน"  (Printed official POS receipts: 7-Eleven, restaurants, etc.)
  3. "สลิปเงินสด"     (Handwritten cash bill or manual receipt)
"""

import json
import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY in .env")
        _client = genai.Client(api_key=api_key)
    return _client


VISION_SYSTEM_PROMPT = """\
You are an expert expense receipt and bank slip analyzer for a trip in Thailand.

Your job: Look at the provided image and extract structured financial details.

CLASSIFICATION RULES for "evidence_type":
- "สลิปโอน": Any mobile banking transfer slip (e.g. KBank / Kasikorn, SCB, Krungthai NEXT, Bangkok Bank, PromptPay, TrueMoney). Usually shows sender, receiver, transaction reference, transfer time, and amount.
- "ใบเสร็จรับเงิน": Printed cash register / POS receipts (e.g. 7-Eleven, supermarket, restaurant, train tickets, hotel receipts).
- "สลิปเงินสด": Handwritten cash bills, carbon-copy receipts, or manual paper receipts.
- Set "is_receipt_or_slip" to false if the image is unrelated (e.g. selfies, scenery, memes).

EXTRACTION RULES:
1. amount: Total amount paid in Thai Baht as a plain number (e.g. 150.0). If amount cannot be found, set to null.
2. description: Short Thai summary of what was paid for (e.g. "ค่าอาหาร 7-Eleven", "โอนเงิน PromptPay", "ตั๋วรถไฟ").
3. evidence_type: Must be one of ["ใบเสร็จรับเงิน", "สลิปโอน", "สลิปเงินสด"] or null if not an expense slip.
"""


def analyze_receipt_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict | None:
    """
    Send an image to Gemini Vision and return structured receipt data.

    Returns:
      dict like: {
        "is_receipt_or_slip": True,
        "evidence_type": "สลิปโอน",
        "amount": 150.0,
        "description": "โอนเงิน PromptPay",
        "merchant_or_bank": "KBank"
      }
      or None if image is not a receipt/slip.
    """
    client = _get_client()

    response_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "is_receipt_or_slip": types.Schema(type=types.Type.BOOLEAN),
            "evidence_type": types.Schema(type=types.Type.STRING, nullable=True),
            "amount": types.Schema(type=types.Type.NUMBER, nullable=True),
            "description": types.Schema(type=types.Type.STRING, nullable=True),
            "merchant_or_bank": types.Schema(type=types.Type.STRING, nullable=True),
        },
        required=["is_receipt_or_slip", "evidence_type", "amount", "description", "merchant_or_bank"],
    )

    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[image_part, "Analyze this image and extract receipt/slip information."],
            config=types.GenerateContentConfig(
                system_instruction=VISION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.1,
            ),
        )

        result = json.loads(response.text)
        logger.info("Gemini Vision parsed image → %s", result)

        if not result.get("is_receipt_or_slip"):
            return None

        # Validate that evidence_type matches one of the 3 sheet options
        ev_type = result.get("evidence_type")
        if ev_type not in ("ใบเสร็จรับเงิน", "สลิปโอน", "สลิปเงินสด"):
            if "โอน" in str(ev_type):
                ev_type = "สลิปโอน"
            elif "เงินสด" in str(ev_type):
                ev_type = "สลิปเงินสด"
            else:
                ev_type = "ใบเสร็จรับเงิน"

        return {
            "evidence_type": ev_type,
            "amount": result.get("amount"),
            "description": result.get("description") or "ค่าใช้จ่าย",
            "merchant_or_bank": result.get("merchant_or_bank"),
        }

    except Exception as e:
        logger.error("Gemini Vision analysis failed: %s", e, exc_info=True)
        return None
