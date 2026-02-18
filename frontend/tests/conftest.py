import sys
from pathlib import Path

# Add project root to sys.path so "frontend" is importable as a package
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
