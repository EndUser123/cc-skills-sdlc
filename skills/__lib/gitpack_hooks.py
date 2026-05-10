#!/usr/bin/env python3
"""GitPack for skill-guard + cc-skills-sdlc hooks diagnostic."""
import ast
import json
import os
from pathlib import Path
from datetime import datetime

TARGETS = [
    ('skill-guard', 'P:\\\\\\packages/skill-guard/src/skill_guard'),
    ('sdlc/code_v3.0/hooks', 'P:\\\\\\packages/cc-skills-sdlc/skills/code_v3.0/hooks'),
    ('sdlc/rca/hooks', 'P:\\\\\\packages/cc-skills-sdlc/skills/rca/hooks'),
    ('sdlc/refactor/hooks', 'P:\\\\\\packages/cc-skills-sdlc/skills/refactor/hooks'),
    ('sdlc/design/hooks', 'P:\\\\\\packages/cc-skills-sdlc/skills/design/hooks'),
    ('sdlc/pre-mortem/hooks', 'P:\\\\\\packages/cc-skills-sdlc/skills/pre-mortem/hooks'),
    ('sdlc/hooks.json', 'P:\\\\\\packages/cc-skills-sdlc/hooks'),
]

EXCLUDE_DIRS = {'__pycache__', '.git', '.venv', 'venv', 'site-packages', '.ruff_cache', '.mypy_cache', '.pytest_cache'}

OUTPUT_DIR = Path('P:\\\\\\.claude/.artifacts/')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_signatures(filepath):
    """Extract function/class signatures from a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=str(filepath))
    except Exception as e:
        return f'[PARSE ERROR: {e}]'

    sigs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            method_sigs = []
            for m in methods[:15]:
                args = [a.arg for a in m.args.args[:6]]
                ret_type = ast.unparse(m.returns) if m.returns else ''
                args_str = ', '.join(args[:5])
                if args_str:
                    method_sigs.append(f'    def {m.name}({args_str}, ...): {ret_type}')
                else:
                    method_sigs.append(f'    def {m.name}(): {ret_type}')
            if method_sigs:
                sigs.append(f'class {node.name}:\n' + '\n'.join(method_sigs))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args[:6]]
            ret_type = ast.unparse(node.returns) if node.returns else ''
            args_str = ', '.join(args)
            sigs.append(f'def {node.name}({args_str}): {ret_type}')

    return '\n'.join(sigs[:60])


def get_files(root):
    files = []
    root_path = Path(root)
    if not root_path.exists():
        return files
    for pyfile in root_path.rglob('*.py'):
        if any(ex in pyfile.parts for ex in EXCLUDE_DIRS):
            continue
        files.append(pyfile)
    hooks_json = root_path / 'hooks.json'
    if hooks_json.exists():
        files.append(hooks_json)
    return sorted(set(files))


def main():
    parts = []
    parts.append(f'# GitPack: skill-guard + cc-skills-sdlc hooks\n')
    parts.append(f'**Generated:** {datetime.now().isoformat()}\n')
    parts.append(f'**Purpose:** Debug hook firing and manual skill invocation issues\n\n')
    parts.append('## HOOK REGISTRATION OVERVIEW\n\n')
    parts.append('```\n')

    # Show plugin hook registration
    for name, path in TARGETS:
        if name.endswith('.json'):
            parts.append(f'  {name}: {path}\n')
            try:
                with open(path) as f:
                    data = json.load(f)
                for hook_type, configs in data.get('hooks', {}).items():
                    parts.append(f'    {hook_type}: {len(configs)} config(s)\n')
                    for cfg in configs:
                        cmd = cfg.get('hooks', [{}])[0].get('command', 'N/A') if cfg.get('hooks') else 'N/A'
                        parts.append(f'      - matcher: {cfg.get("matcher", "*")}, cmd: {cmd[:80]}\n')
            except Exception as e:
                parts.append(f'    ERROR: {e}\n')
        else:
            files = get_files(path)
            parts.append(f'  {name}: {len(files)} file(s) in {path}\n')

    parts.append('```\n\n')

    for name, path in TARGETS:
        files = get_files(path)
        parts.append(f'## {name}\n')
        parts.append(f'**Path:** `{path}`\n')
        parts.append(f'**Files ({len(files)}):**\n\n')

        for f in files:
            try:
                size = f.stat().st_size
            except:
                size = 0
            parts.append(f'### `{f.name}` ({size:,} bytes)\n')

            if f.suffix == '.json':
                try:
                    with open(f) as jf:
                        data = json.load(jf)
                    parts.append('```json\n' + json.dumps(data, indent=2)[:3000] + '\n```\n')
                except Exception as e:
                    parts.append(f'[JSON error: {e}]\n')
            else:
                sigs = extract_signatures(f)
                parts.append('```python\n' + sigs + '\n```\n\n')

    sig_file = OUTPUT_DIR / 'gitpack_skillguard_sdlc_sig.md'
    full_file = OUTPUT_DIR / 'gitpack_skillguard_sdlc_full.md'

    with open(sig_file, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))

    with open(full_file, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))
        f.write('\n\n## FULL SOURCE APPENDIX\n\n')

        for name, path in TARGETS:
            files = get_files(path)
            f: Path
            for f in files:
                if f.suffix == '.json':
                    continue
                try:
                    with open(f, 'r', encoding='utf-8') as src:
                        content = src.read()
                except Exception as e:
                    content = f'[READ ERROR: {e}]'

                f_rel = f.relative_to(Path('P:\\\\\\packages'))
                parts.append(f'### {f_rel}\n\n')
                parts.append('```python\n' + content + '\n```\n\n')

    print(f'Written: {sig_file}')
    print(f'Written: {full_file}')
    print(f'Total chars: {len("".join(parts)):,}')


if __name__ == '__main__':
    main()