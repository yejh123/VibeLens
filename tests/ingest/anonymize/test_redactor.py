"""Tests for the scanning and redaction engine."""

from vibelens.ingest.anonymize.rule_anonymizer.patterns import (
    CREDENTIAL_PATTERNS,
    PII_PATTERNS,
)
from vibelens.ingest.anonymize.rule_anonymizer.redactor import (
    redact_custom_strings,
    redact_patterns,
    scan_text,
)

PLACEHOLDER = "[REDACTED]"


class TestScanText:
    def test_no_matches_returns_empty(self) -> None:
        findings = scan_text("just some normal text", CREDENTIAL_PATTERNS)
        print(f"  no matches: {findings}")
        assert findings == []

    def test_single_match_returns_correct_finding(self) -> None:
        text = "key: sk-ant-api03-ABCDEF1234567890abcdefgh"
        findings = scan_text(text, CREDENTIAL_PATTERNS)
        print(f"  single match: {[(f.name, f.matched_text) for f in findings]}")
        assert len(findings) == 1
        assert findings[0].name == "anthropic_key"
        assert findings[0].start >= 0
        assert findings[0].end > findings[0].start

    def test_multiple_matches_sorted_by_start(self) -> None:
        text = (
            "first ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl "
            "then sk-ant-api03-ABCDEF1234567890abcdefgh"
        )
        findings = scan_text(text, CREDENTIAL_PATTERNS)
        print(f"  multiple: {[(f.name, f.start) for f in findings]}")
        assert len(findings) >= 2
        assert findings[0].start <= findings[1].start

    def test_allowlisted_skipped(self) -> None:
        text = "contact user@example.com for help"
        findings = scan_text(text, PII_PATTERNS)
        print(f"  allowlisted: {findings}")
        assert len(findings) == 0


class TestRedactPatterns:
    def test_single_redaction(self) -> None:
        text = "key=sk-ant-api03-ABCDEF1234567890abcdefgh"
        result, count = redact_patterns(text, CREDENTIAL_PATTERNS, PLACEHOLDER)
        print(f"  single redaction: '{result}' (count={count})")
        assert count == 1
        assert PLACEHOLDER in result
        assert "sk-ant-api03" not in result

    def test_multiple_non_overlapping(self) -> None:
        text = "a=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl b=AKIAIOSFODNN7EXAMPLE"
        result, count = redact_patterns(text, CREDENTIAL_PATTERNS, PLACEHOLDER)
        print(f"  multiple: '{result}' (count={count})")
        assert count == 2
        assert result.count(PLACEHOLDER) == 2

    def test_overlapping_dedup(self) -> None:
        # Bearer token wrapping a JWT — should deduplicate
        text = (
            "Authorization: Bearer "
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        result, count = redact_patterns(text, CREDENTIAL_PATTERNS, PLACEHOLDER)
        print(f"  overlapping: '{result}' (count={count})")
        assert count >= 1
        assert "eyJ" not in result

    def test_custom_placeholder(self) -> None:
        text = "secret=sk-ant-api03-ABCDEF1234567890abcdefgh"
        result, count = redact_patterns(text, CREDENTIAL_PATTERNS, "***")
        print(f"  custom placeholder: '{result}' (count={count})")
        assert "***" in result
        assert count == 1

    def test_no_matches_returns_original(self) -> None:
        text = "nothing sensitive here"
        result, count = redact_patterns(text, CREDENTIAL_PATTERNS, PLACEHOLDER)
        assert result == text
        assert count == 0


class TestRedactCustomStrings:
    def test_literal_replaced(self) -> None:
        text = "My company token is ACME-INTERNAL-12345"
        result, count = redact_custom_strings(text, ["ACME-INTERNAL-12345"], PLACEHOLDER)
        print(f"  literal: '{result}' (count={count})")
        assert PLACEHOLDER in result
        assert count == 1

    def test_multiple_occurrences_counted(self) -> None:
        text = "found secret here and secret there"
        result, count = redact_custom_strings(text, ["secret"], PLACEHOLDER)
        print(f"  multiple occurrences: '{result}' (count={count})")
        assert count == 2
        assert "secret" not in result

    def test_empty_strings_skipped(self) -> None:
        text = "no change expected"
        result, count = redact_custom_strings(text, ["", ""], PLACEHOLDER)
        assert result == text
        assert count == 0

    def test_regex_metacharacters_escaped(self) -> None:
        text = "pattern (foo+bar) should be literal"
        result, count = redact_custom_strings(text, ["(foo+bar)"], PLACEHOLDER)
        print(f"  regex escaped: '{result}' (count={count})")
        assert PLACEHOLDER in result
        assert count == 1
