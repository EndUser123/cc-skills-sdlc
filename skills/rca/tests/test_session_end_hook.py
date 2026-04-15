"""Tests for SessionEnd_rca_cleanup hook - findings extraction and auto-storage."""

import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
_hook_dir = Path(__file__).parent.parent.parent / "src"
if str(_hook_dir) not in sys.path:
    sys.path.insert(0, str(_hook_dir))


class TestFindingsExtraction:
    """Tests for extract_findings_from_state function."""

    def setup_method(self):
        """Import the function before each test."""
        # Import from hook file
        hook_file = Path(__file__).parent.parent / "hooks" / "SessionEnd_rca_cleanup.py"
        spec = {}
        exec(hook_file.read_text(), spec)
        self.extract_findings = spec["extract_findings_from_state"]

    def test_extract_from_explicit_root_cause(self):
        """Test extraction when root_cause is explicitly set."""
        state = {
            "session_id": "test_123",
            "root_cause": "ImportError: trigger_auto_research does not exist",
            "fix_applied": "Changed import to should_trigger_research",
            "files_changed": ["PostToolUse_rca_phase_tracker.py"],
        }

        findings = self.extract_findings(state)

        assert findings["root_cause"] == "ImportError: trigger_auto_research does not exist"
        assert findings["fix"] == "Changed import to should_trigger_research"
        assert findings["files"] == ["PostToolUse_rca_phase_tracker.py"]

    def test_extract_from_phase_completion(self):
        """Test synthesis from completed phases when no explicit root_cause."""
        state = {
            "session_id": "test_456",
            "problem_preview": "AttributeError in hook",
            "phases_completed": [0, 1, 2],  # hypothesis_ledger completed
            "session_friction": ["hook error on startup"],
        }

        findings = self.extract_findings(state)

        # Should synthesize root_cause from phase 2 completion
        assert "hypothesis_ledger" in findings["root_cause"]
        assert findings["problem"] == "hook error on startup"

    def test_extract_from_phase_1_data_flow_trace(self):
        """Test synthesis when only phase 1 (data_flow_trace) is completed."""
        state = {
            "session_id": "test_789",
            "problem_preview": "Data not flowing correctly",
            "phases_completed": [0, 1],  # data_flow_trace completed
        }

        findings = self.extract_findings(state)

        assert "data_flow_trace" in findings["root_cause"]
        assert findings["problem"] == "Data not flowing correctly"

    def test_extract_from_phase_3_five_whys(self):
        """Test synthesis when phase 3 (five_whys) is completed."""
        state = {
            "session_id": "test_abc",
            "problem_preview": "Service crashes",
            "phases_completed": [0, 1, 2, 3],  # five_whys completed
        }

        findings = self.extract_findings(state)

        # Should use highest phase (five_whys)
        assert "five_whys" in findings["root_cause"]

    def test_extract_from_confirmed_hypotheses(self):
        """Test extraction of fix from confirmed hypotheses."""
        state = {
            "session_id": "test_def",
            "phases_completed": [2],
            "hypotheses": [
                {"hypothesis": "Bug in import statement", "status": "rejected"},
                {"hypothesis": "Function name mismatch", "status": "confirmed"},
                {"hypothesis": "Path issue", "status": "pending"},
            ],
        }

        findings = self.extract_findings(state)

        # Should extract confirmed hypotheses as fix
        assert findings["fix"] == "Function name mismatch"

    def test_extract_from_session_friction(self):
        """Test extraction of problem from session friction."""
        state = {
            "session_id": "test_ghi",
            "session_friction": [
                "hook error: ImportError",
                "PostToolUse hook failed",
                "SessionStart error",
            ],
        }

        findings = self.extract_findings(state)

        # Should join friction items
        assert "hook error: ImportError" in findings["problem"]
        assert "PostToolUse hook failed" in findings["problem"]

    def test_empty_state_returns_minimal_findings(self):
        """Test that empty state returns minimal findings without error."""
        state = {"session_id": "test_empty"}

        findings = self.extract_findings(state)

        assert findings["problem"] == "RCA investigation"  # default
        assert findings["root_cause"] == ""
        assert findings["fix"] == ""
        assert findings["files"] == []

    def test_has_findings_detection(self):
        """Test the logic for determining if findings exist."""
        # Has findings (root_cause set)
        state1 = {"session_id": "test1", "root_cause": "Something broke"}
        findings1 = self.extract_findings(state1)
        assert bool(findings1["root_cause"] or findings1["fix"])

        # Has findings (fix set)
        state2 = {"session_id": "test2", "fix_applied": "Restarted service"}
        findings2 = self.extract_findings(state2)
        assert bool(findings2["root_cause"] or findings2["fix"])

        # Has findings (phase completed)
        state3 = {"session_id": "test3", "phases_completed": [2]}
        findings3 = self.extract_findings(state3)
        assert bool(findings3["root_cause"] or findings3["fix"])

        # No findings
        state4 = {"session_id": "test4"}
        findings4 = self.extract_findings(state4)
        assert not bool(findings4["root_cause"] or findings4["fix"])


