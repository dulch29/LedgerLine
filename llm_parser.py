"""
LLM-powered expense parser using Google Gemini.

AGENTIC AI CONCEPT: "Tool Use"
──────────────────────────────
In agentic AI, the LLM isn't the whole app — it's a *tool* that the app
calls when it needs intelligence. Here, our Flask app (the "agent") calls
Gemini (the "tool") specifically for one job: understanding messy human
text and extracting structured data from it.

By keeping this in its own module, we achieve:
1. Separation of concerns: app.py doesn't know or care about Gemini internals
2. Swappability: you can switch to GPT, Claude, or a local model by only
   changing this file
3. Testability: you can test the parser without running the full LINE bot

AGENTIC AI CONCEPT: "Structured Output"
────────────────────────────────────────
We tell Gemini to return its answer as JSON with specific fields. This is
way more reliable than trying to regex-parse a free-text response. The
model's output becomes a clean Python dict that the rest of our code can
trust.
"""

import json
import os
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ── Gemini client setup ──────────────────────────────────────────────────

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazy-initialize the Gemini client (created on first use)."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY in .env — get one free at "
                "https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=api_key)
    return _client


# ── The system prompt ────────────────────────────────────────────────────
# This is the set of instructions Gemini follows every time it parses a
# message. The prompt is in English (LLMs follow English instructions most
# reliably) but we tell it to output Thai descriptions.

SYSTEM_PROMPT = """\
You are an expense-tracking assistant for a Bangkok trip.

Your ONLY job: look at a chat message and decide if it describes an expense.
If it does, extract structured data. If it doesn't, say so.

RULES:
1. The user might write in English, Thai, or a mix. Handle all three.
2. Always output the item description in Thai.
3. The amount should be a plain number (no currency symbol).
4. Time is optional — extract it only if the user mentions a specific time.
   Use 24-hour format (HH:MM).
5. If the message is NOT an expense (greetings, questions, random chat),
   set "is_expense" to false.

EXAMPLES:
  Input: "7am breakfast 150 baht"
  Output: {"is_expense": true, "amount": 150, "description": "ค่าอาหารเช้า", "time": "07:00"}

  Input: "taxi 200"
  Output: {"is_expense": true, "amount": 200, "description": "ค่าแท็กซี่", "time": null}

  Input: "กาแฟ 65 บาท"
  Output: {"is_expense": true, "amount": 65, "description": "กาแฟ", "time": null}

  Input: "hello"
  Output: {"is_expense": false, "amount": null, "description": null, "time": null}

  Input: "coffee and cake 180"
  Output: {"is_expense": true, "amount": 180, "description": "กาแฟและเค้ก", "time": null}

  Input: "lunch at street stall 80 baht around noon"
  Output: {"is_expense": true, "amount": 80, "description": "ค่าอาหารกลางวัน", "time": "12:00"}
"""


# ── The main parse function ─────────────────────────────────────────────

def parse_expense(user_message: str) -> dict | None:
    """
    Send a raw user message to Gemini and get structured expense data back.

    Returns a dict like:
        {"amount": 150, "description": "ค่าอาหารเช้า", "time": "07:00"}
    if the message is an expense, or None if it's not.

    The heavy lifting here is done by Gemini's "response_mime_type" feature,
    which forces the model to return valid JSON matching our schema. This is
    much more reliable than asking for JSON in the prompt and hoping for the
    best.
    """
    client = _get_client()

    # Define the shape of JSON we want back.
    # Gemini will ONLY return data matching this schema.
    response_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "is_expense": types.Schema(type=types.Type.BOOLEAN),
            "amount": types.Schema(type=types.Type.NUMBER, nullable=True),
            "description": types.Schema(type=types.Type.STRING, nullable=True),
            "time": types.Schema(type=types.Type.STRING, nullable=True),
        },
        required=["is_expense", "amount", "description", "time"],
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=response_schema,
                # Low temperature = more deterministic/consistent outputs.
                # We don't want creative answers, we want reliable parsing.
                temperature=0.1,
            ),
        )

        # Parse the JSON string Gemini returned into a Python dict
        result = json.loads(response.text)
        logger.info("Gemini parsed '%s' → %s", user_message, result)

        if not result.get("is_expense"):
            return None

        return {
            "amount": result["amount"],
            "description": result["description"],
            "time": result.get("time"),
        }

    except Exception as e:
        # If Gemini fails (network error, quota exceeded, etc.), we don't
        # want the whole bot to crash. Log the error and return None so the
        # bot can reply with a friendly "I didn't understand" message.
        logger.error("Gemini parsing failed: %s", e, exc_info=True)
        return None
