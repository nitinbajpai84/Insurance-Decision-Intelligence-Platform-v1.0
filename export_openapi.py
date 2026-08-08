#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from copilot_api_gateway.api import app


def main() -> int:
    output = Path("openapi_copilot_api.json")
    output.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

