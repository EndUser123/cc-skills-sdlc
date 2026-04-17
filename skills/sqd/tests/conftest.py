"""conftest — ensure layers is importable from the sqd skill directory."""
from pathlib import Path
import sys

# Ensure the skill root (parent of layers/) is on sys.path
Skill_ROOT = Path(__file__).parent.parent
if str(Skill_ROOT) not in sys.path:
    sys.path.insert(0, str(Skill_ROOT))
