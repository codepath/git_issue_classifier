#!/usr/bin/env python3
"""
Database setup script for git-issue-classifier.

Creates the Supabase schema programmatically using direct PostgreSQL connection.

Usage:
    python setup/setup_database.py           # Create schema
    python setup/setup_database.py --verify  # Verify existing schema
    python setup/setup_database.py --drop    # Drop and recreate (DANGEROUS)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import load_config
from utils.logger import setup_logger

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("Error: psycopg2 not installed. Run: uv sync")
    sys.exit(1)

logger = setup_logger(__name__)


# SQL for creating the schema
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pull_requests (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    
    -- Basic Info (from index phase - Phase 1)
    repo TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    merged_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL,
    linked_issue_number INTEGER,  -- Parsed from PR body during index phase
    
    -- Enriched Data (from enrichment phase - Phase 2) - NULLABLE
    files JSONB,
    linked_issue JSONB,
    issue_comments JSONB,
    
    -- Enrichment Status Tracking
    enrichment_status TEXT NOT NULL DEFAULT 'pending',
    enrichment_attempted_at TIMESTAMP,
    enrichment_error TEXT,
    
    -- Constraints
    UNIQUE(repo, pr_number)
);
"""

CREATE_CLASSIFICATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS classifications (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    
    -- Foreign Key (for joins if needed)
    pr_id BIGINT REFERENCES pull_requests(id) ON DELETE CASCADE,
    
    -- Denormalized PR info (for standalone export)
    github_url TEXT NOT NULL,
    repo TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    merged_at TIMESTAMP NOT NULL,
    
    -- Classification fields
    difficulty TEXT CHECK (difficulty IN ('trivial', 'easy', 'medium', 'hard')),
    categories TEXT[],
    concepts_taught TEXT[],
    prerequisites TEXT[],
    reasoning TEXT,
    
    -- Metadata
    classified_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(pr_id)
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_enrichment_status ON pull_requests(enrichment_status);",
    "CREATE INDEX IF NOT EXISTS idx_repo ON pull_requests(repo);",
    "CREATE INDEX IF NOT EXISTS idx_merged_at ON pull_requests(merged_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_classifications_difficulty ON classifications(difficulty);",
    "CREATE INDEX IF NOT EXISTS idx_classifications_repo ON classifications(repo);",
    "CREATE INDEX IF NOT EXISTS idx_classifications_merged_at ON classifications(merged_at DESC);",
]

DROP_TABLE_SQL = "DROP TABLE IF EXISTS classifications CASCADE; DROP TABLE IF EXISTS pull_requests CASCADE;"


def get_database_url(config) -> str:
    """
    Get PostgreSQL database URL.
    
    Uses DATABASE_URL from .env if available, otherwise constructs from Supabase URL.
    """
    if config.credentials.database_url:
        return config.credentials.database_url
    
    # If no DATABASE_URL, provide instructions
    logger.error("DATABASE_URL not found in .env file")
    logger.error("\nTo get your DATABASE_URL:")
    logger.error("1. Go to Supabase Dashboard → Project Settings → Database")
    logger.error("2. Find 'Connection string' under 'Connection pooling'")
    logger.error("3. Copy the 'URI' connection string")
    logger.error("4. Add to .env file: DATABASE_URL=postgresql://...")
    logger.error("\nExample format:")
    logger.error("DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres")
    sys.exit(1)


