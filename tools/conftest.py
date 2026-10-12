"""Make the launcher package and the agent package importable during tests."""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent

for _p in (str(TOOLS), str(REPO / "agents" / "desktop")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
