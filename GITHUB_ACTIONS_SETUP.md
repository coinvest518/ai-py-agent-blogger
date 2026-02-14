# GitHub Actions Deployment Guide

This guide shows how to deploy the FDWA AI Agent using **GitHub Actions** instead of Railway or other servers.

## ✅ Advantages of GitHub Actions

| Feature | Benefit |
|---------|---------|
| **No server management** | Push code and forget |
| **Free tier** | 2,000 minutes/month for public repos |
| **Scheduled runs** | Cron-based automation (every 2 hours) |
| **Built-in secrets** | Secure API key management |
| **Logs & artifacts** | Easy debugging |

## 🚀 Quick Setup (10 minutes)

### Step 1: Add Secrets to GitHub

1. Go to your repo on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each:

#### Required Secrets:
| Secret Name | Description |
|-------------|-------------|
| `MISTRAL_API_KEY` | Mistral AI for content generation |
| `HF_TOKEN` | Hugging Face for image generation (FREE) |
| `LANGSMITH_API_KEY` | LangSmith tracing |
| `LANGSMITH_WORKSPACE_ID` | LangSmith workspace |
| `COMPOSIO_API_KEY` | Composio platform integration |

#### Platform Secrets (add for each platform you use):

**Facebook:**
- `FACEBOOK_ACCOUNT_ID`
- `FACEBOOK_PAGE_ID`

**LinkedIn:**
- `LINKEDIN_USER_ID`
- `LINKEDIN_AUTHOR_URN`
- `LINKEDIN_ACCESS_TOKEN`

**Instagram:**
- `INSTAGRAM_ACCOUNT_ID`
- `INSTAGRAM_USER_ID`

**Telegram:**
- `TELEGRAM_ACCOUNT_ID`
- `TELEGRAM_AUTH_CONFIG_ID`
- `TELEGRAM_ENTITY_ID`
- `TELEGRAM_GROUP_CHAT_ID`
- `TELEGRAM_BOT_TOKEN`

**Twitter:**
- `TWITTER_ACCOUNT_ID`
- `TWITTER_ENTITY_ID`

**Image Upload:**
- `IMGBB_API_KEY`

**Search APIs:**
- `SERPAPI_ACCOUNT_ID`
- `TAVILY_ACCOUNT_ID`

**Google Sheets:**
- `GOOGLESHEETS_ACCOUNT_ID`
- `GOOGLESHEETS_USER_ID`
- `GOOGLESHEETS_ACCESS_TOKEN`
- `GOOGLESHEETS_REFRESH_TOKEN`
- `GOOGLESHEETS_POSTS_SPREADSHEET_ID`
- `GOOGLESHEETS_TOKENS_SPREADSHEET_ID`

**Blog/Email:**
- `BLOGGER_EMAIL`
- `GMAIL_CONNECTED_ACCOUNT_ID`
- `GMAIL_USER_ID`
- `GMAIL_ACCESS_TOKEN`
- `GMAIL_REFRESH_TOKEN`

### Step 2: Push to GitHub

```bash
cd ai-agent
git add .
git commit -m "Add GitHub Actions scheduler"
git push origin main
```

### Step 3: Done! Agent runs every 2 hours automatically.

## ⏰ Schedule

The agent runs every **2 hours** (12 times per day).

To change: Edit `.github/workflows/scheduler.yml` line 9:
```yaml
- cron: '0 */2 * * *'  # Every 2 hours
```

**Other schedules:**
| Schedule | Cron |
|----------|------|
| Every hour | `0 * * * *` |
| Every 4 hours | `0 */4 * * *` |
| Every 6 hours | `0 */6 * * *` |
| 3x daily (9am, 1pm, 5pm UTC) | `0 9,13,17 * * *` |

## 🎮 Manual Runs

1. Go to **Actions** tab in your GitHub repo
2. Click **Run FDWA AI Agent**
3. Click **Run workflow** → **Run workflow**

## 📊 Monitoring

- **View logs:** Actions → Select a run → Click job name
- **LangSmith traces:** https://smith.langchain.com

## 🔧 Troubleshooting

### "Secret not found" errors
- Ensure all secrets are added in Settings → Secrets
- Secret names are case-sensitive

### Agent failures
- Check Actions logs for detailed errors
- Verify API keys in Composio dashboard
- Check LangSmith traces

## 📁 Workflow Files

```
.github/workflows/
├── scheduler.yml          # ← Agent runs every 2 hours
├── unit-tests.yml         # CI tests on push
└── integration-tests.yml  # Daily integration tests
```
