"""Lightweight healthcheck script for Docker."""

import sys
import urllib.request

try:
    urllib.request.urlopen("http://localhost:8000/health", timeout=5)
except Exception:
    sys.exit(1)
