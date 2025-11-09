# FDWA Social Media Agent - Deployment Guide

## Railway Deployment

### 1. Push to GitHub
```bash
git add .
git commit -m "Add UI and scheduler for Railway deployment"
git push
```

### 2. Deploy on Railway

1. Go to [Railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select: `coinvest518/ai-studio-agent`
4. Railway will auto-detect Python

### 3. Configure Railway

**Start Command:**
```
python main.py
```

**Environment Variables:**
Add all these in Railway dashboard (use your actual values from .env file):

```
MISTRAL_API_KEY=your_mistral_key_here
GOOGLE_AI_API_KEY=your_google_key_here
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_TRACING=true
COMPOSIO_API_KEY=your_composio_key_here
LANGSMITH_PROJECT=fdwa-multi-agent
LANGSMITH_WORKSPACE_ID=your_workspace_id_here
FACEBOOK_ACCOUNT_ID=your_facebook_account_id
FACEBOOK_PAGE_ID=your_facebook_page_id
PORT=8000
```

### 4. Access Your App

Once deployed, Railway gives you a URL like:
```
https://your-app.railway.app
```

Visit it to see your control panel!

## Features

### Automatic Posting
- Runs every 6 hours automatically
- No manual intervention needed

### Manual Control
- Visit your Railway URL
- Click "Run Agent Now" to post immediately
- See last run status and results

### What It Does

1. **Research** - Finds trending topics
2. **Generate** - Creates tweet with AI
3. **Image** - Generates art image
4. **Post** - Posts to Twitter & Facebook
5. **Comment** - Adds company URL to Facebook post

## Monitoring

- Check Railway logs for detailed execution
- View LangSmith dashboard for traces
- UI shows last run status

## Troubleshooting

**Agent not running?**
- Check Railway logs
- Verify all environment variables are set
- Ensure PORT is set to 8000

**UI not loading?**
- Check Railway deployment status
- Verify main.py is being executed
- Check logs for errors

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py

# Visit
http://localhost:8000
```
