#!/usr/bin/env python3
"""Runtime compatibility layer for direct social publishing.

Platform policy now lives in direct_api_publish.py so the scheduled workflow
and local tests use one TikTok implementation instead of a second override.
"""
from __future__ import annotations

import os

import direct_api_publish as core


def main() -> int:
    os.environ.setdefault("LINKEDIN_VERSION", "202604")
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
