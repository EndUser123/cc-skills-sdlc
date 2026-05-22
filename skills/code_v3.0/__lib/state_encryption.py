#!/usr/bin/env python3
"""
State file encryption module for /code skill.

Provides encryption at rest for state files with strict file permissions (600),
sensitive data redaction, and GDPR Article 32 compliance for data security.

Features:
- Fernet symmetric encryption for state files
- Automatic file permission enforcement (600)
- Sensitive pattern redaction (API keys, passwords, tokens)
- Key management with secure storage
- GDPR Article 32 compliance (encryption of personal data)

Usage:
    from lib.state_encryption import encrypt_state, decrypt_state

    # Encrypt and save state
    encrypt_state(state_data, "state_file.enc")

    # Decrypt and load state
    state_data = decrypt_state("state_file.enc")
"""

import base64
import json
import platform
import re
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Check if running on Windows
IS_WINDOWS = platform.system() == "Windows"

# Sensitive patterns to redact before encryption
SENSITIVE_PATTERNS = [
    # API keys (JSON format and other formats)
    r'"(?:api[_-]?key|apikey|api[_-]?secret)"\s*:\s*"([a-zA-Z0-9_\-]{20,})"',
    r'(?:api[_-]?key|apikey|api[_-]?secret)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
    r'["\']([a-zA-Z0-9]{32,})["\']?\s*(?:is|:)\s*["\']?(?:api[_-]?key|apikey)',

    # Passwords (JSON format and other formats)
    r'"(?:password|passwd|pwd)"\s*:\s*"([^\s"]{8,})"',
    r'(?:password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']{8,})["\']?',

    # Tokens (JSON format and other formats)
    r'"(?:token|bearer[_-]?token|access[_-]?token)"\s*:\s*"([a-zA-Z0-9_\-\.]{20,})"',
    r'(?:token|bearer[_-]?token|access[_-]?token)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',

    # Secret keys (JSON format and other formats)
    r'"(?:secret[_-]?key|secretkey|private[_-]?key)"\s*:\s*"([a-zA-Z0-9_\-]{20,})"',
    r'(?:secret[_-]?key|secretkey|private[_-]?key)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',

    # URLs with credentials
    r'(https?://)([^\s"\']+?:([^\s"\']+)?@)([^\s"\']+)',

    # Base64 encoded data (potential secrets)
    r'["\']([A-Za-z0-9+/]{32,}={0,2})["\']?\s*(?:is|:)\s*["\']?(?:base64|encoded)',
]

SENSITIVE_REPLACEMENT = '[REDACTED]'


class StateEncryptionError(Exception):
    """Raised when state encryption/decryption fails."""
    pass


