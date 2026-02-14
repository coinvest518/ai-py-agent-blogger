# Google Sheets Integration

## Overview

The AI agent now uses **Google Sheets** as a centralized cloud storage system for:
1. **Social Media Posts** - Track all posts across Twitter, Facebook, LinkedIn, Instagram, Telegram
2. **Crypto Tokens** - Track tokens mentioned in Telegram messages
3. **Duplicate Prevention** - Search history before posting
4. **Analytics** - View engagement, trends, and performance

## Features

### 📊 Two Spreadsheets Created Automatically

#### 1. Posts Tracking Spreadsheet
Columns:
- **Timestamp** - When post was created
- **Platform** - twitter, facebook, linkedin, instagram, telegram
- **Content Preview** - First 100 characters
- **Post ID** - Platform-specific ID
- **Image URL** - If image was posted
- **Engagement** - Likes, shares, comments (updated later)
- **Status** - posted, failed, pending
- **Hash** - Content hash for duplicate detection
- **Full Content** - Complete post text

#### 2. Crypto Tokens Spreadsheet
Columns:
- **Timestamp** - When token was mentioned
- **Symbol** - Token symbol (BTC, ETH, SOL, etc.)
- **Name** - Full name (Bitcoin, Ethereum, etc.)
- **Contract** - Token contract address
- **Chain** - Blockchain network (ethereum, solana, etc.)
- **Source** - Where mentioned (telegram_outbound, telegram_inbound, etc.)
- **Price** - Current price (if available)
- **Market Cap** - Market capitalization
- **Mentions** - Number of times mentioned
- **Sentiment** - positive, negative, neutral
- **Notes** - Additional context

## Setup

### 1. Connect Google Sheets Account (Already Done ✅)
Your Google Sheets account is already connected:
- **Account ID**: `ca_d2PZO0JrpWtW`
- **Status**: ACTIVE

### 2. Spreadsheet IDs

The agent DOES NOT create Google Sheets automatically. You must create the spreadsheets yourself (or via Composio Playground) and add their IDs to `.env`.

Required `.env` keys (must be present for Sheets features to work):
```env
GOOGLESHEETS_POSTS_SPREADSHEET_ID=1ABC...XYZ
GOOGLESHEETS_TOKENS_SPREADSHEET_ID=1DEF...UVW
GOOGLESHEETS_ACCOUNT_ID=ca_d2PZO0JrpWtW
```

If a spreadsheet ID is missing the agent will **not** attempt creation — it will simply skip saving and log a warning. This is intentional to ensure the system only writes to spreadsheets you explicitly manage.

Alternatively, you can manually create spreadsheets and add their IDs to `.env`:
```env
GOOGLESHEETS_POSTS_SPREADSHEET_ID=1ABC...XYZ
GOOGLESHEETS_TOKENS_SPREADSHEET_ID=1DEF...UVW
```

### 3. Run Application

Start the agent:
```bash
python main.py
```

The startup log will show:
```
✅ Google Sheets already configured
OR
📝 Creating spreadsheets...
✅ Posts spreadsheet created: 1ABC...XYZ
✅ Tokens spreadsheet created: 1DEF...UVW
```

## Usage

### Automatic Post Tracking

Every time the agent posts to social media:
1. **Content is checked** for duplicates in Google Sheets
2. **Post is saved** to the Posts spreadsheet
3. **Tokens are extracted** from the content
4. **Tokens are saved** to the Tokens spreadsheet

### Token Extraction

The system automatically extracts crypto tokens from:
- **Telegram messages** (both sent and received)
- **Tweet content**
- **Image captions**

Supported formats:
- `$BTC` - Dollar sign format
- `$ETH` - Dollar sign format
- `BTCUSDT` - Trading pair format
- `SOLUSDT` - Trading pair format

### Search and Prevent Duplicates

Before posting, the agent:
1. Searches Google Sheets for similar content
2. Compares content hashes (ignores URLs, hashtags)
3. If duplicate found within 30 days → Adds timestamp to make unique
4. Records new post to Sheets

### Manual Access

