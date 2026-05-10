#!/usr/bin/env python3
"""
Fix Git Bash paths in state JSON files.

Scans state directory for JSON files containing Git Bash paths (/p/...)
and normalizes them to Windows native format (P:\\\\\\\...).

Functions:
    detect_git_bash_paths: Recursively find Git Bash paths in JSON data
    normalize_git_bash_path: Convert Git Bash path to Windows format
    fix_paths_in_data: Normalize all Git Bash paths in JSON data structure
    fix_paths_in_file: Process a single JSON file
    find_state_files: Recursively find all JSON files in directory
    fix_paths_in_directory: Batch process all JSON files
    main: CLI entry point

Author: /code skill improvement document
Date: 2026-03-01
"""

import argparse
import json
import logging
import re
import shutil
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# Git Bash path pattern: /[letter]/path (e.g., /p/.claude/skills/code)
GIT_BASH_PATTERN = re.compile(r'^/[a-z]/[\w/\-.]+')


def detect_git_bash_paths(data: Any) -> list[str]:
    """Recursively scan JSON data for Git Bash path strings.

    Args:
        data: Any JSON-serializable data (dict, list, str, etc.)

    Returns:
        List of detected Git Bash path strings.
    """
    git_paths = []

    if isinstance(data, str):
        # Check if string matches Git Bash path pattern
        if GIT_BASH_PATTERN.match(data):
            git_paths.append(data)
    elif isinstance(data, dict):
        # Recursively scan dictionary values
        for value in data.values():
            git_paths.extend(detect_git_bash_paths(value))
    elif isinstance(data, list):
        # Recursively scan list items
        for item in data:
            git_paths.extend(detect_git_bash_paths(item))

    return git_paths


def normalize_git_bash_path(path: str) -> str:
    """Convert Git Bash path to Windows native format.

    Args:
        path: Git Bash path string (e.g., /p/.claude/skills/code)

    Returns:
        Normalized Windows path (e.g., P:\\\\\\\.claude\\skills\\code)
    """
    if path is None:
        return None
    if not path:
        return path

    # Only normalize Git Bash paths (/[letter]/...)
    # Leave other paths unchanged (relative paths, Windows paths, etc.)
    if not GIT_BASH_PATTERN.match(path):
        return path

    # Convert Git Bash path to Windows format
    # Extract drive letter and convert /p/... to P:\\\\\\...
    drive_letter = path[1].upper()
    rest = path[2:]
    result = f"{drive_letter}:{rest}"

    # Convert forward slashes to backslashes
    result = result.replace('/', '\\')

    # Double the backslashes for JSON serialization consistency
    result = result.replace('\\', '\\\\')

    return result


# Alias for test compatibility
normalize_path = normalize_git_bash_path


def fix_paths_in_data(data: Any) -> tuple[Any, int]:
    """Recursively normalize all Git Bash paths in JSON data.

    Args:
        data: Any JSON-serializable data structure.

    Returns:
        Tuple of (modified_data, count_of_paths_normalized)
    """
    count = 0

    if isinstance(data, str):
        # Check if string is a Git Bash path
        if GIT_BASH_PATTERN.match(data):
            return normalize_git_bash_path(data), 1
        return data, 0
    elif isinstance(data, dict):
        # Recursively process dictionary values
        new_dict = {}
        for key, value in data.items():
            new_value, value_count = fix_paths_in_data(value)
            new_dict[key] = new_value
            count += value_count
        return new_dict, count
    elif isinstance(data, list):
        # Recursively process list items
        new_list = []
        for item in data:
            new_item, item_count = fix_paths_in_data(item)
            new_list.append(new_item)
            count += item_count
        return new_list, count
    else:
        # Return other types unchanged (int, bool, None, etc.)
        return data, 0


def fix_paths_in_file_with_rollback(
    file_path: str | Path,
    backup: bool = True,
    simulate_error: bool = False
) -> dict:
    """Fix paths in file with rollback on error.

    Args:
        file_path: Path to JSON file.
        backup: Whether to create backup before modification.
        simulate_error: If True, simulate an error for testing rollback.

    Returns:
        Dict with operation results.
    """
    file_path = Path(file_path)
    backup_path = None

    try:
        # Load JSON file
        data = json.loads(file_path.read_text())

        # Create backup if requested
        if backup:
            backup_path = file_path.with_suffix('.json.backup')
            shutil.copy2(file_path, backup_path)
            logger.debug(f"Created backup: {backup_path}")

        # Fix paths in data
        modified_data, count = fix_paths_in_data(data)

        # Simulate error for testing rollback
        if simulate_error:
            raise RuntimeError("Simulated error for testing rollback")

        # Write modified data back to file
        file_path.write_text(json.dumps(modified_data, indent=2))

        return {
            'backup_path': str(backup_path) if backup_path else None,
            'paths_normalized': count,
            'success': True
        }

    except Exception as e:
        # Rollback: restore from backup if it exists
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, file_path)
            backup_path.unlink()
            logger.debug("Rolled back changes and removed backup")

        return {
            'backup_path': None,
            'paths_normalized': 0,
            'success': False,
            'error': str(e)
        }


