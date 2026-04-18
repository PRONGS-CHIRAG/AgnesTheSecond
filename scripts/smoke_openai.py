#!/usr/bin/env python3
"""Smoke test: OpenAI API (openai SDK)."""

from __future__ import annotations

import json

from agnes.config.settings import Settings
from agnes.retrieval.openai_client import ping as openai_ping
from agnes.utils.logging import configure_logging


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level)
    result = openai_ping(settings)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
