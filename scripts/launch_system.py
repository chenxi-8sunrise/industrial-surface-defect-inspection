from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ready() -> bool:
    try:
        with OPENER.open(f"{URL}/api/health", timeout=1) as response:
            status = json.load(response)
        return status.get("service") == "surface-defect-api" and status.get("status") == "ok"
    except (urllib.error.URLError, OSError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not ready():
        log_path = ROOT / "artifacts" / "server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                close_fds=True,
            )
        deadline = time.monotonic() + 45
        while not ready():
            if process.poll() is not None or time.monotonic() >= deadline:
                print(f"Server did not become ready. Check: {log_path}")
                return 1
            time.sleep(0.4)

    print(f"System ready: {URL}")
    if not args.no_browser:
        webbrowser.open(URL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
