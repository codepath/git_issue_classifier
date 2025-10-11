#!/usr/bin/env python3
"""
Migration 001: Add issue generation columns to pull_requests table.

This migration adds:
- generated_issue: TEXT column for storing generated issue markdown
- issue_generated_at: TIMESTAMPTZ column for tracking when issue was generated
- idx_pr_has_generated_issue: Partial index for querying PRs with generated issues

This script is idempotent - safe to run multiple times.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.config_loader import load_config
from utils.logger import setup_logger

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 not installed. Run: uv sync")
    sys.exit(1)

logger = setup_logger(__name__)


def get_database_url(config) -> str:
    """Get PostgreSQL database URL from config."""
    if config.credentials.database_url:
        return config.credentials.database_url
    
    logger.error("DATABASE_URL not found in .env file")
    logger.error("Add to .env file: DATABASE_URL=postgresql://...")
    sys.exit(1)


def create_connection(database_url: str):
    """Create a PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(database_url)
        logger.info("✓ Connected to PostgreSQL database")
        return conn
    except Exception as e:
        logger.error(f"✗ Failed to connect to database: {e}")
        sys.exit(1)


def check_column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = %s 
                AND column_name = %s
            );
        """, (table_name, column_name))
        exists = cursor.fetchone()[0]
        cursor.close()
        return exists
    except Exception as e:
        logger.error(f"Failed to check if column exists: {e}")
        return False


def check_index_exists(conn, index_name: str) -> bool:
    """Check if an index exists."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM pg_indexes 
                WHERE indexname = %s
            );
        """, (index_name,))
        exists = cursor.fetchone()[0]
        cursor.close()
        return exists
    except Exception as e:
        logger.error(f"Failed to check if index exists: {e}")
        return False


def add_column_if_not_exists(conn, column_name: str, column_definition: str) -> bool:
    """Add a column to pull_requests table if it doesn't exist."""
    if check_column_exists(conn, "pull_requests", column_name):
        logger.info(f"⊙ Column '{column_name}' already exists, skipping")
        return True
    
    try:
        cursor = conn.cursor()
        sql = f"ALTER TABLE pull_requests ADD COLUMN {column_name} {column_definition};"
        cursor.execute(sql)
        conn.commit()
        cursor.close()
        logger.info(f"✓ Added column '{column_name}'")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to add column '{column_name}': {e}")
        conn.rollback()
        return False


def create_index_if_not_exists(conn, index_name: str, index_sql: str) -> bool:
    """Create an index if it doesn't exist."""
    if check_index_exists(conn, index_name):
        logger.info(f"⊙ Index '{index_name}' already exists, skipping")
        return True
    
    try:
        cursor = conn.cursor()
        cursor.execute(index_sql)
        conn.commit()
        cursor.close()
        logger.info(f"✓ Created index '{index_name}'")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create index '{index_name}': {e}")
        conn.rollback()
        return False


def verify_migration(conn) -> bool:
    """Verify that the migration was successful."""
    logger.info("\nVerifying migration...")
    
    success = True
    
    # Check generated_issue column
    if check_column_exists(conn, "pull_requests", "generated_issue"):
        logger.info("✓ Column 'generated_issue' exists")
    else:
        logger.error("✗ Column 'generated_issue' missing")
        success = False
    
    # Check issue_generated_at column
    if check_column_exists(conn, "pull_requests", "issue_generated_at"):
        logger.info("✓ Column 'issue_generated_at' exists")
    else:
        logger.error("✗ Column 'issue_generated_at' missing")
        success = False
    
    # Check index
    if check_index_exists(conn, "idx_pr_has_generated_issue"):
        logger.info("✓ Index 'idx_pr_has_generated_issue' exists")
    else:
        logger.error("✗ Index 'idx_pr_has_generated_issue' missing")
        success = False
    
    return success


def main():
    logger.info("="*80)
    logger.info("MIGRATION 001: Add Issue Generation Columns")
    logger.info("="*80)
    
    # Load configuration
    try:
        config = load_config()
        logger.info("✓ Configuration loaded")
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        sys.exit(1)
    
    # Get database URL and connect
    database_url = get_database_url(config)
    conn = create_connection(database_url)
    
    try:
        logger.info("\nAdding columns...")
        
        # Add generated_issue column (TEXT, nullable)
        if not add_column_if_not_exists(
            conn, 
            "generated_issue", 
            "TEXT"
        ):
            sys.exit(1)
        
        # Add issue_generated_at column (TIMESTAMPTZ, nullable)
        if not add_column_if_not_exists(
            conn,
            "issue_generated_at",
            "TIMESTAMPTZ"
        ):
            sys.exit(1)
        
        logger.info("\nCreating indexes...")
        
        # Create partial index for PRs with generated issues
        index_sql = """
        CREATE INDEX idx_pr_has_generated_issue 
        ON pull_requests(id) 
        WHERE generated_issue IS NOT NULL;
        """
        if not create_index_if_not_exists(
            conn,
            "idx_pr_has_generated_issue",
            index_sql
        ):
            sys.exit(1)
        
        # Verify migration
        if verify_migration(conn):
            logger.info("\n" + "="*80)
            logger.info("✓ Migration completed successfully!")
            logger.info("="*80)
            sys.exit(0)
        else:
            logger.error("\n✗ Migration verification failed")
            sys.exit(1)
    
    finally:
        conn.close()
        logger.info("\n✓ Database connection closed")


if __name__ == "__main__":
    main()

