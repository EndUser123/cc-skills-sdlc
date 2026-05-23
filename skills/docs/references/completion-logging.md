# Skill Completion Logging

After completing documentation updates, log coverage:

```python
import sys
from pathlib import Path
sys.path.insert(0, 'P://.claude/skills/gto/lib')
from skill_coverage_detector import _append_skill_coverage
from skill_guard.utils.terminal_detection import detect_terminal_id

_append_skill_coverage(
    project_root=Path.cwd(),
    target_key='docs',
    skill='/docs',
    terminal_id=detect_terminal_id(),
    git_sha=None,
)
```
