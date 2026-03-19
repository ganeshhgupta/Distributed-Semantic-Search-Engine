"""
pytest configuration for the distributed search engine test suite.
"""
import sys
from pathlib import Path

# Ensure the project root is on sys.path so all modules are importable
# without installing the package.
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
