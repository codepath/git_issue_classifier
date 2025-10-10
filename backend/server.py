#!/usr/bin/env python3
"""
Backend Server Entry Point

Simple uvicorn launcher for the PR Explorer API.
Can be run directly or imported.

Usage:
    # Development mode with auto-reload
    python backend/server.py
    
    # Custom host/port
    python backend/server.py --host 0.0.0.0 --port 8080
    
    # Production mode (no reload)
    python backend/server.py --no-reload
    
    # Or use uvicorn directly
    uvicorn backend.app:app --reload
"""

import argparse
import sys


def main():
    """Launch the FastAPI backend server."""
    parser = argparse.ArgumentParser(
        description="PR Explorer API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Development mode (auto-reload enabled)
  python backend/server.py
  
  # Custom host/port
  python backend/server.py --host 0.0.0.0 --port 8080
  
  # Production mode (no reload)
  python backend/server.py --no-reload
        """
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the API server on (default: 8000)"
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (use for production)"
    )
    
    args = parser.parse_args()
    
    # Print startup info
    print("=" * 80)
    print("PR Explorer API Server")
    print("=" * 80)
    print(f"API will be available at: http://{args.host}:{args.port}")
    print(f"API docs available at: http://{args.host}:{args.port}/docs")
    print("")
    print("To start the frontend:")
    print("  cd frontend && npm run dev")
    print("")
    print("Press Ctrl+C to stop the server")
    print("=" * 80)
    print("")
    
    # Start uvicorn server
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()

