"""Pytest configuration for PVM tests."""

import sys
from pathlib import Path

# Ensure src/ is on the path so `from pvm.models import ...` works
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))
