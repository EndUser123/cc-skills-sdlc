"""
Tree-of-Thought (ToT) Tracer for Phase 8 (TRACE) enhancement.

Generates branching reasoning patterns for code trace-throughs:
- 2-3 branches per decision point
- Branch scoring (sure/maybe/unlikely)
- Pruning to high-value branches
- Hierarchical branch tracking
"""

import re
from typing import Any


class BranchGenerator:
    """
    Tree-of-Thought branch generator for code tracing.

    Generates branching reasoning patterns for conditional logic
    and scores them by likelihood.
    """

    # Patterns that indicate branching points
    CONDITIONAL_PATTERNS = [
        r"\bif\s+",  # if statements
        r"\belif\s+",  # elif statements
        r"\belse\s*:",  # else clauses
        r"\bfor\s+",  # for loops
        r"\bwhile\s+",  # while loops
        r"\btry\s*:",  # try blocks
        r"\bexcept\s+",  # except blocks
        r"\bmatch\s+|case\s+",  # match/case statements
    ]

    # Keywords that indicate sure branches (common paths)
    SURE_KEYWORDS = [
        "main",
        "normal",
        "success",
        "happy path",
        "default",
        "valid",
        "authenticated",
        "authorized",
        "allowed",
    ]

    # Keywords that indicate unlikely branches (edge cases)
    UNLIKELY_KEYWORDS = [
        "error",
        "exception",
        "fail",
        "failed",
        "failure",
        "invalid",
        "denied",
        "edge case",
        "rare",
        "unusual",
        "unexpected",
    ]

    def __init__(self, code_content: str):
        """
        Initialize branch generator with code content.

        Args:
            code_content: Full text of code to analyze
        """
        self.code_content = code_content
        self.lines = code_content.split("\n")
        self._branch_counter = 0

    def generate_branches(self) -> list[dict[str, Any]]:
        """
        Generate branches for all decision points in the code.

        Returns:
            List of branch dicts with 'id', 'description', 'score', and optional 'parent_id'
        """
        branches = []

        # Find all conditional statements
        conditionals = self._find_conditionals()

        # Generate branches for each conditional
        for conditional in conditionals:
            branch_list = self._generate_branches_for_conditional(conditional)

            # Add parent_id for nested conditionals
            if conditional.get("parent_line"):
                for branch in branch_list:
                    branch["parent_id"] = f"b_{conditional['parent_line']}"

            branches.extend(branch_list)

        # If no conditionals found, generate a single main path branch
        if not branches and self.code_content.strip():
            branches.append({"id": "b_1", "description": "Main execution path", "score": "sure"})

        return branches

    def prune_branches(self, branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Remove 'unlikely' scored branches from the branch list.

        Args:
            branches: List of branch dicts to prune

        Returns:
            Filtered list of branches without 'unlikely' scored ones
        """
        return [b for b in branches if "score" in b and b["score"] != "unlikely"]

    def _find_conditionals(self) -> list[dict[str, Any]]:
        """
        Find all conditional statements in the code.

        Returns:
            List of conditional dicts with line number, type, and nesting info
        """
        conditionals = []
        indent_stack = []  # Track nesting levels

        for line_num, line in enumerate(self.lines, start=1):
            stripped = line.strip()

            # Check if this line contains a conditional pattern
            for pattern in self.CONDITIONAL_PATTERNS:
                if re.search(pattern, stripped):
                    # Calculate current nesting level
                    current_indent = len(line) - len(line.lstrip())

                    # Check if this is nested (has parent)
                    parent_line = None
                    if indent_stack and current_indent > indent_stack[-1]["indent"]:
                        parent_line = indent_stack[-1]["line_num"]

                    conditionals.append(
                        {"line_num": line_num, "text": stripped, "parent_line": parent_line}
                    )

                    # Push to indent stack if it's a block starter
                    if any(
                        re.search(p, stripped)
                        for p in [
                            r"\bif\s+",
                            r"\bfor\s+",
                            r"\bwhile\s+",
                            r"\btry\s*:",
                            r"\bmatch\s+",
                        ]
                    ):
                        indent_stack.append({"line_num": line_num, "indent": current_indent})

                    break

        return conditionals

    def _generate_branches_for_conditional(
        self, conditional: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Generate branches for a single conditional statement.

        Args:
            conditional: Conditional dict with line number and text

        Returns:
            List of branch dicts (2-3 branches per conditional)
        """
        text = conditional["text"]
        line_num = conditional["line_num"]

        branches = []

        # Analyze the conditional type
        if re.search(r"\bif\s+", text):
            # if statement: generate 2 branches (true/false)
            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="true",
                    description=self._generate_description(text, "true path"),
                    score=self._score_branch(text, "true"),
                )
            )

            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="false",
                    description=self._generate_description(text, "false path"),
                    score=self._score_branch(text, "false"),
                )
            )

        elif re.search(r"\belif\s+", text):
            # elif statement: generate 2 branches (condition true/false)
            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="elif_true",
                    description=self._generate_description(text, "elif true path"),
                    score=self._score_branch(text, "elif"),
                )
            )

            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="elif_false",
                    description=self._generate_description(text, "elif false path"),
                    score="maybe",
                )
            )

        elif re.search(r"\belse\s*:", text):
            # else clause: single branch
            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="else",
                    description=self._generate_description(text, "else path"),
                    score="maybe",
                )
            )

        elif re.search(r"\bfor\s+", text):
            # for loop: 2 branches (loop continues/exits)
            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="loop",
                    description=self._generate_description(text, "loop iteration"),
                    score="sure",
                )
            )

            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="exit",
                    description=self._generate_description(text, "loop exit"),
                    score="maybe",
                )
            )

        elif re.search(r"\btry\s*:", text):
            # try block: 2 branches (success/exception)
            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="try_success",
                    description=self._generate_description(text, "try block success"),
                    score="sure",
                )
            )

            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="try_exception",
                    description=self._generate_description(text, "exception raised"),
                    score="maybe",
                )
            )

        elif re.search(r"\bexcept\s+", text):
            # except block: single branch
            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="except",
                    description=self._generate_description(text, "exception handler"),
                    score="unlikely",  # Exceptions are less common
                )
            )

        else:
            # Generic conditional: 2 branches
            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="branch_1",
                    description=self._generate_description(text, "branch 1"),
                    score="maybe",
                )
            )

            branches.append(
                self._create_branch(
                    line_num=line_num,
                    suffix="branch_2",
                    description=self._generate_description(text, "branch 2"),
                    score="maybe",
                )
            )

        return branches

    def _create_branch(
        self, line_num: int, suffix: str, description: str, score: str
    ) -> dict[str, Any]:
        """
        Create a branch dict with auto-generated ID.

        Args:
            line_num: Line number where branch occurs
            suffix: Suffix to make ID unique
            description: Human-readable branch description
            score: Branch score ('sure', 'maybe', 'unlikely')

        Returns:
            Branch dict with 'id', 'description', 'score'
        """
        self._branch_counter += 1
        return {"id": f"b_{self._branch_counter}", "description": description, "score": score}

    def _generate_description(self, conditional_text: str, path_type: str) -> str:
        """
        Generate a human-readable description for a branch.

        Args:
            conditional_text: The conditional statement text
            path_type: Type of path (e.g., 'true path', 'false path')

        Returns:
            Human-readable branch description
        """
        # Extract the condition part
        match = re.search(r"(if|elif|for|while|except)\s*\(?([^)]+)\)?", conditional_text)
        if match:
            condition = match.group(2).strip()
            return f"Path: {path_type} when {condition}"
        else:
            return f"Path: {path_type}"

    def _score_branch(self, conditional_text: str, path_type: str) -> str:
        """
        Score a branch based on its likelihood.

        Args:
            conditional_text: The conditional statement text
            path_type: Type of path (e.g., 'true', 'false', 'elif')

        Returns:
            Branch score: 'sure', 'maybe', or 'unlikely'
        """
        text_lower = conditional_text.lower()

        # Check for sure indicators (use word boundaries to avoid partial matches)
        for keyword in self.SURE_KEYWORDS:
            if re.search(r"\b" + re.escape(keyword) + r"\b", text_lower):
                return "sure"

        # Check for unlikely indicators (use word boundaries)
        for keyword in self.UNLIKELY_KEYWORDS:
            if re.search(r"\b" + re.escape(keyword) + r"\b", text_lower):
                return "unlikely"

        # Check path type
        if path_type in ["true", "loop", "try_success"]:
            return "sure"
        elif path_type in ["false", "exit", "try_exception", "except"]:
            return "maybe"

        # Default to maybe
        return "maybe"


if __name__ == "__main__":
    # Example usage
    sample_code = """
def handle_request(request):
    if request.method == 'GET':
        return handle_get(request)
    elif request.method == 'POST':
        return handle_post(request)
    else:
        return error('Method not allowed')
"""

    generator = BranchGenerator(sample_code)
    branches = generator.generate_branches()

    print("Generated Branches:")
    for branch in branches:
        print(f"  {branch['id']}: {branch['description']}")
        print(f"    Score: {branch['score']}")
