"""Verify a mounted evidence checkout with the registered compiler interpreter."""

import os
import sys
from pathlib import Path

from freeze import published, verify, versions

if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    os.environ["SIZE0_CLAIMS"] = sys.argv[2]
    versions()
    published(root, checkout=Path(__file__).resolve().parent)
    verify(root)
