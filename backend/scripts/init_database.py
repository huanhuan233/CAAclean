from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import init_db


def main() -> int:
    asyncio.run(init_db())
    print("database tables initialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
