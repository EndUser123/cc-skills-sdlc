# AST-Based Refactoring (REQUIRED)

**All Python refactoring MUST use LibCST transformations.**

**When to use AST**:
- Function/method extraction
- Parameter reordering
- Import reorganization
- Code movement across files
- Signature changes

**Available Helpers**:
```python
from scripts.ast_refactor_helpers import (
    safe_transform_file,
    LibCSTTransformer,
    RenameAttribute,
    RemoveUnusedImport,
    extract_method_callsafe,
    diff_sources,
)
import libcst as cst
```

**Example: Extract Method** (using LibCST directly):
```python
class ExtractMethodTransformer(LibCSTTransformer):
    def __init__(self, target_function: str, new_method: str):
        super().__init__()
        self.target_function = target_function
        self.new_method = new_method

    def leave_FunctionDef(self, original_node, updated_node):
        if updated_node.name.value == self.target_function:
            self._increment()
            # Extract logic to new method
            return create_extracted_method(updated_node)
        return updated_node

result = safe_transform_file(
    "src/module.py",
    ExtractMethodTransformer,
    target_function="old_function",
    new_method="extracted_method"
)
# result.changed == True means transformation was applied
# result.new_source contains the transformed code
```

**Reference**: LibCST documentation — https://libcst.readthedocs.io/
