# Alexandria Deployment Guide

This guide walks through deploying Alexandria to Railway with Cloudflare R2 for file storage.

## Prerequisites

1. [Railway account](https://railway.app/) (free tier works)
2. [Cloudflare account](https://cloudflare.com/) (for R2 storage)
3. [GitHub account](https://github.com/) (Railway deploys from GitHub)

## Step 1: Prepare Your Repository

1. Create a new GitHub repository
2. Push the Alexandria code:

```bash
cd alexandria
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/alexandria.git
git push -u origin main
```

## Step 2: Set Up Cloudflare R2

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → R2
2. Click "Create bucket"
   - Name: `alexandria-files`
   - Location: Choose closest to your users
3. Go to "Manage R2 API Tokens" → "Create API Token"
   - Permissions: Object Read & Write
   - Specify bucket: `alexandria-files`
4. Save the credentials:
   - Access Key ID
   - Secret Access Key
   - Account ID (for endpoint URL)

Your R2 endpoint will be: `https://<account-id>.r2.cloudflarestorage.com`

## Step 3: Deploy to Railway

### 3.1 Create the Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `alexandria` repository

### 3.2 Add PostgreSQL with pgvector

1. In your project, click "New" → "Database" → "PostgreSQL"
2. Railway automatically creates and connects the database
3. The `DATABASE_URL` is auto-injected into services
4. **Enable pgvector extension** — Railway's PostgreSQL includes pgvector. The migration will enable it automatically on first run.

### 3.3 Deploy Backend

1. Click "New" → "GitHub Repo" → Select `alexandria`
2. Configure the service:
   - Root Directory: `backend`
   - Click "Add Variables" and set:

```
JWT_SECRET=<generate with: openssl rand -hex 32>
ENCRYPTION_KEY=<generate with: openssl rand -hex 32>
DEBUG=false
CORS_ORIGINS=["https://alexandria-frontend-production.up.railway.app"]
R2_ACCESS_KEY_ID=<your R2 access key>
R2_SECRET_ACCESS_KEY=<your R2 secret key>
R2_BUCKET_NAME=alexandria-files
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
```

3. Generate a domain:
   - Settings → Networking → Generate Domain
   - Note the URL (e.g., `alexandria-backend-production.up.railway.app`)

### 3.4 Deploy Frontend

1. Click "New" → "GitHub Repo" → Select `alexandria` again
2. Configure the service:
   - Root Directory: `frontend`
   - Click "Add Variables":

```
NEXT_PUBLIC_API_URL=https://alexandria-backend-production.up.railway.app
```

3. Add build arguments (in Settings → Build):
   - `NEXT_PUBLIC_API_URL=https://alexandria-backend-production.up.railway.app`

4. Generate a domain:
   - Settings → Networking → Generate Domain

### 3.5 Update CORS

Go back to the backend service and update `CORS_ORIGINS` with the actual frontend URL:

```
CORS_ORIGINS=["https://alexandria-frontend-production.up.railway.app"]
```

## Step 4: Initialize the Database

The database migrations run automatically on deploy. Your first visit to the frontend will show the setup page.

### Embedding Model Download

The first time you add an article, the embedding model (~420MB) will be downloaded from Hugging Face. This happens once per deployment and may take a few minutes.

### Backfill Embeddings (if upgrading)

If you're upgrading an existing installation, run the embedding backfill to generate embeddings for existing articles:

```bash
# In Railway shell or local environment
cd backend
python scripts/backfill_embeddings.py
```

This generates semantic search embeddings for all articles that don't have them.

## Step 5: Set Up Backups (Optional but Recommended)

### Option A: Railway Cron Job

1. In your backend service, go to Settings → Cron
2. Add a cron job:
   - Schedule: `0 3 * * *` (daily at 3 AM)
   - Command: `./scripts/backup.sh`

### Option B: Manual Backups

SSH into Railway and run:
```bash
./scripts/backup.sh
```

### Restore from Backup

```bash
./scripts/restore.sh alexandria_backup_20240115_030000.sql.gz
```

## Step 6: Custom Domain (Optional)

1. In your frontend service: Settings → Networking → Custom Domain
2. Add your domain (e.g., `alexandria.yourdomain.com`)
3. Add the CNAME record to your DNS provider
4. Update `CORS_ORIGINS` in backend to include the new domain

## Cost Estimate

| Service | Cost |
|---------|------|
| Railway (backend + frontend + postgres) | ~$5-15/month |
| Cloudflare R2 (storage) | ~$0.015/GB/month |
| **Total** | **~$5-15/month** |

Railway's free tier includes $5/month credit, so you may pay nothing initially.

## Troubleshooting

### Backend won't start
- Check logs in Railway dashboard
- Verify DATABASE_URL is set (should be automatic)
- Run migrations: `alembic upgrade head`

### Frontend can't connect to backend
- Check CORS_ORIGINS includes the frontend URL
- Verify NEXT_PUBLIC_API_URL is correct
- Check browser console for errors

### Database connection errors
- PostgreSQL might still be starting up
- Check Railway logs for the database service

### R2 upload errors
- Verify R2 credentials are correct
- Check bucket name matches
- Ensure bucket permissions allow write

### Semantic search not working
- Check pgvector extension is enabled: `SELECT * FROM pg_extension WHERE extname = 'vector';`
- Run migrations: `alembic upgrade head`
- Run embedding backfill: `python scripts/backfill_embeddings.py`
- Check logs for embedding model download errors

### Slow first article processing
- First article triggers ~420MB model download from Hugging Face
- Subsequent articles are fast (model cached in memory)

## Security Checklist

- [ ] JWT_SECRET is unique and random (32+ bytes)
- [ ] ENCRYPTION_KEY is unique and random (32+ bytes)
- [ ] DEBUG is set to `false` in production
- [ ] CORS_ORIGINS only includes your frontend URL
- [ ] R2 bucket is private (default)
- [ ] Database is not publicly accessible (Railway default)
- [ ] pgvector extension is enabled (check with `\dx` in psql)

## Monitoring

Railway provides built-in:
- Deployment logs
- Resource usage graphs
- Alerts for service crashes

Check the Metrics tab in your Railway dashboard.

## Updates

To deploy updates:
1. Push to your GitHub repository
2. Railway automatically deploys changes

To roll back:
1. Go to Deployments in Railway
2. Click on a previous deployment
3. Click "Rollback"
