"""Native bundled entry point; keep mutable state outside installation resources."""
import argparse
import multiprocessing
import os
from pathlib import Path
import sys


def main():
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="Kingdom bundled backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if getattr(sys, "frozen", False):
        default = Path.home() / ".kingdom"
        runtime = Path(os.environ.get("KINGDOM_DATA_DIR", default)).resolve()
        runtime.mkdir(parents=True, exist_ok=True)
        os.chdir(runtime)
    from backend.main import app
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, timeout_graceful_shutdown=3)


if __name__ == "__main__":
    main()
