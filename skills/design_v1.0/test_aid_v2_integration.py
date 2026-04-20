"""
Test AID Integration v2 for /arch skill

Verifies CLI-based AID integration works correctly.
"""

import tempfile
from pathlib import Path

from aid_wrapper_v2 import create_aid_integrator


def test_aid_integrator_creation():
    """Test that AidIntegratorV2 can be created."""
    print("Testing AID integrator creation...")

    try:
        integrator = create_aid_integrator()
        print("✅ AID integrator created successfully")
        print(f"   AID path: {integrator._aid_path}")
        return True
    except RuntimeError as e:
        print(f"❌ AID integrator creation failed: {e}")
        print("   Install AID CLI from: https://github.com/janreges/ai-distiller/releases")
        return False


def test_basic_distillation():
    """Test basic code distillation."""
    print("\nTesting basic distillation...")

    # Create a simple test file
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_file = tmpdir_path / "test_module.py"
        test_file.write_text('''
"""
Test module for AID distillation.
"""
from typing import List, Dict

class DataProcessor:
    """Process data items."""

    def __init__(self, config: Dict):
        self.config = config

    def process(self, items: List[str]) -> List[str]:
        """Process a list of items."""
        return [item.upper() for item in items]

def helper_function(value: int) -> int:
    """Helper for calculations."""
    return value * 2
''')

        try:
            integrator = create_aid_integrator()
            result = integrator.distill(tmpdir_path)

            print("✅ Basic distillation succeeded")
            print(f"   Files analyzed: {result.files_analyzed}")
            print(f"   Compression ratio: {result.compression_ratio:.1%}")
            print(f"   Distilled structure length: {len(result.distilled_structure)} chars")

            # Verify we got some output
            assert result.files_analyzed > 0, "No files analyzed"
            assert len(result.distilled_structure) > 0, "No distilled structure"

            return True
        except Exception as e:
            print(f"❌ Basic distillation failed: {e}")
            return False


def test_layer_detection():
    """Test architectural layer detection."""
    print("\nTesting layer detection...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create files with different layer patterns
        (tmpdir_path / "user_controller.py").write_text("class UserController: pass")
        (tmpdir_path / "auth_service.py").write_text("class AuthService: pass")
        (tmpdir_path / "user_repository.py").write_text("class UserRepository: pass")
        (tmpdir_path / "user_model.py").write_text("class User: pass")

        try:
            integrator = create_aid_integrator()
            layers = integrator.detect_layers(tmpdir_path)

            print("✅ Layer detection succeeded")
            print(f"   Confidence: {layers['confidence']:.1%}")
            print("   Layers found:")
            for layer_name, files in layers["layers"].items():
                if files:
                    print(f"     {layer_name}: {len(files)} files")

            if layers["violations"]:
                print(f"   Violations: {layers['violations']}")
            else:
                print("   No violations detected")

            return True
        except Exception as e:
            print(f"❌ Layer detection failed: {e}")
            return False


def test_dependency_analysis():
    """Test dependency direction analysis."""
    print("\nTesting dependency direction analysis...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create files with import patterns
        (tmpdir_path / "controller.py").write_text("from service import Service")
        (tmpdir_path / "service.py").write_text("from repository import Repository")
        (tmpdir_path / "repository.py").write_text("# No imports")

        try:
            integrator = create_aid_integrator()
            dep_dir = integrator.analyze_dependency_direction(tmpdir_path)

            print("✅ Dependency analysis succeeded")
            print(f"   Files analyzed: {len(dep_dir['graph'])}")

            if dep_dir["inbound_coupling"]:
                print("   High inbound coupling:")
                for file, count in list(dep_dir["inbound_coupling"].items())[:3]:
                    print(f"     {file}: {count} importers")

            if dep_dir["outbound_coupling"]:
                high_outbound = {f: c for f, c in dep_dir["outbound_coupling"].items() if c > 1}
                if high_outbound:
                    print("   High outbound coupling:")
                    for file, count in list(high_outbound.items())[:3]:
                        print(f"     {file}: {count} imports")

            if dep_dir["violations"]:
                print(f"   Violations: {dep_dir['violations']}")
            else:
                print("   No violations detected")

            return True
        except Exception as e:
            print(f"❌ Dependency analysis failed: {e}")
            return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("AID INTEGRATION V2 TEST SUITE")
    print("=" * 70)

    results = []
    results.append(test_aid_integrator_creation())

    # Only run further tests if AID is available
    if results[-1]:
        results.append(test_basic_distillation())
        results.append(test_layer_detection())
        results.append(test_dependency_analysis())

    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"TEST RESULTS: {passed}/{total} passed")

    if passed == total:
        print("✅ All tests passed - AID integration is working!")
    else:
        print("❌ Some tests failed - check AID CLI installation")

    print("=" * 70)

    return passed == total


if __name__ == "__main__":
    import sys

    sys.exit(0 if main() else 1)
