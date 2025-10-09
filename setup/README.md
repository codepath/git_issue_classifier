# Database Setup

This directory contains setup scripts for initializing the database schema.

## Overview

The `setup_database.py` script creates the Supabase schema required for the two-phase workflow:
1. **Phase 1 (Index)**: Store basic PR metadata
2. **Phase 2 (Enrichment)**: Add files, diffs, and linked issue data
3. **Phase 3 (Classification)**: Add LLM-generated classifications

## Prerequisites

1. **Supabase Project**: You must have a Supabase project created
2. **Environment Variables**: Set in `.env` file:
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_KEY` - Your Supabase API key (anon/public key)
   - `DATABASE_URL` - PostgreSQL connection string (see below)

## Schema Overview

### Two-Table Design

The database uses two main tables:
1. **`pull_requests`** - Stores PR data and enrichment
2. **`classifications`** - Stores LLM classifications (denormalized for easy export)

### Table: `pull_requests`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | BIGSERIAL | No | Primary key |
| `repo` | TEXT | No | Repository (e.g., "facebook/react") |
| `pr_number` | INTEGER | No | PR number |
| `title` | TEXT | No | PR title |
| `body` | TEXT | Yes | PR description |
| `merged_at` | TIMESTAMP | No | When PR was merged |
| `created_at` | TIMESTAMP | No | When PR was created |
| `files` | JSONB | Yes | Changed files with diffs (Phase 2) |
| `linked_issue` | JSONB | Yes | Linked issue details (Phase 2) |
| `issue_comments` | JSONB | Yes | Issue comments (Phase 2) |
| `enrichment_status` | TEXT | No | 'pending', 'success', 'failed' |
| `enrichment_attempted_at` | TIMESTAMP | Yes | Last enrichment attempt |
| `enrichment_error` | TEXT | Yes | Error message if failed |

**Constraints:**
- `UNIQUE(repo, pr_number)` - Prevents duplicate PRs

### Table: `classifications`

Self-contained table for LLM classifications, ready for export to Google Sheets.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | BIGSERIAL | No | Primary key |
| `pr_id` | BIGINT | No | Foreign key to pull_requests |
| `github_url` | TEXT | No | GitHub PR URL |
| `repo` | TEXT | No | Repository (e.g., "scalar/scalar") |
| `pr_number` | INTEGER | No | PR number |
| `title` | TEXT | No | PR title |
| `body` | TEXT | Yes | PR description |
| `merged_at` | TIMESTAMP | No | When PR was merged |
| `difficulty` | TEXT | Yes | 'trivial', 'easy', 'medium', 'hard' |
| `categories` | TEXT[] | Yes | Array of categories |
| `concepts_taught` | TEXT[] | Yes | Array of concepts |
| `prerequisites` | TEXT[] | Yes | Array of prerequisites |
| `reasoning` | TEXT | Yes | LLM's reasoning |
| `classified_at` | TIMESTAMP | No | When classified |

**Constraints:**
- `UNIQUE(pr_id)` - One classification per PR
- `FOREIGN KEY(pr_id)` - References pull_requests(id)
- `CHECK` constraint on difficulty (trivial, easy, medium, hard)

**Indexes on `pull_requests`:**
- `idx_enrichment_status` - Fast queries for PRs needing enrichment
- `idx_repo` - Filter by repository
- `idx_merged_at` - Sort by merge date

**Indexes on `classifications`:**
- `idx_classifications_difficulty` - Filter by difficulty
- `idx_classifications_repo` - Filter by repository
- `idx_classifications_merged_at` - Sort by merge date

## Usage

### Step 1: Get DATABASE_URL

Before running the setup script, you need to add your PostgreSQL connection string to `.env`:

1. Go to **Supabase Dashboard** → **Project Settings** → **Database**
2. Scroll to **Connection pooling** section
3. Copy the **URI** connection string (should start with `postgresql://`)
4. Add to your `.env` file:
   ```bash
   DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

**Note:** Replace `[password]` with your actual database password.

### Step 2: Run Setup Script

The script will create the schema programmatically:

```bash
uv run python setup/setup_database.py
```

Expected output:
```
✓ Configuration loaded
✓ Connected to PostgreSQL database

================================================================================
CREATING SCHEMA
================================================================================

✓ Created table 'pull_requests'
✓ Created index 'idx_enrichment_status'
✓ Created index 'idx_repo'
✓ Created index 'idx_merged_at'

✓ Database schema created successfully!
```

### Step 3: Verify Schema

Verify the schema was created correctly:

```bash
uv run python setup/setup_database.py --verify
```

Expected output:
```
✓ Configuration loaded
✓ Connected to PostgreSQL database

================================================================================
VERIFYING SCHEMA
================================================================================

✓ Table 'pull_requests' exists
✓ Index 'idx_enrichment_status' exists
✓ Index 'idx_repo' exists
✓ Index 'idx_merged_at' exists

✓ Schema verification successful
```

### Step 4: Create Required Functions

After creating the tables, you need to create PostgreSQL functions for efficient queries.

**Function: `get_distinct_repos()`**

This function returns unique repository names for the PR Explorer web UI.

1. Go to **Supabase Dashboard** → **SQL Editor**
2. Click **New Query**
3. Paste the following SQL:

```sql
CREATE OR REPLACE FUNCTION get_distinct_repos()
RETURNS TABLE(repo TEXT) AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT pull_requests.repo
  FROM pull_requests
  ORDER BY pull_requests.repo;
END;
$$ LANGUAGE plpgsql;
```

4. Click **Run** to create the function

**Verify it works:**

```sql
SELECT * FROM get_distinct_repos();
```

You should see a list of unique repository names.

## Advanced Usage

### Drop and Recreate Schema (DANGEROUS)

If you need to drop and recreate the schema (this will DELETE ALL DATA):

```bash
uv run python setup/setup_database.py --drop
```

You'll be prompted to confirm before any data is deleted.

## Troubleshooting

### Connection Failed

**Error:** `Failed to connect to database`

**Solution:** 
1. Make sure `DATABASE_URL` is set correctly in `.env`
2. Check that your IP is allowed in Supabase:
   - Dashboard → Project Settings → Database
   - Check "Connection pooling" or "Direct connection" settings
3. Verify the database password is correct

### DATABASE_URL Not Found

**Error:** `DATABASE_URL not found in .env file`

**Solution:** Add your PostgreSQL connection string to `.env`:
1. Go to Supabase Dashboard → Project Settings → Database
2. Find the connection string under "Connection pooling"
3. Add to `.env`: `DATABASE_URL=postgresql://...`

### Verification Failed

**Error:** `Schema verification failed`

**Solution:** Run the setup script first:
```bash
uv run python setup/setup_database.py
```

### Unique Constraint Violation

**Error:** `duplicate key value violates unique constraint "pull_requests_repo_pr_number_key"`

**Solution:** This is expected behavior - you're trying to insert a PR that already exists. The application code uses `UPSERT` to handle this.

## Schema Modifications

If you need to modify the schema later:

1. **Add a column**: Use SQL `ALTER TABLE` in Supabase SQL Editor
2. **Add an index**: Update `CREATE_INDEXES_SQL` in `setup_database.py`
3. **Re-run setup**: Safe to run multiple times (uses `IF NOT EXISTS`)
