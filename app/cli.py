"""Small setup/self-test CLI used by setup.ps1."""

from __future__ import annotations

import argparse
import json

from app.runtime import build_runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows Siri Agent local maintenance")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    runtime = build_runtime(startup_refresh=False)
    if args.refresh or args.self_test:
        entries, diagnostics = runtime.catalog.refresh()
        print(json.dumps({"count": len(entries), "sources": diagnostics.source_counts, "warnings": diagnostics.warnings}, ensure_ascii=False))
    if args.self_test:
        print("self-test: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
