"""Entry point: ``python -m generic_agent_engineered.gateway``."""

from __future__ import annotations

import asyncio
import sys

from .server import serve_stdio


def main() -> int:
    try:
        return asyncio.run(serve_stdio())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
