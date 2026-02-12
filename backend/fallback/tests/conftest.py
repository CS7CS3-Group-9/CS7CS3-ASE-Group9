import sys
from pathlib import Path

# Up to project root: conftest.py -> tests/ -> api/ -> backend/ -> root/
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))