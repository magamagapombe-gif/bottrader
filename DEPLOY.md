# SuperEye — Deployment Guide
# Total cost: $0

## Step 1 — Supabase (database)

1. Go to https://supabase.com → New project (free tier)
2. Open SQL Editor → paste contents of `backend/schema.sql` → Run
3. Go to Project Settings → API
   - Copy "Project URL"  → this is SUPABASE_URL
   - Copy "service_role" key (NOT anon key) → this is SUPABASE_KEY

## Step 2 — Render (backend API)

1. Go to https://render.com → New Web Service
2. Connect your GitHub repo (push the `backend/` folder)
3. Settings:
   - Runtime: Python 3
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables (add all three):
   - SUPABASE_URL    = <from step 1>
   - SUPABASE_KEY    = <from step 1>
   - ADMIN_SECRET    = <make up a strong secret, e.g. a UUID>
5. Deploy. Copy the URL (e.g. https://supereye-api.onrender.com)
6. Update BACKEND_URL in `bot/supereye.py` with this URL

## Step 3 — Vercel (dashboard)

1. Go to https://vercel.com → New Project
2. Import the `dashboard/` folder
3. Environment Variables:
   - NEXT_PUBLIC_API_URL     = https://supereye-api.onrender.com
   - NEXT_PUBLIC_ADMIN_SECRET = <same secret from step 2>
4. Deploy. Your dashboard is live at https://your-project.vercel.app

## Step 4 — Build the exe (on Windows)

```cmd
pip install pyinstaller MetaTrader5 numpy requests
cd bot
pyinstaller supereye.spec
```
The exe appears in `bot/dist/SuperEye.exe`
Distribute this file to users (Google Drive, etc.)

## Step 5 — Issue your first token

1. Go to your Vercel dashboard URL
2. Log in with your ADMIN_SECRET as the token
3. Click Admin tab → Issue new token
   - Username: alice
   - Role: user
   - Expires: 30 (or blank for never)
4. Copy the generated token (shown once)
5. Send the token + SuperEye.exe to your user

## User flow

1. User downloads SuperEye.exe, double-clicks
2. Setup screen appears → enters token + Exness MT5 details
3. Token validates against backend
4. Main GUI opens → user picks pair, grid, capital, goal → Start Bot
5. You see them appear online in the dashboard within 60 seconds

## Revoking access

Dashboard → Admin tab → click Revoke next to the user.
Their bot will finish its current profit cycle then shut down gracefully.
This happens within 60 seconds of revocation.

## Notes

- Render free tier sleeps after 15min inactivity. The exe wakes it up
  on start (cold start ~30s). This is fine — only affects startup time.
- Upgrade to Render Starter ($7/mo) if you want no sleep delays.
- The exe stores credentials in %USERPROFILE%\.supereye\config.json
  Delete this file to reset / re-enter credentials.
- Campaign progress stored in %USERPROFILE%\.supereye\campaign.json
- History log in %USERPROFILE%\.supereye\history.json
