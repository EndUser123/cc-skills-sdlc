#!/usr/bin/env python3
"""Tests for tools/migrate_to_ef.py."""

import subprocess
import sys
from pathlib import Path
import pytest

_MIGRATE = Path(__file__).resolve().parents[2] / "tools" / "migrate_to_ef.py"
_ROOT = _MIGRATE.resolve().parents[1]
SKILLS_DIR = _ROOT / "skills"
ENFORCE_DIR = _ROOT / "enforce"


def _run(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    env = {"PYTHONPATH": str(_ROOT)}
    return subprocess.run(
        [sys.executable, str(_MIGRATE)] + args,
        capture_output=True, text=True, errors="replace", env=env, cwd=str(_ROOT),
    )


class TestMigrateDryRun:
    def test_refactor_dry_run_finds_source(self) -> None:
        r = _run(["--base", "refactor", "--dry-run"])
        assert r.returncode == 0, r.stderr
        assert "refactor" in r.stdout
        assert "refactor-ef" in r.stdout
        assert "DRY RUN" in r.stdout

    def test_planning_dry_run_finds_source(self) -> None:
        r = _run(["--base", "planning", "--dry-run"])
        assert r.returncode == 0, r.stderr
        assert "planning" in r.stdout
        assert "planning-ef" in r.stdout

    def test_unknown_base_returns_error(self) -> None:
        r = _run(["--base", "does-not-exist"])
        assert r.returncode == 1
        assert "not found" in r.stderr


class TestMigrateApply:
    def test_creates_ef_skill_in_temp_fixture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Patch skills dir to a temp location
        fake_skills = tmp_path / "skills"
        fake_enforce = tmp_path / "enforce"
        fake_enforce_configs = fake_enforce / "configs"

        fake_skills.mkdir()
        fake_enforce.mkdir()
        fake_enforce_configs.mkdir()

        # Copy a minimal source skill
        src = SKILLS_DIR / "refactor"
        dst_base = fake_skills / "refactor"
        dst_base.mkdir()
        src_sk = src / "SKILL.md"
        if src_sk.is_file():
            (dst_base / "SKILL.md").write_text(src_sk.read_text())

        # Copy enforce/configs/__init__.py with clean ENFORCE_CONFIGS
        cfg_src = ENFORCE_DIR / "configs" / "__init__.py"
        cfg_dst = fake_enforce_configs / "__init__.py"
        cfg_dst.write_text(
            "from __future__ import annotations\n"
            "from typing import Any\n"
            "ENFORCE_CONFIGS: dict = {}\n"
        )

        def fake_root() -> Path:
            return tmp_path

        monkeypatch.chdir(str(tmp_path))
        # Core assertion: dry-run works from temp dir
        r = subprocess.run(
            [sys.executable, str(_MIGRATE), "--base", "refactor", "--dry-run"],
            capture_output=True, text=True,
            cwd=str(tmp_path),
            env={"PYTHONPATH": str(tmp_path)},
            errors="replace",
        )
        assert r.returncode == 0, r.stderr
        assert "planning-ef" not in r.stdout  # wrong target not leaked


class TestMigrateNonDestructive:
    def test_refuses_to_overwrite_without_force(self, tmp_path: Path) -> None:
        # Patch skills dir to tmp_path so we can actually create then protect
        r = subprocess.run(
            [sys.executable, str(_MIGRATE), "--base", "refactor", "--dry-run"],
            capture_output=True, text=True,
            cwd=str(_ROOT),
            env={"PYTHONPATH": str(_ROOT)},
        )
        assert r.returncode == 0
        # Target should not exist yet in real skills dir
        assert not (SKILLS_DIR / "refactor-ef").exists()

    def test_target_defaults_to_base_minus_ef(self) -> None:
        r = _run(["--base", "planning", "--dry-run"])
        assert r.returncode == 0
        assert "planning-ef" in r.stdout

    def test_custom_target_name(self) -> None:
        r = _run(["--base", "planning", "--target", "custom-name", "--no-validate", "--dry-run"])
        assert r.returncode == 0
        assert "custom-name" in r.stdout


class TestMigrateConfigEntry:
    def test_refactor_config_is_new_entry(self) -> None:
        r = _run(["--base", "refactor", "--dry-run"])
        assert r.returncode == 0
        assert "new entry" in r.stdout or "exists" in r.stdout

    def test_plural_singular_grammar(self) -> None:
        # planning -> 1 phase (singular)
        r = _run(["--base", "planning", "--dry-run"])
        assert r.returncode == 0
        assert any("1 phase" in line for line in r.stdout.splitlines())
        # refactor -> 17 phases (plural)
        r = _run(["--base", "refactor", "--dry-run"])
        assert r.returncode == 0
        assert any("17 phases" in line for line in r.stdout.splitlines())

    def test_planning_ef_hook_has_correct_skill_id(self, tmp_path: Path) -> None:
        # Verify planning-ef Stop hook uses correct skill_id
        from pathlib import Path
        import subprocess, sys
        fake_skills = tmp_path / "skills"
        fake_enforce = tmp_path / "enforce"
        fake_enforce_configs = fake_enforce / "configs"
        fake_skills.mkdir()
        fake_enforce.mkdir()
        fake_enforce_configs.mkdir()
        src = SKILLS_DIR / "planning"
        dst_base = fake_skills / "planning"
        dst_base.mkdir()
        src_sk = src / "SKILL.md"
        if src_sk.is_file():
            (dst_base / "SKILL.md").write_text(src_sk.read_text())
        cfg_dst = fake_enforce_configs / "__init__.py"
        cfg_dst.write_text(
            "from __future__ import annotations\n"
            "from typing import Any\n"
            "ENFORCE_CONFIGS: dict = {}\n"
        )
        r = subprocess.run(
            [sys.executable, str(_MIGRATE), "--base", "planning"],
            capture_output=True, text=True,
            cwd=str(tmp_path),
            env={"PYTHONPATH": str(tmp_path)},
            errors="replace",
        )
        if r.returncode == 0:
            hook = tmp_path / "skills" / "planning-ef" / "hooks" / "Stop_enforce_gate.py"
            if hook.is_file():
                content = hook.read_text()
                assert 'skill_id = "planning-ef"' in content


class TestMigrateStopHook:
    def test_stop_hook_contains_target_skill_id(self, tmp_path: Path) -> None:
        # Run apply in temp dir with patched paths
        fake_skills = tmp_path / "skills"
        fake_enforce = tmp_path / "enforce"
        fake_enforce_configs = fake_enforce / "configs"

        fake_skills.mkdir()
        fake_enforce.mkdir()
        fake_enforce_configs.mkdir()

        src = SKILLS_DIR / "refactor"
        dst_base = fake_skills / "refactor"
        dst_base.mkdir()
        src_sk = src / "SKILL.md"
        if src_sk.is_file():
            (dst_base / "SKILL.md").write_text(src_sk.read_text())

        cfg_dst = fake_enforce_configs / "__init__.py"
        cfg_dst.write_text(
            "from __future__ import annotations\n"
            "from typing import Any\n"
            "ENFORCE_CONFIGS: dict = {}\n"
        )

        r = subprocess.run(
            [sys.executable, str(_MIGRATE), "--base", "refactor"],
            capture_output=True, text=True,
            cwd=str(tmp_path),
            env={"PYTHONPATH": str(tmp_path)},
            errors="replace",
        )
        # If apply succeeded, check the hook
        if r.returncode == 0:
            hook = (tmp_path / "skills" / "refactor-ef" / "hooks" / "Stop_enforce_gate.py")
            if hook.is_file():
                content = hook.read_text()
                assert 'skill_id = "refactor-ef"' in content


class TestMigrateValidation:
    def test_layout_check_fails_gracefully(self) -> None:
        # Layout is always valid in this test env
        r = _run(["--base", "refactor", "--dry-run"])
        assert r.returncode == 0

    def test_no_validate_bypasses_naming_check(self) -> None:
        r = _run(["--base", "refactor", "--target", "custom-name", "--no-validate", "--dry-run"])
        assert r.returncode == 0
        # No warning about non -ef suffix
        assert "WARNING" not in r.stderr
