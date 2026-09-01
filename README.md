# LedgerLine — Bangkok Trip Expense Bot

## What this does

A LINE chatbot that logs trip expenses to a Google Sheet using AI:

1. **You text**: `"7am breakfast 150 baht"` (English, Thai, or mix)
2. **Gemini AI parses it** → extracts description (in Thai) + amount
3. **Writes to Google Sheets** → fills the correct row with smart date handling
4. **Asks**: "Paid already? (yes/no)" → updates the status column

## Architecture (Agentic AI concepts)

```
LINE Message → Flask Webhook (Orchestrator)
                    ├── Gemini Flash (Tool: Language Understanding)
                    ├── Google Sheets API (Tool: Data Storage)
                    └── In-memory state (Memory: Confirmation Tracking)
```

This project demonstrates three core agentic AI patterns:
- **Tool Use**: The bot calls Gemini for reasoning and Sheets for actions
- **Orchestrator Pattern**: `app.py` decides which tool to use and when
- **State Tracking**: The bot remembers which expenses need confirmation

---

## Setup

### Prerequisites
- Python 3.10+
- A LINE Messaging API channel (from Day 1)
- A Google account
- ngrok (for local development)

### Step 1: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Get a Gemini API key (free)

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **"Create API key"**
4. Copy the key

Add it to your `.env` file:
```
GEMINI_API_KEY=your_key_here
```

### Step 3: Set up Google Sheets API

This is the most involved step — follow carefully:

#### 3a. Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click the project dropdown (top-left) → **"New Project"**
3. Name it **"LedgerLine"** → Create

#### 3b. Enable the Google Sheets API
1. In your new project, go to **APIs & Services → Library**
2. Search for **"Google Sheets API"**
3. Click it → **Enable**

#### 3c. Create a Service Account
1. Go to **IAM & Admin → Service Accounts**
2. Click **"Create Service Account"**
3. Name: `ledgerline-bot` → Create and Continue
4. Skip the role/access steps (click Done)
5. Click on the service account you just created
6. Go to the **Keys** tab → **Add Key → Create new key → JSON**
7. A `.json` file will download — rename it to `credentials.json`
8. Move it to this project folder (same folder as `app.py`)

> ⚠️ **Security**: Never commit `credentials.json` to git! It's already in `.gitignore`.

#### 3d. Share your Google Sheet
1. Open the `credentials.json` file and find the `"client_email"` field
   (it looks like `ledgerline-bot@ledgerline-xxxxx.iam.gserviceaccount.com`)
2. Open your Google Sheet in the browser
3. Click **Share** → paste the service account email → give **Editor** access
4. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

Add to your `.env`:
```
GOOGLE_SHEET_ID=your_sheet_id_here
```

### Step 4: Test each component

Test the LLM parser first (doesn't need Sheets):
```bash
python test_parser.py
```

Then test the Sheets connection:
```bash
python test_sheets.py
```

### Step 5: Run the bot

```bash
python app.py
```

In another terminal:
```bash
ngrok http 5000
```

Update your LINE webhook URL to the new ngrok URL + `/callback`.

---

## Google Sheet Format

Your sheet should have these columns (in Thai):

| Column | Header | Description |
|--------|--------|-------------|
| A | รายการที่ | Item number (pre-numbered 1-30) |
| B | วันที่ | Date (DD/MM/YYYY, only on first entry per day) |
| C | จำนวนเงินที่จ่าย | Amount paid |
| D | รายการ | Item description (in Thai) |
| E | สถานะ | Status: จ่าย (paid) / รอดำเนินการ (pending) |
| F | หลักฐาน | Evidence type (v2 — photo classification) |

---

## Configuration

All settings are in `.env` (see `.env.example` for the template):

| Variable | Required | Description |
|----------|----------|-------------|
| `LINE_CHANNEL_SECRET` | ✅ | From LINE Developers Console |
| `LINE_CHANNEL_ACCESS_TOKEN` | ✅ | From LINE Developers Console |
| `GEMINI_API_KEY` | ✅ | From [AI Studio](https://aistudio.google.com/apikey) |
| `GOOGLE_SHEETS_ID` | ✅ | From your Google Sheet URL |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | ❌ | Default: `credentials.json` |
| `GOOGLE_SHEET_TAB` | ❌ | Default: `Sheet1` |

---

## Project Roadmap

- [x] **Day 1**: Echo bot (webhook pipe works)
- [x] **Day 2**: AI expense parsing + Google Sheets logging + status confirmation
- [ ] **v2**: Photo receipt classification (auto-detect receipt type from images)
- [ ] **v2**: Multi-turn state tracking (persistent memory across restarts)
- [ ] **v2**: Multi-user support (per-user sheets or "logged by" column)