def create_connection(database_url: str):
    """Create a PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(database_url)
        logger.info("✓ Connected to PostgreSQL database")
        return conn
    except Exception as e:
        logger.error(f"✗ Failed to connect to database: {e}")
        logger.error("\nMake sure:")
        logger.error("1. DATABASE_URL is correct in .env file")
        logger.error("2. Your IP is allowed in Supabase (Project Settings → Database → Connection pooling)")
        logger.error("3. Database password is correct")
        sys.exit(1)


def execute_sql(conn, sql_statement: str, description: str) -> bool:
    """Execute a SQL statement."""
    try:
        cursor = conn.cursor()
        cursor.execute(sql_statement)
        conn.commit()
        cursor.close()
        logger.info(f"✓ {description}")
        return True
    except Exception as e:
        logger.error(f"✗ {description} failed: {e}")
        conn.rollback()
        return False


def verify_schema(conn) -> bool:
    """Verify that the schema exists and is accessible."""
    try:
        cursor = conn.cursor()
        
        # Check if pull_requests table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'pull_requests'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.error("✗ Table 'pull_requests' does not exist")
            cursor.close()
            return False
        
        logger.info("✓ Table 'pull_requests' exists")
        
        # Check if classifications table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'classifications'
            );
        """)
        classifications_exists = cursor.fetchone()[0]
        
        if not classifications_exists:
            logger.error("✗ Table 'classifications' does not exist")
            cursor.close()
            return False
        
        logger.info("✓ Table 'classifications' exists")
        
        # Check pull_requests indexes
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'pull_requests';
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        
        expected_indexes = ['idx_enrichment_status', 'idx_repo', 'idx_merged_at']
        for idx in expected_indexes:
            if idx in indexes:
                logger.info(f"✓ Index '{idx}' exists")
            else:
                logger.warning(f"⚠ Index '{idx}' missing")
        
        # Check classifications indexes
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'classifications';
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        
        expected_indexes = ['idx_classifications_difficulty', 'idx_classifications_repo', 'idx_classifications_merged_at']
        for idx in expected_indexes:
            if idx in indexes:
                logger.info(f"✓ Index '{idx}' exists")
            else:
                logger.warning(f"⚠ Index '{idx}' missing")
        
        cursor.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ Schema verification failed: {e}")
        return False


def create_schema(conn) -> bool:
    """Create the database schema."""
    logger.info("\n" + "="*80)
    logger.info("CREATING SCHEMA")
    logger.info("="*80 + "\n")
    
    # Create pull_requests table
    if not execute_sql(conn, CREATE_TABLE_SQL, "Created table 'pull_requests'"):
        return False
    
    # Create classifications table
    if not execute_sql(conn, CREATE_CLASSIFICATIONS_TABLE_SQL, "Created table 'classifications'"):
        return False
    
    # Create indexes
    for idx_sql in CREATE_INDEXES_SQL:
        idx_name = idx_sql.split("INDEX IF NOT EXISTS ")[1].split(" ON")[0]
        if not execute_sql(conn, idx_sql, f"Created index '{idx_name}'"):
            return False
    
    logger.info("\n✓ Database schema created successfully!")
    return True


def drop_schema(conn) -> bool:
    """Drop the existing schema (DANGEROUS)."""
    logger.warning("\n" + "="*80)
    logger.warning("⚠️  WARNING: DROPPING EXISTING SCHEMA")
    logger.warning("="*80)
    logger.warning("This will DELETE ALL DATA in both pull_requests and classifications tables!")
    
    response = input("\nType 'yes' to confirm: ")
    if response.lower() != 'yes':
        logger.info("Aborted.")
        return False
    
    if not execute_sql(conn, DROP_TABLE_SQL, "Dropped tables 'pull_requests' and 'classifications'"):
        return False
    
    logger.info("✓ Schema dropped")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Set up database schema for git-issue-classifier"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing schema without creating"
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop and recreate tables (DANGEROUS - deletes all data)"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config()
        logger.info("✓ Configuration loaded")
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        logger.error("Make sure .env file exists with required variables")
        sys.exit(1)
    
    # Get database URL
    database_url = get_database_url(config)
    
    # Create connection
    conn = create_connection(database_url)
    
    try:
        # Verify mode
        if args.verify:
            logger.info("\n" + "="*80)
            logger.info("VERIFYING SCHEMA")
            logger.info("="*80 + "\n")
            
            if verify_schema(conn):
                logger.info("\n✓ Schema verification successful")
                sys.exit(0)
            else:
                logger.error("\n✗ Schema verification failed")
                sys.exit(1)
        
        # Drop mode
        if args.drop:
            if not drop_schema(conn):
                sys.exit(1)
        
        # Create schema
        if create_schema(conn):
            logger.info("\n" + "="*80)
            logger.info("NEXT STEPS")
            logger.info("="*80)
            logger.info("\n1. Verify the schema:")
            logger.info("   python setup/setup_database.py --verify")
            logger.info("\n2. Run the full verification test:")
            logger.info("   uv run python verify_milestone5.py")
            sys.exit(0)
        else:
            logger.error("\n✗ Schema creation failed")
            sys.exit(1)
            
    finally:
        conn.close()
        logger.info("\n✓ Database connection closed")


if __name__ == "__main__":
    main()