# Deployment Guide - Render

This guide walks you through deploying Open Bootstrap to Render using the `render.yaml` blueprint.

## Prerequisites

1. **Render Account**: Sign up at [render.com](https://render.com)
2. **GitHub Repository**: Your code must be pushed to GitHub
3. **Environment Variables**: Have your credentials ready (Supabase, API keys, etc.)

## Quick Deploy (Recommended)

### Step 1: Push to GitHub

```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

### Step 2: Create New Blueprint in Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml`
5. Click **"Apply"**

### Step 3: Configure Environment Variables

Render will create both services but they'll need environment variables. For each service:

#### Backend API Environment Variables

Go to your backend service → **Environment** tab and add:

**Required:**
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

**Optional (only if using fetch commands):**
```bash
GITHUB_TOKEN=ghp_...
GITLAB_TOKEN=glpat-...
OPENAI_API_KEY=sk-...  # If using OpenAI instead of Anthropic
```

#### Frontend Environment Variables

After the backend is deployed, get its URL (e.g., `https://openbootstrap-api.onrender.com`)

Go to your frontend service → **Environment** tab and update:

```bash
VITE_API_URL=https://openbootstrap-api.onrender.com
```

**Important:** After updating `VITE_API_URL`, you must **manually redeploy** the frontend for the change to take effect (click "Manual Deploy" → "Clear build cache & deploy").

### Step 4: Verify Deployment

1. **Backend**: Visit `https://your-backend.onrender.com/api/repos`
   - Should return `{"repos": [...]}`
   
2. **Frontend**: Visit `https://your-frontend.onrender.com`
   - Should load the React app and fetch PRs from backend

## Manual Deploy (Alternative)

If you prefer to create services manually instead of using the Blueprint:

### Backend Service

1. **New Web Service**
2. **Connect Repository**
3. **Configure:**
   - Name: `openbootstrap-api`
   - Runtime: `Python 3`
   - Build Command: `pip install uv && uv sync --frozen`
   - Start Command: `uv run uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
   - Plan: Free (or Starter for production)
4. **Add Environment Variables** (see above)

### Frontend Service

1. **New Static Site**
2. **Connect Repository**
3. **Configure:**
   - Name: `openbootstrap`
   - Build Command: `cd frontend && npm install && npm run build`
   - Publish Directory: `frontend/dist`
   - Add environment variable: `VITE_API_URL=<your-backend-url>`

## Production Checklist

Before going live, verify:

- [ ] All environment variables are set correctly
- [ ] Backend `/api/repos` endpoint returns data
- [ ] Frontend loads and can fetch data from backend
- [ ] CORS is working (no console errors)
- [ ] Database connection is stable
- [ ] Services are on Starter plan (no cold starts, always available)

## Professional Plan Benefits

Since you're on the Professional plan, you get:

- ✅ **No cold starts**: Services are always running (instant response)
- ✅ **More resources**: Better CPU and memory allocation
- ✅ **Custom domains**: Free SSL certificates included
- ✅ **Priority support**: Faster response times
- ✅ **Better performance**: Higher request limits and faster builds
- ✅ **Team collaboration**: Multiple team members can access the dashboard

Your services are configured with the **Starter** instance type which is included in your plan.

## Using Custom Domains

After upgrading to paid plan:

1. Go to service → **Settings** → **Custom Domain**
2. Add your domain (e.g., `api.yourdomain.com` for backend)
3. Update frontend `VITE_API_URL` to use custom domain
4. Redeploy frontend

## Troubleshooting

### Backend won't start

**Check logs:** Dashboard → Service → Logs

Common issues:
- Missing environment variables (check `SUPABASE_URL`, `SUPABASE_KEY`, etc.)
- Database connection failed (verify `DATABASE_URL`)
- `uv sync` failed (check `pyproject.toml` and `uv.lock` are committed)

### Frontend shows blank page

**Check browser console** for errors:

- `CORS error`: Backend CORS is already set to allow all origins, this shouldn't happen
- `API fetch failed`: Check that `VITE_API_URL` is set correctly and backend is running
- `404 errors`: Verify routes are configured (should be automatic in `render.yaml`)

### Cold starts (if any)

With your Professional plan and Starter instances, you shouldn't experience cold starts. If you do:
- Verify the service is on "Starter" plan (not "Free")
- Check Settings → Instance Type

### Environment variable changes not taking effect

Frontend environment variables (`VITE_*`) are **baked into the build** at build time.

To apply changes:
1. Update environment variable in Render Dashboard
2. Click **Manual Deploy** → **Clear build cache & deploy**

## Monitoring & Logs

- **Logs**: Dashboard → Service → Logs (real-time)
- **Metrics**: Dashboard → Service → Metrics (CPU, RAM, requests)
- **Health Checks**: Backend has automatic health check at `/api/repos`

## Cost Estimate (Professional Plan)

With your Professional plan subscription:
- Backend: Starter instance (included in plan)
- Frontend: Static site (free)
- **Total: Covered by your Professional plan subscription**

Note: Your Professional plan includes multiple services, so you can deploy both backend and frontend without additional per-service charges.

## Environment Variable Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SUPABASE_URL` | ✅ | Your Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | ✅ | Supabase anon/public key | `eyJhbG...` |
| `DATABASE_URL` | ✅ | Direct Postgres connection | `postgresql://postgres:...` |
| `LLM_PROVIDER` | ✅ | LLM provider to use | `anthropic` or `openai` |
| `LLM_MODEL` | ✅ | Model name | `claude-3-5-sonnet-20241022` |
| `ANTHROPIC_API_KEY` | ✅* | Anthropic API key | `sk-ant-...` |
| `OPENAI_API_KEY` | ⚠️ | OpenAI API key (if using OpenAI) | `sk-...` |
| `GITHUB_TOKEN` | ⚠️ | GitHub PAT (only for fetch command) | `ghp_...` |
| `GITLAB_TOKEN` | ⚠️ | GitLab PAT (only for fetch command) | `glpat-...` |
| `VITE_API_URL` | ✅ | Backend API URL (frontend only) | `https://your-api.onrender.com` |

✅ = Required  
⚠️ = Optional (depends on usage)  
✅* = Required if using Anthropic

## Next Steps

After successful deployment:

1. **Test the API**: Use the Swagger docs at `https://your-backend.onrender.com/docs`
2. **Fetch PRs**: SSH into your backend or use Render Shell to run:
   ```bash
   uv run python main.py fetch facebook/react --limit 100
   ```
3. **Classify PRs**: 
   ```bash
   uv run python main.py classify facebook/react --limit 50
   ```
4. **Browse in UI**: Open your frontend URL and explore!

## Support

- **Render Docs**: https://render.com/docs
- **Render Community**: https://community.render.com
- **This Project**: [Open an issue on GitHub]

---

**Deployment created with `render.yaml` blueprint** ✨

