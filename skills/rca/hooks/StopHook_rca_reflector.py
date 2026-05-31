#!/usr/bin/env python3
"""Compatibility wrapper -- delegates to cc-aca-reasoning plugin."""
import sys
from pathlib import Path

_PLUGIN_ROOT = Path("P:/packages/cc-aca-reasoning")
sys.path.insert(0, str(_PLUGIN_ROOT / "__lib"))

from _bootstrap import bootstrap; _hd = bootstrap(__file__)

from pathlib import Path as _P
_hook = Path(r"P:\packages\cc-aca-reasoning\hooks\\stop\\StopHook_rca_reflector.py")
if not _hook.exists():
    raise ImportError(f"Plugin hook not found: {_hook}")

import importlib.util
_spec = importlib.util.spec_from_file_location("StopHook_rca_reflector", _hook)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_globals = {k: v for k, v in vars(_mod).items() if not k.startswith("__")}
globals().update(_globals)

if hasattr(_mod, "main"):
    _mod.main()
