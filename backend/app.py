"""
FastAPI application for PR Explorer.

This provides a REST API for browsing PRs stored in Supabase.
The React frontend will consume these endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.config_loader import load_config
from utils.logger import setup_logger
from storage.supabase_client import SupabaseClient

logger = setup_logger(__name__)

# Load config and initialize Supabase client
config = load_config()
supabase = SupabaseClient(
    config.credentials.supabase_url,
    config.credentials.supabase_key
)

# Create FastAPI app
app = FastAPI(
    title="PR Explorer API",
    description="REST API for browsing GitHub PRs stored in Supabase",
    version="1.0.0"
)

# Enable CORS for both local development and production
# Allows the React frontend to call the API from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (development + production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routes
from backend.routes import router
app.include_router(router)

logger.info("FastAPI app initialized")
