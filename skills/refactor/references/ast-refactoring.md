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
from packages.refactor.ast_refactor_helpers import (
    safe_transform_file,
    LibCSTTransformer,
    RenameAttribute,
    RemoveUnusedImport,
)
```

**Example: Extract Method**:
```python
class ExtractMethodTransformer(LibCSTTransformer):
    def __init__(self, target_function: str, new_method: str):
        super().__init__()
        self.target_function = target_function
        self.new_method = new_method

    def leave_FunctionDef(self, original_node, updated_node):
        if updated_node.name.value == self.target_function:
            self._increment_modifications()
            # Extract logic to new method
            return create_extracted_method(updated_node)
        return updated_node

success, error, count = safe_transform_file(
    "src/module.py",
    ExtractMethodTransformer,
    target_function="old_function",
    new_method="extracted_method"
)
```

**Reference**: `P:/packages/refactor/AST_HELPERS_GUIDE.md` for complete API documentation.
