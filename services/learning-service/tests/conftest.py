from __future__ import annotations

import sys
from pathlib import Path


LEARNING_SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "packages" / "platform_common").exists()),
    LEARNING_SERVICE_ROOT,
)
PLATFORM_COMMON_ROOT = REPO_ROOT / "packages" / "platform_common"

for path in (LEARNING_SERVICE_ROOT, REPO_ROOT, PLATFORM_COMMON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
