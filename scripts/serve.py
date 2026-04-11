"""Start the Financial Analyst web interface.

Usage:
    python scripts/serve.py
    python scripts/serve.py --port 8080
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    print(f"\n  Financial Analyst AI  →  http://localhost:{args.port}\n")
    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=["web", "agents", "tools", "config"],
    )
