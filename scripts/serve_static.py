#!/usr/bin/env python3
"""
Secure local static server for the brewfile repo.

Features:
- Serves files rooted at the repository directory.
- Disables directory listing (returns 403 when no index file).
- Redirects requests to "/" -> "/docs/tools/index.html".
- Normalizes and confines paths to the repo root (blocks path traversal and
  following symlinks outside of the root).

Usage:
  python3 scripts/serve_static.py            # listens on 127.0.0.1:8000
  python3 scripts/serve_static.py --port 9000
"""
from __future__ import annotations

import argparse
import posixpath
import sys
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Tuple
from urllib.parse import unquote, urlparse

# Resolve repository root as the directory that contains this script's parent
# directory (scripts/.. -> repo root). Adjust if the layout changes.
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent.resolve()

# Default redirect target for "/"
ROOT_REDIRECT = "/docs/tools/index.html"


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


class SecureHTTPRequestHandler(SimpleHTTPRequestHandler):
    # Ensure we serve from the repo root regardless of the current working dir
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    # Redirect "/" to the desired docs page
    def do_GET(self):
        # Normalize path for exact root check (preserve query for redirect if present)
        parsed = urlparse(self.path)
        if parsed.path in ("", "/"):
            target = ROOT_REDIRECT
            # Preserve query string if present
            if parsed.query:
                target = f"{target}?{parsed.query}"
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", target)
            self.end_headers()
            return
        return super().do_GET()

    # Deny directory listings entirely
    def list_directory(self, path):
        self.send_error(HTTPStatus.FORBIDDEN, "Directory listing disabled")
        return None

    # Harden path translation to keep all requests within REPO_ROOT and
    # disallow following symlinks that escape the root.
    def translate_path(self, path: str) -> str:
        # Borrow the normalization approach from SimpleHTTPRequestHandler
        # but anchor to REPO_ROOT and then enforce confinement.
        path = urlparse(path).path
        path = posixpath.normpath(unquote(path))
        parts = [p for p in path.split('/') if p and p not in ('.',)]
        # Always join under REPO_ROOT
        resolved = REPO_ROOT
        for part in parts:
            # Prevent sneaky segments
            if part in ("..",):
                # We'll treat any attempt to traverse up as not found
                return str(REPO_ROOT / "__forbidden__")
            resolved = (resolved / part)
        # Resolve symlinks; if resolution escapes REPO_ROOT, deny
        try:
            real = resolved.resolve()
        except FileNotFoundError:
            # Even if the target doesn't exist, compute its would-be parent
            real = resolved.parent.resolve() / resolved.name
        if not is_within(real, REPO_ROOT):
            return str(REPO_ROOT / "__forbidden__")
        return str(real)

    # Avoid verbose logging of full local paths; only log method, path, code
    def log_message(self, format: str, *args) -> None:
        try:
            msg = "%s - - [%s] " % (self.address_string(), self.log_date_time_string())
            msg += (format % args)
            sys.stderr.write(msg + "\n")
        except Exception:
            # Fallback to base behavior if something goes wrong
            super().log_message(format, *args)


def serve(port: int) -> None:
    server_address: Tuple[str, int] = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, SecureHTTPRequestHandler)
    print(
        f"Serving {REPO_ROOT} on http://{server_address[0]}:{server_address[1]} "
        f"(no directory listing)"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Secure local static server for the brewfile repo"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to listen on (default: 8000)"
    )
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
