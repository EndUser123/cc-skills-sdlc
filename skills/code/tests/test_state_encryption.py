#!/usr/bin/env python3
"""Tests for state file encryption module."""

import json
import platform
import stat

# Import module to test
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib.state_encryption import (
        SENSITIVE_PATTERNS,
        SENSITIVE_REPLACEMENT,
        StateEncryptionError,
        decrypt_state,
        encrypt_existing_state,
        encrypt_state,
        is_state_encrypted,
        verify_gdpr_compliance,
    )

    STATE_ENCRYPTION_AVAILABLE = True
except ImportError as e:
    STATE_ENCRYPTION_AVAILABLE = False
    IMPORT_ERROR = str(e)


class TestStateEncryption:
    """Tests for state file encryption functionality."""

    def setup_method(self):
        """Set up temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        import shutil

        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_encrypt_and_decrypt_state(self):
        """Test basic encryption and decryption of state data."""
        original_state = {
            "phase": "GREEN",
            "task_id": "TASK-001",
            "timestamp": "2026-03-15T12:00:00Z",
            "metadata": {"key": "value"},
        }

        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(original_state, state_file)

        # Verify file exists and is encrypted
        assert state_file.exists(), "Encrypted file should exist"
        assert is_state_encrypted(state_file), "File should be encrypted"

        # Decrypt
        decrypted_state = decrypt_state(state_file)

        # Verify data matches
        assert decrypted_state == original_state, "Decrypted data should match original"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Windows does not support Unix-style file permissions",
    )
    def test_file_permissions_enforced(self):
        """Test that encrypted files have 600 permissions (owner read/write only)."""
        state = {"phase": "RED", "task_id": "TASK-001"}
        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(state, state_file)

        # Check file permissions
        file_mode = state_file.stat().st_mode

        # Verify 600 permissions (rw-------)
        # Owner should have read+write, group/others should have none
        assert (
            stat.S_IMODE(file_mode) == 0o600
        ), f"File should have 600 permissions, got {oct(stat.S_IMODE(file_mode))}"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_sensitive_pattern_redaction_api_key(self):
        """Test that API keys are redacted before encryption."""
        state_with_secrets = {
            "phase": "GREEN",
            "api_key": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "task_id": "TASK-001",
        }

        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(state_with_secrets, state_file)

        # Decrypt
        decrypted_state = decrypt_state(state_file)

        # Verify API key was redacted
        assert (
            decrypted_state["api_key"] == SENSITIVE_REPLACEMENT
        ), "API key should be redacted to [REDACTED]"
        assert decrypted_state["phase"] == "GREEN", "Non-sensitive data should be preserved"
        assert decrypted_state["task_id"] == "TASK-001", "Non-sensitive data should be preserved"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_sensitive_pattern_redaction_password(self):
        """Test that passwords are redacted before encryption."""
        state_with_password = {
            "phase": "GREEN",
            "config": {"password": "secret12345", "username": "admin"},
        }

        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(state_with_password, state_file)

        # Decrypt
        decrypted_state = decrypt_state(state_file)

        # Verify password was redacted
        assert (
            decrypted_state["config"]["password"] == SENSITIVE_REPLACEMENT
        ), "Password should be redacted to [REDACTED]"
        assert (
            decrypted_state["config"]["username"] == "admin"
        ), "Non-sensitive data should be preserved"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption_module not available"
    )
    def test_sensitive_pattern_redaction_token(self):
        """Test that tokens are redacted before encryption."""
        state_with_token = {
            "phase": "GREEN",
            "auth": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.verylongtoken",
                "token_type": "Bearer",
            },
        }

        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(state_with_token, state_file)

        # Decrypt
        decrypted_state = decrypt_state(state_file)

        # Verify token was redacted
        assert (
            decrypted_state["auth"]["access_token"] == SENSITIVE_REPLACEMENT
        ), "Access token should be redacted to [REDACTED]"
        assert (
            decrypted_state["auth"]["token_type"] == "Bearer"
        ), "Non-sensitive data should be preserved"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_encrypted_file_format(self):
        """Test that encrypted files have correct format."""
        state = {"phase": "GREEN", "task_id": "TASK-001"}
        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(state, state_file)

        # Read encrypted data
        encrypted_data = state_file.read_bytes()

        # Verify it looks like Fernet encrypted data
        assert len(encrypted_data) > 0, "Encrypted file should not be empty"
        assert encrypted_data[0:1] == b"g", "Fernet tokens start with 'g'"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_decrypt_nonexistent_file(self):
        """Test that decrypting nonexistent file raises error."""
        nonexistent_file = self.temp_path / "does_not_exist.enc"

        with pytest.raises(StateEncryptionError):
            decrypt_state(nonexistent_file)

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_decrypt_invalid_file(self):
        """Test that decrypting invalid file raises error."""
        invalid_file = self.temp_path / "invalid.enc"

        # Write non-encrypted data
        invalid_file.write_text("not encrypted data")

        with pytest.raises(StateEncryptionError):
            decrypt_state(invalid_file)

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_encrypt_existing_plaintext_file(self):
        """Test encrypt_existing_state converts plaintext to encrypted."""
        plaintext_state = {"phase": "GREEN", "api_key": "sk-1234567890abcdef"}

        plaintext_file = self.temp_path / "state.json"

        # Write plaintext state
        plaintext_file.write_text(json.dumps(plaintext_state, indent=2))

        # Encrypt existing file
        encrypted_file = encrypt_existing_state(plaintext_file)

        # Verify encrypted file was created
        assert encrypted_file.exists(), "Encrypted file should exist"
        assert encrypted_file.suffix == ".enc", "Encrypted file should have .enc suffix"

        # Verify backup was created
        backup_file = plaintext_file.with_suffix(".json.bak")
        assert backup_file.exists(), "Backup file should exist"

        # Verify original was moved
        assert not plaintext_file.exists(), "Original file should be moved to backup"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_gdpr_compliance_verification(self):
        """Test GDPR Article 32 compliance verification."""
        state = {"phase": "GREEN", "task_id": "TASK-001"}
        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(state, state_file)

        # Verify compliance
        compliance = verify_gdpr_compliance(state_file)

        # Check all compliance requirements
        assert compliance["encryption"] is True, "Should have encryption at rest"

        # On Windows, access_control is not applicable (no Unix-style permissions)
        if platform.system() != "Windows":
            assert (
                compliance["access_control"] is True
            ), "Should have access control (600 permissions)"

        assert compliance["key_management"] is True, "Should have secure key management"

        # Note: data_redaction will be False since this test has no sensitive patterns
        assert isinstance(
            compliance["data_redaction"], bool
        ), "Should have data_redaction check result"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_gdpr_compliance_with_redacted_data(self):
        """Test GDPR compliance verification with redacted sensitive data."""
        state_with_secrets = {"phase": "GREEN", "api_key": "sk-1234567890abcdef"}

        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(state_with_secrets, state_file)

        # Verify compliance
        compliance = verify_gdpr_compliance(state_file)

        # With sensitive data that gets redacted, data_redaction should be True
        assert (
            compliance["data_redaction"] is True
        ), "Should have data redaction for sensitive patterns"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_multiple_encryptions_same_file(self):
        """Test that re-encrypting the same file works correctly."""
        state_v1 = {"phase": "RED", "task_id": "TASK-001"}
        state_v2 = {"phase": "GREEN", "task_id": "TASK-001", "result": "success"}

        state_file = self.temp_path / "state.enc"

        # First encryption
        encrypt_state(state_v1, state_file)
        decrypted_v1 = decrypt_state(state_file)
        assert decrypted_v1["phase"] == "RED"

        # Second encryption (overwrite)
        encrypt_state(state_v2, state_file)
        decrypted_v2 = decrypt_state(state_file)
        assert decrypted_v2["phase"] == "GREEN"
        assert decrypted_v2["result"] == "success"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_key_file_permissions(self):
        """Test that key files have 600 permissions."""
        state = {"phase": "GREEN"}
        state_file = self.temp_path / "state.enc"

        # Encrypt (creates key file)
        encrypt_state(state, state_file)

        # Find key file
        key_file = Path(".claude/state/keys") / f"{state_file.name}.key"

        if key_file.exists():
            # Check key file permissions
            key_mode = key_file.stat().st_mode
            assert (
                stat.S_IMODE(key_mode) == 0o600
            ), f"Key file should have 600 permissions, got {oct(stat.S_IMODE(key_mode))}"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_empty_state_encryption(self):
        """Test encrypting empty state."""
        empty_state = {}
        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(empty_state, state_file)

        # Decrypt
        decrypted_state = decrypt_state(state_file)

        # Verify
        assert decrypted_state == {}, "Empty state should encrypt/decrypt correctly"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_nested_data_redaction(self):
        """Test that sensitive data in nested structures is redacted."""
        nested_state = {
            "level1": {
                "level2": {"api_key": "sk-1234567890abcdef", "config": {"password": "secret123"}}
            },
            "safe_data": "preserve this",
        }

        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(nested_state, state_file)

        # Decrypt
        decrypted_state = decrypt_state(state_file)

        # Verify nested redaction
        assert (
            decrypted_state["level1"]["level2"]["api_key"] == SENSITIVE_REPLACEMENT
        ), "Nested API key should be redacted"
        assert (
            decrypted_state["level1"]["level2"]["config"]["password"] == SENSITIVE_REPLACEMENT
        ), "Nested password should be redacted"
        assert (
            decrypted_state["safe_data"] == "preserve this"
        ), "Non-sensitive nested data should be preserved"

    @pytest.mark.skipif(
        not STATE_ENCRYPTION_AVAILABLE, reason="state_encryption module not available"
    )
    def test_list_data_redaction(self):
        """Test that sensitive data in lists is redacted."""
        list_state = {
            "items": [
                {"id": 1, "api_key": "sk-key1"},
                {"id": 2, "api_key": "sk-key2"},
                {"id": 3, "name": "safe item"},
            ]
        }

        state_file = self.temp_path / "state.enc"

        # Encrypt
        encrypt_state(list_state, state_file)

        # Decrypt
        decrypted_state = decrypt_state(state_file)

        # Verify list redaction
        assert (
            decrypted_state["items"][0]["api_key"] == SENSITIVE_REPLACEMENT
        ), "API key in list item should be redacted"
        assert (
            decrypted_state["items"][1]["api_key"] == SENSITIVE_REPLACEMENT
        ), "API key in list item should be redacted"
        assert (
            decrypted_state["items"][2]["name"] == "safe item"
        ), "Non-sensitive data in list should be preserved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
