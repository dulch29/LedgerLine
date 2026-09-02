"""
State tracking for pending confirmations and multi-turn reconciliation (v2).

AGENTIC AI CONCEPT: "Multi-Turn Context & Reconciliation"
──────────────────────────────────────────────────────────
In a true conversational agent, actions span across multiple turns:
  Turn 1: User sends text: "มื้อเช้า 150 บาท"
          → Bot logs row 11, saves session memory {"row": 11, "amount": 150}
  Turn 2: User confirms: "ใช่"
          → Bot updates status to "จ่าย"
  Turn 3: User sends an image of a bank slip
          → Bot checks session memory: "Ah! Row 11 was recently logged by this user!"
          → Bot attaches "สลิปโอน" directly to Row 11!

This module manages the working memory for each user session.
"""

import time
from typing import Any

# Maps user_id → dict of session data
# Example:
#   {
#     "U1234abcd": {
#       "row": 11,
#       "amount": 150.0,
#       "description": "ค่ามื้อเช้า",
#       "updated_at": 1725200000.0,
#       "status_confirmed": False
#     }
#   }
_sessions: dict[str, dict[str, Any]] = {}

# Context memory timeout in seconds (1 hour)
SESSION_TIMEOUT_SECONDS = 3600


def set_pending(
    user_id: str,
    row_number: int,
    amount: float | None = None,
    description: str | None = None,
) -> None:
    """Store active expense session for this user."""
    _sessions[user_id] = {
        "row": row_number,
        "amount": amount,
        "description": description or "",
        "updated_at": time.time(),
        "status_confirmed": False,
    }


def get_pending(user_id: str) -> int | None:
    """
    Get the active row awaiting confirmation for this user.
    Returns row number or None if expired/not found.
    """
    session = _get_valid_session(user_id)
    if session and not session.get("status_confirmed", False):
        return session.get("row")
    return None


def get_recent_row(user_id: str) -> int | None:
    """
    Get the most recent row logged by this user (e.g. for attaching a slip later).
    Returns row number or None if expired/not found.
    """
    session = _get_valid_session(user_id)
    if session:
        return session.get("row")
    return None


def mark_status_confirmed(user_id: str) -> None:
    """Mark that the status (paid/pending) has been answered, but keep row memory for slips."""
    if user_id in _sessions:
        _sessions[user_id]["status_confirmed"] = True
        _sessions[user_id]["updated_at"] = time.time()


def clear_pending(user_id: str) -> None:
    """Clear session memory completely."""
    _sessions.pop(user_id, None)


def _get_valid_session(user_id: str) -> dict[str, Any] | None:
    """Internal helper to get a session if it hasn't timed out."""
    session = _sessions.get(user_id)
    if not session:
        return None

    # Auto-expire sessions older than SESSION_TIMEOUT_SECONDS
    if time.time() - session.get("updated_at", 0) > SESSION_TIMEOUT_SECONDS:
        _sessions.pop(user_id, None)
        return None

    return session
