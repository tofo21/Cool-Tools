#!/usr/bin/env python3
"""Validation-only entry point for a versioned ESPN market manifest."""

from capture_espn_market_2026 import main


if __name__ == "__main__":
    raise SystemExit(main(["--validate-only", *__import__("sys").argv[1:]]))