def fix_paths_in_file(file_path: str | Path, backup: bool = True) -> int:
    """Load JSON file, normalize paths, and write back.

    Args:
        file_path: Path to JSON file.
        backup: Whether to create backup before modification.

    Returns:
        Number of paths normalized.
    """
    file_path = Path(file_path)

    try:
        # Load JSON file
        data = json.loads(file_path.read_text())

        # Create backup if requested
        backup_path = None
        if backup:
            backup_path = file_path.with_suffix('.json.backup')
            shutil.copy2(file_path, backup_path)

        # Fix paths in data
        modified_data, count = fix_paths_in_data(data)

        # Write modified data back to file
        file_path.write_text(json.dumps(modified_data, indent=2))

        return count

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return 0


def find_state_files(state_dir: str | Path) -> list[Path]:
    """Recursively scan directory for JSON files.

    Args:
        state_dir: Root directory to scan.

    Returns:
        List of Path objects for all JSON files found.
    """
    state_dir = Path(state_dir)

    if not state_dir.exists():
        logger.warning(f"State directory does not exist: {state_dir}")
        return []

    # Find all .json files recursively
    json_files = list(state_dir.rglob('*.json'))

    # Filter out backup files
    json_files = [f for f in json_files if not f.suffix == '.backup']

    return json_files


def fix_paths_in_directory(
    state_dir: str | Path,
    backup: bool = True,
    dry_run: bool = False
) -> dict:
    """Batch process all JSON files in state directory.

    Args:
        state_dir: Root directory containing JSON files.
        backup: Whether to create backups before modification.
        dry_run: If True, report changes without executing.

    Returns:
        Dict mapping file paths to number of paths normalized.
    """
    state_dir = Path(state_dir)
    results = {}

    # Find all JSON files
    json_files = find_state_files(state_dir)

    if dry_run:
        # Dry run: just report what would change
        for json_file in json_files:
            try:
                data = json.loads(json_file.read_text())
                git_paths = detect_git_bash_paths(data)
                results[str(json_file)] = len(git_paths)

                if git_paths:
                    logger.info(f"Would fix {len(git_paths)} paths in {json_file.relative_to(state_dir)}")
                    for path in git_paths:
                        logger.info(f"  {path} -> {normalize_git_bash_path(path)}")

            except Exception as e:
                logger.error(f"Error scanning {json_file}: {e}")
                results[str(json_file)] = 0
    else:
        # Normal operation: fix paths in files
        for json_file in json_files:
            try:
                count = fix_paths_in_file(json_file, backup=backup)
                results[str(json_file)] = count

                if count > 0:
                    backup_file = json_file.with_suffix('.json.backup')
                    logger.info(f"Fixed {count} path(s) in {json_file.relative_to(state_dir)}")
                    if backup and backup_file.exists():
                        logger.info(f"  Backup: {backup_file.relative_to(state_dir)}")

            except Exception as e:
                logger.error(f"Error processing {json_file}: {e}")
                results[str(json_file)] = 0

    return results


def fix_paths_main(state_dir: str | Path, backup: bool = True, dry_run: bool = False) -> dict:
    """Main entry point for path fixing operations.

    Args:
        state_dir: Root directory containing JSON files.
        backup: Whether to create backups before modification.
        dry_run: If True, report changes without executing.

    Returns:
        Dict mapping file paths to number of paths normalized.
    """
    state_dir = Path(state_dir)

    if not state_dir.exists():
        logger.error(f"State directory does not exist: {state_dir}")
        return {}

    # Find all JSON files
    json_files = find_state_files(state_dir)

    if not json_files:
        logger.warning(f"No JSON files found in {state_dir}")
        return {}

    logger.info("Fixing Git Bash paths in state files...")
    logger.info("")

    # Detect all Git Bash paths
    total_git_paths = 0
    for json_file in json_files:
        try:
            data = json.loads(json_file.read_text())
            git_paths = detect_git_bash_paths(data)
            total_git_paths += len(git_paths)
        except Exception:
            pass

    logger.info(f"Scanned: {len(json_files)} JSON file(s)")
    logger.info(f"Found: {total_git_paths} Git Bash path(s) to normalize")
    logger.info("")

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("")

    # Process files
    results = fix_paths_in_directory(state_dir, backup=backup, dry_run=dry_run)

    # Print summary
    if not dry_run:
        total_fixed = sum(count for count in results.values())
        logger.info("")
        logger.info(f"Summary: {total_fixed} path(s) normalized in {len(results)} file(s)")

    return results


def main() -> int:
    """CLI entry point with argparse.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description='Fix Git Bash paths in state JSON files'
    )
    parser.add_argument(
        '--state-dir',
        type=str,
        default=str(Path.cwd() / '.claude' / 'state'),
        help='Path to state directory (default: .claude/state)'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create backup files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report changes without executing'
    )

    args = parser.parse_args()

    # Convert state_dir to Path
    state_dir = Path(args.state_dir)

    # Run main function
    try:
        results = fix_paths_main(
            state_dir=state_dir,
            backup=not args.no_backup,
            dry_run=args.dry_run
        )

        # Check if any files were processed
        if not results:
            return 1

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
