"""
LedgerLine — Day 2: AI-powered trip expense logger.

WHAT CHANGED FROM DAY 1 (echo bot):
────────────────────────────────────
The echo handler has been replaced with a multi-step flow:
  1. Check if the user is answering a "paid?" confirmation → update status
  2. Otherwise, try to parse the message as an expense → log to Google Sheets
  3. If parsing fails, reply with a helpful hint

AGENTIC AI CONCEPT: "Orchestrator Pattern"
──────────────────────────────────────────
This file is the ORCHESTRATOR — it doesn't do the hard work itself. Instead,
it coordinates three tools:
  • llm_parser.py  → understands human language (the "brain")
  • sheets_client.py → reads/writes Google Sheets (the "hands")
  • state.py → remembers pending confirmations (the "memory")

This is the core pattern of agentic AI: an orchestrator that decides WHICH
tool to use, WHEN, and WHAT to do with the result. The LLM handles reasoning,
the tools handle actions, and the orchestrator ties them together.
"""

import os
import logging

from dotenv import load_dotenv
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

import llm_parser
import sheets_client
import state

# ── Setup ────────────────────────────────────────────────────────────────

load_dotenv()

# Configure logging so we can see what's happening in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    raise RuntimeError(
        "Missing LINE credentials. Copy .env.example to .env and fill in your "
        "channel secret + access token from the LINE Developers Console."
    )

app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ── Words the user might say to confirm "yes, it's paid" ────────────────
# We check these in lowercase so "Yes", "YES", "yes" all match.
YES_WORDS = {"yes", "y", "ใช่", "paid", "จ่ายแล้ว", "จ่าย", "ค่ะ", "ครับ"}
NO_WORDS = {"no", "n", "ไม่", "not yet", "ยัง", "ยังไม่จ่าย", "pending"}


# ── Webhook endpoint ────────────────────────────────────────────────────

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        # This usually means the channel secret is wrong, or the request
        # didn't actually come from LINE.
        abort(400)

    return "OK"


# Keep track of processed webhook events to prevent duplicate processing on retries
_processed_event_ids = set()


# ── Message handler ─────────────────────────────────────────────────────

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """
    The main message handler — the "brain" of the orchestrator.
    """
    event_id = getattr(event, "webhook_event_id", None)
    if event_id:
        if event_id in _processed_event_ids:
            logger.info("Ignoring duplicate webhook event: %s", event_id)
            return
        _processed_event_ids.add(event_id)
        # Limit set size so memory doesn't grow unbounded
        if len(_processed_event_ids) > 1000:
            _processed_event_ids.pop()

    user_id = event.source.user_id
    user_text = event.message.text.strip()
    reply_text = ""

    logger.info("Message from %s: '%s'", user_id, user_text)

    # ── Step 1: Check for pending confirmation ──────────────────────
    pending_row = state.get_pending(user_id)
    if pending_row is not None:
        reply_text = _handle_confirmation(user_id, user_text, pending_row)
    else:
        # ── Step 2: Try to parse as an expense ──────────────────────
        reply_text = _handle_expense(user_id, user_text)

    # ── Send the reply ──────────────────────────────────────────────
    if reply_text:
        _reply(event.reply_token, user_id, reply_text)


def _handle_confirmation(user_id: str, user_text: str, row: int) -> str:
    """
    Handle a yes/no reply to the "Paid already?" question.
    """
    text_lower = user_text.lower().strip()

    try:
        if text_lower in YES_WORDS:
            sheets_client.update_status(row, "จ่าย")
            state.clear_pending(user_id)
            return "บันทึกสถานะแล้ว: จ่ายแล้ว"
        elif text_lower in NO_WORDS:
            sheets_client.update_status(row, "รอดำเนินการ")
            state.clear_pending(user_id)
            return "บันทึกสถานะแล้ว: รอดำเนินการ"
        else:
            # The user said something unexpected — clear pending state
            # and treat this as a new expense message.
            state.clear_pending(user_id)
            sheets_client.update_status(row, "รอดำเนินการ")
            logger.info(
                "Unexpected confirmation reply '%s', treating as new expense",
                user_text,
            )
            return _handle_expense(user_id, user_text)

    except Exception as e:
        logger.error("Failed to update status for row %d: %s", row, e, exc_info=True)
        state.clear_pending(user_id)
        return f"⚠️ เกิดข้อผิดพลาดในการอัปเดตสถานะ: {e}"


def _handle_expense(user_id: str, user_text: str) -> str:
    """
    Parse a message as an expense and log it to Google Sheets.
    """
    # ── 1. REASON: Parse with Gemini ──────────────────────────────
    parsed = llm_parser.parse_expense(user_text)

    if parsed is None:
        return (
            "🤔 ไม่เข้าใจข้อความ ลองพิมพ์แบบนี้:\n"
            '  "breakfast 150 baht"\n'
            '  "taxi 200"\n'
            '  "กาแฟ 65 บาท"'
        )

    description = parsed["description"]
    amount = parsed["amount"]

    # ── 2. ACT: Write to Google Sheets ────────────────────────────
    try:
        row_num = sheets_client.append_expense(description, amount)
    except Exception as e:
        logger.error("Failed to write to Google Sheets: %s", e, exc_info=True)
        return (
            f"⚠️ เข้าใจข้อความแล้ว ({description} ฿{amount:.0f}) "
            f"แต่เขียนลง Sheet ไม่ได้\nError: {e}"
        )

    # ── 3. REMEMBER: Store pending confirmation ───────────────────
    state.set_pending(user_id, row_num)

    # ── Build reply matching your requested format ────────────────
    item_num = row_num - 4  # Row 5 is Item 1, Row 11 is Item 7, etc.
    return (
        f"บันทึกแล้ว: {description} {amount:,.0f} บาท\n"
        f"รายการที่ {item_num}\n"
        f"จ่ายแล้วหรือยัง? (ใช่/ไม่ใช่)"
    )


def _reply(reply_token: str, user_id: str, text: str) -> None:
    """Send a text reply back to the user via LINE, with push fallback."""
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            try:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text=text)],
                    )
                )
                logger.info("Successfully sent reply message to user %s", user_id)
                return
            except Exception as reply_err:
                logger.warning(
                    "Reply token failed (%s), falling back to push message: %s",
                    reply_token, reply_err
                )

            # Fallback to push message directly to the user
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=text)],
                )
            )
            logger.info("Successfully sent push message fallback to user %s", user_id)
    except Exception as e:
        logger.error("Failed to send LINE message to user %s: %s", user_id, e)


# ── Health check ─────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health_check():
    # Just so you can confirm the server is alive by visiting the root URL.
    return "LedgerLine v1 is running 🚀"


if __name__ == "__main__":
    app.run(port=5000, debug=True)