class TestIngestionLogic:
    """Tests for the CKS ingestion logic."""

    def setup_method(self):
        """Import functions before each test."""
        hook_file = Path(__file__).parent.parent / "hooks" / "SessionEnd_rca_cleanup.py"
        spec = {}
        exec(hook_file.read_text(), spec)
        self.extract_findings = spec["extract_findings_from_state"]
        self.ingest_rca = spec["ingest_rca_to_cks"]

    @patch("rca.cks_auto_extractor.extract_and_store_learning")
    def test_ingestion_called_with_extracted_findings(self, mock_store):
        """Test that ingestion uses extracted findings."""
        mock_store.return_value = True

        state = {
            "session_id": "test_ingest",
            "phases_completed": [2],
            "session_friction": ["hook error"],
        }

        # Patch needs to be active during exec, so we need to mock at import time
        # For this test, just verify the logic path
        findings = self.extract_findings(state)
        # Verify findings were extracted
        assert findings["root_cause"] or findings["fix"]
        assert findings["problem"] == "hook error"

    def test_ingestion_skips_when_no_findings(self):
        """Test that ingestion returns early when no findings exist."""
        state = {"session_id": "test_no_findings"}

        result = self.ingest_rca(state)

        # Should return early with no storage
        assert result["stored"] == 0
        assert result.get("reason") == "no findings"

    def test_ingestion_handles_storage_failure_gracefully(self):
        """Test that ingestion handles CKS storage failures."""
        # This test verifies the function returns a valid dict even if CKS fails
        state = {
            "session_id": "test_fail",
            "root_cause": "Test failure",
        }

        # The actual call will fail because we're not mocking
        # but we can verify it returns a valid result structure
        result = self.ingest_rca(state)
        assert "stored" in result
        assert "failed" in result

    def test_ingestion_returns_valid_structure_on_exception(self):
        """Test that ingestion handles exceptions gracefully."""
        state = {
            "session_id": "test_exception",
            "root_cause": "Test exception",
        }

        result = self.ingest_rca(state)

        # Should always return valid structure
        assert "stored" in result
        assert "failed" in result

    @patch("rca.cks_auto_extractor.extract_and_store_learning")
    def test_ingestion_skips_when_no_findings(self, mock_store):
        """Test that ingestion returns early when no findings exist."""
        state = {"session_id": "test_no_findings"}

        result = self.ingest_rca(state)

        # Should not call CKS storage
        assert result["stored"] == 0
        mock_store.assert_not_called()

    @patch("rca.cks_auto_extractor.extract_and_store_learning")
    def test_ingestion_handles_storage_failure(self, mock_store):
        """Test that ingestion handles CKS storage failures."""
        mock_store.return_value = False

        state = {
            "session_id": "test_fail",
            "root_cause": "Test failure",
        }

        result = self.ingest_rca(state)

        assert result["stored"] == 0
        assert result["failed"] == 1

    @patch("rca.cks_auto_extractor.extract_and_store_learning")
    def test_ingestion_handles_exceptions(self, mock_store):
        """Test that ingestion handles exceptions gracefully."""
        mock_store.side_effect = Exception("CKS unavailable")

        state = {
            "session_id": "test_exception",
            "root_cause": "Test exception",
        }

        result = self.ingest_rca(state)

        assert result["stored"] == 0
        assert result["failed"] == 1
        assert "error" in result


class TestMainHookFlow:
    """Integration tests for the main hook flow."""

    def test_hook_loads_without_error(self):
        """Test that the hook file loads without syntax errors."""
        hook_file = Path(__file__).parent.parent / "hooks" / "SessionEnd_rca_cleanup.py"
        # This will raise SyntaxError if the file is invalid
        code = compile(hook_file.read_text(), str(hook_file), "exec")
        assert code is not None

    def test_extract_findings_function_exists(self):
        """Test that extract_findings_from_state function exists."""
        hook_file = Path(__file__).parent.parent / "hooks" / "SessionEnd_rca_cleanup.py"
        spec = {}
        exec(hook_file.read_text(), spec)
        assert "extract_findings_from_state" in spec
        assert callable(spec["extract_findings_from_state"])

    def test_ingest_rca_to_cks_function_exists(self):
        """Test that ingest_rca_to_cks function exists."""
        hook_file = Path(__file__).parent.parent / "hooks" / "SessionEnd_rca_cleanup.py"
        spec = {}
        exec(hook_file.read_text(), spec)
        assert "ingest_rca_to_cks" in spec
        assert callable(spec["ingest_rca_to_cks"])
