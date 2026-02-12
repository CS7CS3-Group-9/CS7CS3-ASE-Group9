import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))
