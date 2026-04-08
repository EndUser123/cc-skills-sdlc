#!/usr/bin/env python3
import sys
from pathlib import Path

code_skill_root = Path(__file__).parent.parent.resolve()
utils_path = code_skill_root / "utils"
sys.path.insert(0, str(code_skill_root))
sys.path.insert(0, str(utils_path))

print("code_skill_root:", code_skill_root)
print("utils_path:", utils_path)
print("utils_path exists:", utils_path.exists())
print("evidence.py exists:", (utils_path / "evidence.py").exists())

try:
    import evidence as evidence_module

    print("evidence module:", evidence_module)
    print("Has EvidenceManager:", hasattr(evidence_module, "EvidenceManager"))
    if hasattr(evidence_module, "EvidenceManager"):
        EvidenceManager = evidence_module.EvidenceManager
        print("SUCCESS: EvidenceManager =", EvidenceManager)
except Exception as e:
    print("ERROR:", str(e))
    print("ERROR type:", type(e).__name__)
