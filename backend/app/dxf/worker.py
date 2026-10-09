"""Bounded host-Python DXF reader, launched outside the FastAPI event loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.dxf.source import parse_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("revision_id")
    args = parser.parse_args()
    document = parse_source(args.source, args.revision_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
