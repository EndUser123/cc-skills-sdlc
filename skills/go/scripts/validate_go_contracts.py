#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:
    print("ERROR: missing dependency 'jsonschema' (pip install jsonschema)", file=sys.stderr)
    sys.exit(2)


SCHEMA_FILES = {
    "run": "run.schema.json",
    "selected-task": "selected-task.schema.json",
    "dispatch-decision": "dispatch-decision.schema.json",
    "dispatch-result": "dispatch-result.schema.json",
}

FILE_PREFIX_TO_SCHEMA_KEY = {
    "run_": "run",
    "selected-task_": "selected-task",
    "dispatch-decision_": "dispatch-decision",
    "dispatch-result_": "dispatch-result",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_schemas(schema_dir: Path) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for key, filename in SCHEMA_FILES.items():
        schema_path = schema_dir / filename
        if not schema_path.exists():
            raise FileNotFoundError(f"Missing schema file: {schema_path}")
        schemas[key] = load_json(schema_path)
    return schemas


def infer_schema_key(file_path: Path) -> str | None:
    name = file_path.name
    for prefix, schema_key in FILE_PREFIX_TO_SCHEMA_KEY.items():
        if name.startswith(prefix) and name.endswith(".json"):
            return schema_key
    return None


def validate_file(file_path: Path, schemas: dict[str, dict[str, Any]]) -> tuple[bool, str]:
    schema_key = infer_schema_key(file_path)
    if schema_key is None:
        return False, f"SKIP  {file_path}  (no matching schema by filename)"

    try:
        payload = load_json(file_path)
    except Exception as e:
        return False, f"FAIL  {file_path}  invalid JSON: {e}"

    schema = schemas[schema_key]
    validator = jsonschema.Draft202012Validator(schema)

    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.path) or "<root>"
        return False, f"FAIL  {file_path}  schema={schema_key}  path={path}  error={first.message}"

    return True, f"PASS  {file_path}  schema={schema_key}"


def validate_directory(artifact_dir: Path, schemas: dict[str, dict[str, Any]]) -> int:
    candidates = sorted(
        p for p in artifact_dir.iterdir()
        if p.is_file() and p.suffix == ".json" and infer_schema_key(p) is not None
    )

    if not candidates:
        print(f"ERROR: no matching contract JSON files found in {artifact_dir}", file=sys.stderr)
        return 1

    failures = 0
    for path in candidates:
        ok, message = validate_file(path, schemas)
        print(message)
        if not ok and message.startswith("FAIL"):
            failures += 1

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate /go v3.1 contract JSON files against local schemas."
    )
    parser.add_argument(
        "--schema-dir",
        required=True,
        help="Directory containing run.schema.json, selected-task.schema.json, dispatch-decision.schema.json, dispatch-result.schema.json",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--file", help="Validate a single JSON file")
    target.add_argument("--artifact-dir", help="Validate all matching JSON files in a /go artifact directory")

    args = parser.parse_args()

    schema_dir = Path(args.schema_dir).resolve()
    if not schema_dir.exists():
        print(f"ERROR: schema dir not found: {schema_dir}", file=sys.stderr)
        return 2

    try:
        schemas = load_schemas(schema_dir)
    except Exception as e:
        print(f"ERROR: failed to load schemas: {e}", file=sys.stderr)
        return 2

    if args.file:
        file_path = Path(args.file).resolve()
        if not file_path.exists():
            print(f"ERROR: file not found: {file_path}", file=sys.stderr)
            return 2
        ok, message = validate_file(file_path, schemas)
        print(message)
        return 0 if ok else 1

    artifact_dir = Path(args.artifact_dir).resolve()
    if not artifact_dir.exists():
        print(f"ERROR: artifact dir not found: {artifact_dir}", file=sys.stderr)
        return 2

    return validate_directory(artifact_dir, schemas)


if __name__ == "__main__":
    raise SystemExit(main())
