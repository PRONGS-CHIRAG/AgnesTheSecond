#!/usr/bin/env python3
"""Write schema summary JSON to outputs/reports/schema_summary.json."""

from __future__ import annotations

import json
from pathlib import Path

from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.data.schema_summary import build_schema_summary
from agnes.utils.logging import configure_logging

OUT = Path("outputs/reports/schema_summary.json")


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level)
    engine = get_engine(settings)
    summary = build_schema_summary(engine)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(OUT), "tables": len(summary.tables)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
