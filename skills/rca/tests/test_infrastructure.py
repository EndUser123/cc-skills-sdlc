"""Infrastructure tests for rca implementation.

These tests verify the foundational directory structure and module imports
required for the rca implementation.

Run with: pytest P:/packages/rca/skill/tests/test_infrastructure.py -v
"""

import sys
from pathlib import Path

import pytest


class TestDirectoryStructure:
    """Tests for rca directory structure existence."""

    @pytest.fixture
    def package_root(self):
        """Return the root path of the rca package."""
        return Path("P:/packages/rca/src/rca")

    @pytest.fixture
    def tier1_dir(self, package_root):
        """Return the Tier 1 subdirectory path."""
        return package_root / "tier1"

    @pytest.fixture
    def skill_root(self):
        """Return the root path of the rca skill."""
        return Path("P:/packages/rca/skill")

    def test_package_directory_exists(self, package_root):
        """Test that main rca package directory exists.

        Given: The rca package is being set up
        When: Checking the main package directory
        Then: The rca directory should exist at P:/packages/rca/src/rca
        """
        assert package_root.exists(), f"rca package not found at {package_root}"
        assert package_root.is_dir(), f"rca path is not a directory: {package_root}"

    def test_tier1_subdirectory_exists(self, tier1_dir):
        """Test that Tier 1 modules are flattened in main package.

        Given: The rca flattened structure (no tier1 subdirectory)
        When: Checking the main package directory
        Then: The tier1 modules should be directly in rca
        """
        # After flattening, tier1 modules are in the main package
        # tier1_dir fixture points to package root after refactor
        # Check for key tier1 modules in main package
        assert (
            tier1_dir.parent / "evidence_saturation.py"
        ).exists(), "evidence_saturation.py not found in main package"
        assert (
            tier1_dir.parent / "phase_state_manager.py"
        ).exists(), "phase_state_manager.py not found in main package"
        assert (
            tier1_dir.parent / "hypothesis_scorer.py"
        ).exists(), "hypothesis_scorer.py not found in main package"
        # Verify tier1 subdirectory does NOT exist (flattened)
        assert (
            not tier1_dir.exists()
        ), f"tier1 subdirectory should not exist after flattening, found at {tier1_dir}"

    def test_skill_directory_exists(self, skill_root):
        """Test that skill directory exists with hooks and templates."""
        assert skill_root.exists(), f"Skill directory not found at {skill_root}"
        assert (skill_root / "hooks").exists(), "Hooks directory should exist"
        assert (skill_root / "templates").exists(), "Templates directory should exist"


class TestModuleImports:
    """Tests for rca module importability."""

    @pytest.fixture(autouse=True)
    def setup_path(self):
        """Add package src to path for imports."""
        package_src = str(Path("P:/packages/rca/src").resolve())
        if package_src not in sys.path:
            sys.path.insert(0, package_src)

    def test_rca_init_importable(self):
        """Test that rca __init__.py is importable.

        Given: The rca package structure
        When: Attempting to import the rca package
        Then: The import should succeed without ImportError
        """
        try:
            from rca import __version__  # noqa: F401

            assert isinstance(__version__, str), "__version__ should be a string"
        except ImportError as e:
            pytest.fail(f"Failed to import rca module: {e}")

    def test_evidence_saturation_module_importable(self):
        """Test that evidence_saturation module can be imported.

        Given: The evidence saturation algorithm is a Tier 1 component
        When: Attempting to import the evidence_saturation module
        Then: The import should succeed and EvidenceSaturationDetector should be available
        """
        try:
            from rca.evidence_saturation import EvidenceSaturationDetector  # noqa: F401

            assert EvidenceSaturationDetector is not None
        except (ImportError, AttributeError) as e:
            pytest.fail(f"Failed to import EvidenceSaturationDetector: {e}")

    def test_phase_state_manager_module_importable(self):
        """Test that phase_state_manager module can be imported.

        Given: Phase state persistence is a Tier 1 component
        When: Attempting to import the phase_state_manager module
        Then: The import should succeed and PhaseStateManager should be available
        """
        try:
            from rca.phase_state_manager import PhaseStateManager  # noqa: F401

            assert PhaseStateManager is not None
        except (ImportError, AttributeError) as e:
            pytest.fail(f"Failed to import PhaseStateManager: {e}")

    def test_hypothesis_scorer_module_importable(self):
        """Test that hypothesis_scorer module can be imported.

        Given: Hypothesis scoring framework is a Tier 1 component
        When: Attempting to import the hypothesis_scorer module
        Then: The import should succeed and HypothesisScorer should be available
        """
        try:
            from rca.hypothesis_scorer import HypothesisScorer  # noqa: F401

            assert HypothesisScorer is not None
        except (ImportError, AttributeError) as e:
            pytest.fail(f"Failed to import HypothesisScorer: {e}")

    def test_tier1_imports_from_main_package(self):
        """Test that Tier 1 classes can be imported from main rca package.

        Given: The rca package with flattened Tier 1 components
        When: Importing Tier 1 classes from rca
        Then: The imports should succeed
        """
        try:
            from rca import (
                ConvergeValidator,
                DebugPyClient,
                EvidenceSaturationDetector,
                HypothesisScorer,
                PhaseStateManager,
            )

            # All should be importable
            assert EvidenceSaturationDetector is not None
            assert PhaseStateManager is not None
            assert HypothesisScorer is not None
            assert ConvergeValidator is not None
            assert DebugPyClient is not None
        except ImportError as e:
            pytest.fail(f"Failed to import Tier 1 classes from rca: {e}")


class TestTier1Modules:
    """Tests for Tier 1 module files in flattened structure."""

    @pytest.fixture
    def package_root(self):
        """Return the rca package root path."""
        return Path("P:/packages/rca/src/rca")

    def test_evidence_saturation_exists(self, package_root):
        """Test that evidence_saturation.py exists in main package."""
        module_file = package_root / "evidence_saturation.py"
        assert module_file.exists(), f"evidence_saturation.py not found at {module_file}"

    def test_phase_state_manager_exists(self, package_root):
        """Test that phase_state_manager.py exists in main package."""
        module_file = package_root / "phase_state_manager.py"
        assert module_file.exists(), f"phase_state_manager.py not found at {module_file}"

    def test_hypothesis_scorer_exists(self, package_root):
        """Test that hypothesis_scorer.py exists in main package."""
        module_file = package_root / "hypothesis_scorer.py"
        assert module_file.exists(), f"hypothesis_scorer.py not found at {module_file}"

    @pytest.mark.xfail(reason="LocalFallbackMode not yet implemented - planned feature")
    def test_local_fallback_mode_exists(self, package_root):
        """Test that local_fallback_mode.py exists in main package."""
        module_file = package_root / "local_fallback_mode.py"
        assert module_file.exists(), f"local_fallback_mode.py not found at {module_file}"

    def test_quality_estimator_exists(self, package_root):
        """Test that quality_estimator.py exists in main package."""
        module_file = package_root / "quality_estimator.py"
        assert module_file.exists(), f"quality_estimator.py not found at {module_file}"

    def test_converge_validator_exists(self, package_root):
        """Test that converge_validator.py exists in main package."""
        module_file = package_root / "converge_validator.py"
        assert module_file.exists(), f"converge_validator.py not found at {module_file}"

    def test_debugpy_client_exists(self, package_root):
        """Test that debugpy_client.py exists in main package."""
        module_file = package_root / "debugpy_client.py"
        assert module_file.exists(), f"debugpy_client.py not found at {module_file}"
