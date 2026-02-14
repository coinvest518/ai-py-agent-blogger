# Twitter/Composio 403 Error Fix Guide

## The Problem
**Error**: `403 Client Forbidden - client-not-enrolled`

**Cause**: Your Twitter app is NOT attached to a Project. Twitter API v2 requires all apps to be inside a Project.

---

## Solution: Attach App to Project (5 minutes)

### Step 1: Go to Twitter Developer Portal
**URL**: https://developer.twitter.com/en/portal/dashboard

### Step 2: Create a Project (if you don't have one)
1. Click **"+ Add Project"** button (under Elevated section)
2. Give your project a name: "YieldBot AI Agent"
3. Describe use case: "AI-powered social media automation for crypto/DeFi content"
4. Click **Next**

### Step 3: Add Your App to the Project
**Option A - During Project Creation:**
- After creating project, you'll be asked to add an app
- Select your existing app from the dropdown
- Click **Add App**

**Option B - After Project Created:**
- Find your project in the dashboard
- Click on the project name
- Look for "Apps" section
 - Click **"Add App"**
- Select your app from the list
- Click **Add to Project**

### Step 4: Get New Keys (CRITICAL!)
Once app is attached to project:
1. Go to project → Your App → **"Keys and tokens"** tab
2. **Regenerate** the keys (old keys won't work!)
   - Bearer Token (regenerate)
   - Access Token & Secret (regenerate)
   - API Key & Secret (regenerate if needed)
3. **SAVE THE NEW KEYS IMMEDIATELY** (shown only once)

### Step 5: Update Composio Connection
**URL**: https://app.composio.dev/

1. Find Twitter in your connections
2. Click **"Reconnect"** or **"Configure"**
3. It will redirect to Twitter
4. Authorize again (this will use the new project-attached app)
5. Done! ✅

---

## Verification

Run this to check if Composio Twitter connection works:

```bash
.\.venv\Scripts\python.exe check_composio_connections.py
```

Look for Twitter status - should say "ACTIVE" now.

---

## Alternative: Use Composio's Default Twitter (Easiest!)

If you don't want to manage your own Twitter app:

1. Go to https://app.composio.dev/
2. Find Twitter in toolkits
3. Use Composio's default OAuth connection (no custom app needed!)
4. Just click "Connect Twitter" and authorize
5. Done! Composio handles all the complexity

---

## What Changed in 2024-2026?

Twitter made API v2 stricter:
- ❌ **Old**: Standalone apps worked fine
- ✅ **New**: All apps MUST be in a Project
- Reason: Better organization and access control

This is why your Composio connection suddenly stopped working or never worked for v2 endpoints.

---

## Still Having Issues?

Check these:

1. **App Permissions**: Make sure app has "Read and Write" permissions
   - Go to app → Settings → User authentication settings
   - Enable OAuth 2.0
   - Set permissions to Read + Write
   - Set callback URL: `https://backend.composio.dev/api/v1/auth-apps/add`

2. **Account Type**: Free tier works! But has limits:
   - 1,500 posts per month
   - 50 posts per 24 hours
   - Enough for your AI agent

3. **Composio Dashboard**: Check connection status
   - Green = Working
   - Red/Yellow = Need to reconnect

---

## Summary

✅ **Create or find a Project** in Twitter Developer Portal  
✅ **Attach your app** to that Project  
✅ **Regenerate all keys/tokens** from the project's app  
✅ **Reconnect in Composio** (it will use new project-based auth)  

That's it! Your Twitter posting will work after this.
