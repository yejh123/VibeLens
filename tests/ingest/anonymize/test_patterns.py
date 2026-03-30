"""Tests for regex patterns, entropy, and allowlist utilities."""

import pytest

from vibelens.ingest.anonymize.rule_anonymizer.patterns import (
    CREDENTIAL_PATTERNS,
    PII_PATTERNS,
    compute_shannon_entropy,
    has_mixed_char_types,
    is_allowlisted,
    is_valid_high_entropy,
)
from vibelens.ingest.anonymize.rule_anonymizer.redactor import scan_text


class TestShannonEntropy:
    def test_empty_string_returns_zero(self) -> None:
        result = compute_shannon_entropy("")
        print(f"  entropy('') = {result}")
        assert result == 0.0

    def test_single_char_returns_zero(self) -> None:
        result = compute_shannon_entropy("aaaaaaa")
        print(f"  entropy('aaaaaaa') = {result}")
        assert result == 0.0

    def test_random_base64_has_high_entropy(self) -> None:
        # Simulated base64-like random string
        text = "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
        result = compute_shannon_entropy(text)
        print(f"  entropy(base64-like) = {result:.3f}")
        assert result > 4.0

    def test_natural_text_has_moderate_entropy(self) -> None:
        text = "the quick brown fox jumps over the lazy dog"
        result = compute_shannon_entropy(text)
        print(f"  entropy(natural text) = {result:.3f}")
        assert 2.0 < result < 5.0


class TestHasMixedCharTypes:
    def test_all_lowercase_returns_false(self) -> None:
        assert has_mixed_char_types("abcdef") is False

    def test_upper_lower_digit_symbol_returns_true(self) -> None:
        assert has_mixed_char_types("Abc123!@") is True

    def test_two_types_returns_false(self) -> None:
        # Only upper + lower = 2 types, threshold is 3
        assert has_mixed_char_types("AbCdEf") is False


class TestIsAllowlisted:
    def test_safe_emails_allowed(self) -> None:
        for email in ["user@example.com", "noreply@anthropic.com", "noreply@github.com"]:
            assert is_allowlisted(email) is True
            print(f"  allowlisted: {email}")

    def test_unknown_email_not_allowed(self) -> None:
        assert is_allowlisted("secret@company.com") is False

    def test_dns_ips_allowed(self) -> None:
        for ip in ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1"]:
            assert is_allowlisted(ip) is True
            print(f"  allowlisted: {ip}")


class TestIsValidHighEntropy:
    def test_short_string_returns_false(self) -> None:
        # Below HIGH_ENTROPY_MIN_LENGTH (40)
        assert is_valid_high_entropy("abc123") is False

    def test_low_entropy_long_string_returns_false(self) -> None:
        # 50 chars but all the same character — zero entropy
        assert is_valid_high_entropy("a" * 50) is False

    def test_genuine_secret_returns_true(self) -> None:
        # High entropy, mixed char types, long enough
        secret = "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5!@#$"
        result = is_valid_high_entropy(secret)
        print(f"  is_valid_high_entropy(genuine secret) = {result}")
        assert result is True


class TestCredentialPatterns:
    @pytest.mark.parametrize(
        ("name", "sample"),
        [
            (
                "jwt",
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
                ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            ),
            ("anthropic_key", "sk-ant-api03-abcdefghijklmnop1234567890ABCDEF"),
            ("openai_key", "sk-proj-abcdefghijklmnopqrstuv"),
            ("github_classic_token", "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl"),
            ("aws_access_key", "AKIAIOSFODNN7EXAMPLE"),
            ("bearer_token", "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"),
            ("env_secret", "API_KEY=my_super_secret_value_12345"),
            ("pem_private_key", "-----BEGIN RSA PRIVATE KEY-----"),
            ("stripe_key", "sk_test_abcdefghijklmnopqrstuv"),
            ("db_url_postgres", "postgres://admin:p@ssw0rd@db.example.com:5432/mydb"),
        ],
    )
    def test_credential_detected(self, name: str, sample: str) -> None:
        findings = scan_text(sample, CREDENTIAL_PATTERNS)
        matched_names = [f.name for f in findings]
        print(f"  {name}: matched={matched_names}")
        assert len(findings) >= 1, f"Expected {name} to be detected in: {sample}"


class TestPIIPatterns:
    def test_email_detected(self) -> None:
        text = "Contact me at real.person@company.com for details"
        findings = scan_text(text, PII_PATTERNS)
        print(f"  PII findings: {[(f.name, f.matched_text) for f in findings]}")
        assert any(f.name == "email" for f in findings)

    def test_private_ip_not_detected(self) -> None:
        text = "Server at 192.168.1.100 is internal"
        findings = scan_text(text, PII_PATTERNS)
        print(f"  PII findings for private IP: {[(f.name, f.matched_text) for f in findings]}")
        assert not any(f.name == "public_ip" for f in findings)

    def test_public_ip_detected(self) -> None:
        text = "External server at 203.0.113.50 exposed"
        findings = scan_text(text, PII_PATTERNS)
        print(f"  PII findings for public IP: {[(f.name, f.matched_text) for f in findings]}")
        assert any(f.name == "public_ip" for f in findings)

    def test_allowlisted_email_skipped(self) -> None:
        text = "Send to user@example.com"
        findings = scan_text(text, PII_PATTERNS)
        print(f"  PII findings for allowlisted email: {findings}")
        assert len(findings) == 0
