#!/usr/bin/env python3
"""Smoke test: SQLite connectivity and core table row counts."""

from __future__ import annotations

import json

from agnes.config.settings import Settings
from agnes.data.db_loader import ping as db_ping
from agnes.utils.logging import configure_logging


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level)
    try:
        counts = db_ping(settings)
    except FileNotFoundError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    except OSError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, "counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
