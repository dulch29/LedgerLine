"""
State tracking for pending confirmations (v1 — in-memory).

AGENTIC AI CONCEPT: "State Tracking"
─────────────────────────────────────
A normal chatbot treats every message independently — it has no memory.
But our bot needs to remember things like "I just logged row 5, and I'm
waiting for the user to tell me if it's paid or not."

This is the simplest form of multi-turn state: a Python dict that maps
each LINE user ID to the row number they need to confirm. When the server
restarts, this memory is lost — which is fine for a 10-day trip. In v2,
you'd swap this for a database (Redis, SQLite, etc.) so the bot remembers
across restarts.

Think of this as the bot's "short-term memory."
"""

# ── The state store ──────────────────────────────────────────────────────

# Maps a LINE user_id → the Google Sheet row number awaiting confirmation.
# Example: {"U1234abcd": 5} means user U1234 just logged an expense on
#          row 5 and hasn't confirmed if it's paid yet.
_pending: dict[str, int] = {}


def set_pending(user_id: str, row_number: int) -> None:
    """Remember that this user needs to confirm a specific row."""
    _pending[user_id] = row_number


def get_pending(user_id: str) -> int | None:
    """
    Check if a user has a pending confirmation.
    Returns the row number if yes, None if no.
    """
    return _pending.get(user_id)


def clear_pending(user_id: str) -> None:
    """Forget the pending confirmation (after user responds yes/no)."""
    _pending.pop(user_id, None)