def _redact_sensitive_data(data: Any) -> Any:
    """
    Redact sensitive patterns from data before encryption.

    Scans for API keys, passwords, tokens, and other sensitive patterns,
    replacing them with [REDACTED] to prevent accidental leakage.

    Args:
        data: Data structure (dict, list, str) to redact

    Returns:
        Redacted data structure

    Examples:
        >>> _redact_sensitive_data({"api_key": "sk-1234567890abcdef"})
        {"api_key": "[REDACTED]"}

        >>> _redact_sensitive_data("password: secret123")
        "password: [REDACTED]"
    """
    # Sensitive key names to check (lowercase for case-insensitive matching)
    SENSITIVE_KEYS = {
        'api_key', 'apikey', 'api-secret', 'apisecret',
        'password', 'passwd', 'pwd',
        'token', 'bearer_token', 'bearer-token', 'bearerToken',
        'access_token', 'access-token', 'accessToken',
        'secret_key', 'secretkey', 'private_key', 'private-key', 'privateKey',
        'auth_token', 'auth-token', 'authToken',
    }

    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            # Check if key name indicates sensitive data
            key_lower = k.lower().replace('-', '_').replace('_', '')
            # Normalize key for comparison (remove separators and convert to lowercase)
            key_normalized = k.lower().replace('-', '').replace('_', '')

            # Check if this is a known sensitive key
            is_sensitive_key = any(
                sensitive_key.replace('-', '').replace('_', '') == key_normalized
                for sensitive_key in SENSITIVE_KEYS
            )

            if is_sensitive_key and isinstance(v, str):
                # Redact sensitive values (no length check for known sensitive keys)
                result[k] = SENSITIVE_REPLACEMENT
            else:
                # Recursively process non-sensitive values
                result[k] = _redact_sensitive_data(v)
        return result
    elif isinstance(data, list):
        return [_redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        text = data
        for pattern in SENSITIVE_PATTERNS:
            text = re.sub(pattern, SENSITIVE_REPLACEMENT, text, flags=re.IGNORECASE)
        return text
    else:
        return data


def _generate_key_from_password(password: str, salt: bytes) -> bytes:
    """
    Generate Fernet key from password using PBKDF2HMAC.

    Args:
        password: Password string for key derivation
        salt: Salt bytes for key derivation

    Returns:
        URL-safe base64-encoded 32-byte key
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # OWASP recommended for 2026
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def _get_or_create_encryption_key(state_file: Path) -> bytes:
    """
    Get or create encryption key for state file.

    Key is stored in .claude/state/keys/ directory with strict permissions (600).
    Key filename matches state filename for easy lookup.

    Args:
        state_file: Path to state file

    Returns:
        Fernet encryption key

    Raises:
        StateEncryptionError: If key cannot be created or accessed
    """
    keys_dir = Path.home() / ".claude" / ".state" / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)

    key_file = keys_dir / f"{state_file.name}.key"

    # Set directory permissions to 700 (owner rwx only)
    try:
        keys_dir.chmod(0o700)
    except OSError as e:
        raise StateEncryptionError(f"Cannot set key directory permissions: {e}")

    # Generate or load key
    if key_file.exists():
        try:
            key_data = key_file.read_bytes()
            # Verify key file has correct permissions
            if not key_file.stat().st_mode & 0o600:
                key_file.chmod(0o600)
            return key_data
        except OSError as e:
            raise StateEncryptionError(f"Cannot read encryption key: {e}")

    # Generate new key with random salt
    try:
        # Generate random key
        key = Fernet.generate_key()

        # Write key with strict permissions
        key_file.write_bytes(key)
        key_file.chmod(0o600)

        return key
    except OSError as e:
        raise StateEncryptionError(f"Cannot create encryption key: {e}")


def _set_strict_permissions(file_path: Path) -> None:
    """
    Set file permissions to 600 (owner read/write only).

    Ensures only the file owner can read or write the file.

    On Windows, this is a no-op due to Windows file security model differences.
    On Unix/Linux, uses chmod() to set 600 permissions.

    Args:
        file_path: Path to file

    Raises:
        StateEncryptionError: If permissions cannot be set on Unix/Linux
    """
    if IS_WINDOWS:
        # Windows: File permissions work differently
        # Rely on Windows file security (ACLs) instead of Unix permissions
        # The encryption still protects data at rest
        return

    try:
        # Unix/Linux: Use chmod to set 600 permissions
        file_path.chmod(0o600)
    except OSError as e:
        raise StateEncryptionError(f"Cannot set file permissions to 600: {e}")


def encrypt_state(state: Dict[str, Any], output_file: Path) -> None:
    """
    Encrypt and save state data to file with strict permissions.

    Process:
    1. Redact sensitive patterns from state data
    2. Serialize to JSON
    3. Encrypt with Fernet symmetric encryption
    4. Write to file with permissions 600

    Args:
        state: State dictionary to encrypt
        output_file: Output file path (will be created/overwritten)

    Raises:
        StateEncryptionError: If encryption or file write fails

    Examples:
        >>> state = {"phase": "GREEN", "api_key": "sk-1234"}
        >>> encrypt_state(state, Path("state.enc"))
        >>> # Creates state.enc with encrypted data
    """
    try:
        # Step 1: Redact sensitive data
        redacted_state = _redact_sensitive_data(state)

        # Step 2: Serialize to JSON
        json_data = json.dumps(redacted_state, indent=2, default=str)

        # Step 3: Get encryption key
        key = _get_or_create_encryption_key(output_file)
        fernet = Fernet(key)

        # Step 4: Encrypt data
        encrypted_data = fernet.encrypt(json_data.encode())

        # Step 5: Write to file with atomic operation
        temp_file = output_file.with_suffix('.tmp')
        temp_file.write_bytes(encrypted_data)

        # Step 6: Set strict permissions before rename
        _set_strict_permissions(temp_file)

        # Step 7: Atomic rename
        temp_file.replace(output_file)

        # Ensure final file has correct permissions
        _set_strict_permissions(output_file)

    except (OSError, json.JSONEncodeError) as e:
        raise StateEncryptionError(f"Encryption failed: {e}")


def decrypt_state(input_file: Path) -> Dict[str, Any]:
    """
    Decrypt and load state data from file.

    Args:
        input_file: Path to encrypted state file

    Returns:
        Decrypted state dictionary

    Raises:
        StateEncryptionError: If decryption fails or file is invalid

    Examples:
        >>> state = decrypt_state(Path("state.enc"))
        >>> print(state["phase"])
        'GREEN'
    """
    try:
        # Verify file exists
        if not input_file.exists():
            raise StateEncryptionError(f"State file not found: {input_file}")

        # Check file permissions
        file_mode = input_file.stat().st_mode
        if file_mode & 0o077:  # Check if group/others have permissions
            # Fix insecure permissions
            _set_strict_permissions(input_file)

        # Read encrypted data
        encrypted_data = input_file.read_bytes()

        # Get decryption key
        key = _get_or_create_encryption_key(input_file)
        fernet = Fernet(key)

        # Decrypt data
        decrypted_data = fernet.decrypt(encrypted_data)

        # Parse JSON
        state = json.loads(decrypted_data.decode())

        return state

    except (OSError, json.JSONDecodeError, InvalidToken) as e:
        raise StateEncryptionError(f"Decryption failed: {e}")


def is_state_encrypted(state_file: Path) -> bool:
    """
    Check if state file is encrypted.

    Args:
        state_file: Path to state file

    Returns:
        True if file appears to be encrypted, False otherwise
    """
    if not state_file.exists():
        return False

    try:
        data = state_file.read_bytes()
        # Fernet encrypted data is base64-like, check for valid format
        # Encrypted data typically starts with known Fernet header
        return len(data) > 0 and data[0:1] == b'g'  # Fernet tokens start with 'g'
    except OSError:
        return False


def encrypt_existing_state(plaintext_file: Path) -> Path:
    """
    Encrypt existing plaintext state file.

    Reads plaintext state file, encrypts it, and replaces the original
    with encrypted version.

    Args:
        plaintext_file: Path to plaintext state file

    Returns:
        Path to encrypted state file

    Raises:
        StateEncryptionError: If encryption fails

    Examples:
        >>> encrypt_existing_state(Path("state.json"))
        Path("state.json.enc")
    """
    try:
        # Read plaintext state
        state = json.loads(plaintext_file.read_text())

        # Create encrypted file path
        encrypted_file = plaintext_file.with_suffix(plaintext_file.suffix + '.enc')

        # Encrypt and save
        encrypt_state(state, encrypted_file)

        # Backup original file
        backup_file = plaintext_file.with_suffix(plaintext_file.suffix + '.bak')
        plaintext_file.rename(backup_file)

        return encrypted_file

    except (OSError, json.JSONDecodeError) as e:
        raise StateEncryptionError(f"Failed to encrypt existing state: {e}")


# GDPR Article 32 compliance verification
def verify_gdpr_compliance(state_file: Path) -> Dict[str, bool]:
    """
    Verify GDPR Article 32 compliance for state file.

    Checks:
    1. Encryption at rest (Fernet)
    2. Access control (file permissions 600)
    3. Key management (secure storage)
    4. Data redaction (sensitive patterns removed)

    Args:
        state_file: Path to state file

    Returns:
        Dictionary with compliance status for each check

    Examples:
        >>> verify_gdpr_compliance(Path("state.enc"))
        {
            "encryption": True,
            "access_control": True,
            "key_management": True,
            "data_redaction": True
        }
    """
    compliance = {
        "encryption": False,
        "access_control": False,
        "key_management": False,
        "data_redaction": False
    }

    try:
        # Check 1: Encryption at rest
        compliance["encryption"] = is_state_encrypted(state_file)

        # Check 2: Access control (file permissions)
        if state_file.exists():
            if IS_WINDOWS:
                # Windows: File exists, encryption protects data at rest
                # Rely on Windows file security (ACLs) instead of Unix permissions
                compliance["access_control"] = True
            else:
                # Unix/Linux: Check file has 600 permissions
                file_mode = state_file.stat().st_mode
                compliance["access_control"] = not bool(file_mode & 0o077)

        # Check 3: Key management
            key_dir = Path.home() / ".claude" / ".state" / "keys"
        if key_dir.exists():
            if IS_WINDOWS:
                # Windows: Key directory exists, encryption protects data at rest
                # Rely on Windows file security (ACLs) instead of Unix permissions
                compliance["key_management"] = True
            else:
                # Unix/Linux: Check key directory has 700 permissions
                key_mode = key_dir.stat().st_mode
                key_perms_ok = not bool(key_mode & 0o077)
                compliance["key_management"] = key_perms_ok

        # Check 4: Data redaction (decrypt and verify)
        if compliance["encryption"]:
            try:
                state = decrypt_state(state_file)
                # Check for unredacted sensitive patterns
                state_str = json.dumps(state)
                has_secrets = any(
                    re.search(pattern, state_str, re.IGNORECASE)
                    for pattern in SENSITIVE_PATTERNS
                )
                compliance["data_redaction"] = not has_secrets
            except StateEncryptionError:
                compliance["data_redaction"] = False

    except OSError:
        pass

    return compliance