You can view and edit data directly in Google Sheets:
1. Open [Google Sheets](https://sheets.google.com/)
2. Find your spreadsheets by title:
   - "AI Agent Posts Tracking"
   - "AI Agent Crypto Tokens"
3. View, filter, edit data as needed

## Testing

Test the integration:
```bash
python tests/test_google_sheets_integration.py
```

Expected output:
```
🧪 Testing Token Extraction:
✅ 'Check out $BTC and $ETH today!' -> ['BTC', 'ETH']
✅ 'BTCUSDT is pumping! $SOL too' -> ['BTC', 'SOL']

📊 Testing Google Sheets Initialization:
✅ Posts Sheet ID: 1ABC...XYZ
✅ Tokens Sheet ID: 1DEF...UVW

💾 Testing Token Save:
✅ Token saved successfully

📝 Testing Post Save:
✅ Post saved successfully
```

## Monitoring

### Real-time Dashboard

The dashboard (`http://localhost:8000`) shows:
- Agent activity in real-time
- "Checking for duplicates in Google Sheets..."
- "Recording post to Google Sheets..."
- "Extracted 2 crypto tokens from message"

### Logs

Check logs for token extraction:
```
[DEBUG] Tracked token BTC from Telegram message
[DEBUG] Tracked token ETH from Telegram photo caption
[INFO] Post saved to Google Sheets: tweet_123456
```

## API Functions

### Save Post
```python
from src.agent.sheets_agent import save_post_to_sheets

save_post_to_sheets(
    content="My crypto post with $BTC",
    platform="twitter",
    post_id="123456",
    image_url="https://...",
    content_hash="abc123"
)
```

### Save Token
```python
from src.agent.sheets_agent import save_token_to_sheets

save_token_to_sheets(
    symbol="BTC",
    name="Bitcoin",
    source="telegram_outbound",
    price="45000",
    notes="Mentioned in market update"
)
```

### Search Posts
```python
from src.agent.sheets_agent import search_posts_in_sheets

# Find all Twitter posts from last 7 days
posts = search_posts_in_sheets(platform="twitter", days_ago=7)

# Find specific post by hash
posts = search_posts_in_sheets(content_hash="abc123")
```

### Search Tokens
```python
from src.agent.sheets_agent import search_tokens_in_sheets

# Find all BTC mentions
tokens = search_tokens_in_sheets(symbol="BTC")

# Find tokens from Telegram
tokens = search_tokens_in_sheets(source="telegram_outbound")
```

### Extract Tokens
```python
from src.agent.sheets_agent import extract_crypto_tokens_from_text

text = "Check out $BTC and $ETH! SOLUSDT is pumping."
tokens = extract_crypto_tokens_from_text(text)
# Returns: ['BTC', 'ETH', 'SOL']
```

## Architecture

### Integration Points

1. **duplicate_detector.py**
   - Calls `search_posts_in_sheets()` to check duplicates
   - Calls `save_post_to_sheets()` after recording locally

2. **telegram_agent.py**
   - `send_message()` extracts tokens and saves to Sheets
   - `send_photo()` extracts tokens from caption and saves

3. **graph.py**
   - All posting nodes call `record_post()` which saves to Sheets
   - Real-time status shows "Saving to Google Sheets..."

4. **api.py**
   - `startup()` initializes Google Sheets on application start
   - Creates spreadsheets if they don't exist

### Data Flow

```
User Request → Agent Workflow → Generate Content
                                       ↓
                              Check Duplicates (Sheets)
                                       ↓
                              Post to Platform (Twitter, etc.)
                                       ↓
                              Save to Sheets (Posts + Tokens)
                                       ↓
                              Update Dashboard (Real-time)
```

## Benefits

### 1. Duplicate Prevention
- **Before**: Posts could be duplicated if local JSON was lost
- **After**: Cloud storage ensures global duplicate detection

### 2. Crypto Token Tracking
- **Before**: Telegram tokens were not tracked
- **After**: Every $BTC mention is saved with timestamp and source

### 3. Analytics
- **Before**: No easy way to view post history
- **After**: Google Sheets provides familiar interface for analysis

### 4. Manual Control
- **Before**: Had to edit JSON files manually
- **After**: Edit posts directly in Google Sheets

### 5. Cloud Backup
- **Before**: Local files could be lost
- **After**: All data synced to Google Drive

### 6. AI Memory
- **Before**: Agent had no memory of past posts
- **After**: Agent can search Sheets for context and trends

## Troubleshooting

### Spreadsheets Not Created
1. Check `.env` has `GOOGLESHEETS_ACCOUNT_ID=ca_d2PZO0JrpWtW`
2. Verify account is ACTIVE in Composio dashboard
3. Run test: `python tests/test_google_sheets_integration.py`

### Token Extraction Not Working
1. Check log level: `export LOG_LEVEL=DEBUG`
2. Look for `[DEBUG] Tracked token BTC from...` messages
3. Verify message contains `$BTC` or `BTCUSDT` format

### Posts Not Saving
1. Check if `GOOGLESHEETS_POSTS_SPREADSHEET_ID` is set in `.env`
2. Verify spreadsheet exists and is accessible
3. Check logs for errors: `grep "Google Sheets" logs.txt`

### Permission Denied
1. Reconnect Google Sheets account in Composio
2. Ensure OAuth scopes include:
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/drive.file`

## Next Steps

1. ✅ **Test Integration**: Run test suite to verify everything works
2. ✅ **Run Agent**: Start agent and watch real-time dashboard
3. ✅ **Check Sheets**: Open Google Sheets to see data flowing in
4. ⏳ **Add Analytics**: Create charts in Sheets for engagement trends
5. ⏳ **Token Alerts**: Set up notifications for specific token mentions
6. ⏳ **Export Reports**: Use Sheets data for weekly/monthly reports

## Support

If you encounter issues:
1. Check logs for errors
2. Run integration test
3. Verify Google Sheets account connection
4. Check spreadsheet IDs in `.env`
5. Ensure proper OAuth permissions

---

**Status**: ✅ Fully Implemented and Ready to Use

**Last Updated**: $(date)

**Version**: 1.0.0
