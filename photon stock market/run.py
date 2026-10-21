"""Run script for Photon - Real-time WebSocket Stock Ticker.

Reads environment configuration and starts the FastAPI server via Uvicorn.
Supports Windows, Linux, and macOS environments cleanly.
"""

import os
import sys
import uvicorn
from dotenv import load_dotenv

# Load optional .env file
load_dotenv()

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    print("=" * 60)
    print("  [*] Photon - Real-time WebSocket Stock Ticker")
    print("=" * 60)
    print(f"  * Local Dashboard:  http://{host}:{port}")
    print(f"  * REST API Stocks:  http://{host}:{port}/api/stocks")
    print(f"  * REST API Health:  http://{host}:{port}/api/health")
    print(f"  * WebSocket Stream: ws://{host}:{port}/ws")
    print(f"  * Auto-Reload:      {debug}")
    print("=" * 60)
    print("  Press Ctrl+C to stop the server.\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )
