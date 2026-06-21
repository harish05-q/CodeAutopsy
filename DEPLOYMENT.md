# CodeAutopsy Deployment Guide (Vercel + Render Free Tiers)

This document outlines the step-by-step instructions to deploy the CodeAutopsy platform for free. We deploy the **Next.js frontend to Vercel** and the **FastAPI backend to Render**.

---

## Step 1: Push Your Code to GitHub

1. Initialize a Git repository in the root directory if not already done:
   ```bash
   git init
   ```
2. Create a `.gitignore` in the root folder to exclude virtual environments, cache, and compiled index files:
   ```text
   # Python
   backend/venv/
   __pycache__/
   *.pyc
   .env
   codeautopsy.db
   analysis/

   # Node
   node_modules/
   .next/
   dist/
   .env.local
   ```
3. Commit and push the code to a new public or private GitHub repository:
   ```bash
   git add .
   git commit -m "feat: complete production-quality CodeAutopsy MVP"
   git remote add origin https://github.com/your-username/codeautopsy.git
   git branch -M main
   git push -u origin main
   ```

---

## Step 2: Deploy the FastAPI Backend to Render (Free Tier)

Render allows you to host Python ASGI applications for free.

1. Go to [Render](https://render.com/) and sign in using your GitHub account.
2. Click **New +** in the top right and select **Web Service**.
3. Choose **Connect a repository** and connect your `codeautopsy` repo.
4. Configure the Web Service settings:
   - **Name**: `codeautopsy-backend` (or a custom name)
   - **Region**: Select the region closest to you
   - **Branch**: `main`
   - **Language**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r backend/requirements.txt
     ```
   - **Start Command**:
     ```bash
     PYTHONPATH=. uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
     ```
5. Click **Advanced** to add **Environment Variables**:
   - `DATABASE_URL`: `sqlite+aiosqlite:////tmp/codeautopsy.db` (Render's free tier local disk is read-only in some directories, but `/tmp` is always writable).
   - `ANALYSIS_DIR`: `/tmp/analysis`
   - `GROQ_API_KEY`: *(Optional. If left blank, users can paste their Groq keys in the frontend Settings page).*
   - `GROQ_MODEL`: `llama-3.3-70b-versatile`
6. Select the **Free Instance Type** and click **Create Web Service**.

Once deployed, copy your backend URL (e.g., `https://codeautopsy-backend.onrender.com`).

---

## Step 3: Deploy the Next.js Frontend to Vercel (Free Tier)

Vercel provides zero-configuration hosting for Next.js projects.

1. Go to [Vercel](https://vercel.com/) and log in using GitHub.
2. Click **Add New** and select **Project**.
3. Import your `codeautopsy` repository from the list.
4. Configure the Vercel deployment:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: `./` (Keep default)
5. Expand the **Environment Variables** section and add:
   - **Key**: `NEXT_PUBLIC_API_BASE`
   - **Value**: `https://your-render-backend-url.onrender.com/api/v1` *(Make sure to append `/api/v1` to the backend URL you copied from Render).*
6. Click **Deploy**.

Vercel will build the frontend and provide a production deployment URL (e.g., `https://codeautopsy.vercel.app`).

---

## Production Persistence Note
Render's Free Tier web services spin down after 15 minutes of inactivity, and the ephemeral `/tmp` disk is wiped whenever the instance restarts (wiping the analyzed repository case folders and history SQLite DB). 

For a permanent portfolio setup:
1. **SQLite Database**: Replace `DATABASE_URL` with a hosted cloud PostgreSQL database (e.g. using free tiers on [Neon](https://neon.tech/) or [Supabase](https://supabase.com/)).
2. **Analysis Artifacts**: Render supports persistent disk mounts (starting at $5/month), or the orchestrator's filesystem storage could be swapped with AWS S3 / Supabase Storage in the future.
