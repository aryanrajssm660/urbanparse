"""
Tests for the deterministic address validator.

These tests verify business behavior, not just that functions execute.
Each test corresponds to a specific edge case from the assessment brief.
"""

from app.validators.address_validator import (
    validate_pin_format,
    validate_pin_city_consistency,
    check_required_fields,
    detect_non_address,
    detect_ambiguity,
    detect_plus_code,
    detect_sensitive_data,
    validate_address,
    determine_final_status,
    ValidationResult,
)
from app.schemas.address import ClaudeParseResult


# =====================================================================
# PIN FORMAT VALIDATION
# =====================================================================

class TestPinFormat:
    def test_valid_pin(self):
        ok, warning = validate_pin_format("560066")
        assert ok is True
        assert warning is None

    def test_invalid_pin_too_short(self):
        ok, warning = validate_pin_format("5600")
        assert ok is False
        assert "6 digits" in warning

    def test_invalid_pin_letters(self):
        ok, warning = validate_pin_format("56006A")
        assert ok is False

    def test_null_pin_is_ok(self):
        """Missing PIN is not a format error — handled by required-fields check."""
        ok, warning = validate_pin_format(None)
        assert ok is True

    def test_empty_pin_is_ok(self):
        ok, warning = validate_pin_format("")
        assert ok is True


# =====================================================================
# PIN-CITY CONSISTENCY
# =====================================================================

class TestPinCityConsistency:
    def test_bangalore_pin_with_bangalore(self):
        """Address #1: 560066 is valid for Bengaluru."""
        ok, warning = validate_pin_city_consistency("560066", "Bengaluru")
        assert ok is True

    def test_delhi_pin_with_bangalore_contradiction(self):
        """Address #8: 110001 is Delhi, but city is Bengaluru — MUST be flagged."""
        ok, warning = validate_pin_city_consistency("110001", "Bengaluru")
        assert ok is False
        assert "contradiction" in warning.lower() or "associated with" in warning.lower()

    def test_noida_pin_with_noida(self):
        """Address #2: 201301 is valid for Noida."""
        ok, warning = validate_pin_city_consistency("201301", "Noida")
        assert ok is True

    def test_no_city_skips_check(self):
        ok, warning = validate_pin_city_consistency("560066", None)
        assert ok is True

    def test_no_pin_skips_check(self):
        ok, warning = validate_pin_city_consistency(None, "Bengaluru")
        assert ok is True


# =====================================================================
# NON-ADDRESS DETECTION
# =====================================================================

class TestNonAddressDetection:
    def test_same_as_last_time(self):
        """Address #15: 'same as last time' is not an address."""
        is_non, warning = detect_non_address("same as last time")
        assert is_non is True

    def test_conversational_text(self):
        """Address #10: conversational text is not an address."""
        is_non, warning = detect_non_address(
            "The address is my office on the 3rd floor, I'll come down to collect"
        )
        assert is_non is True

    def test_valid_address_not_flagged(self):
        """A normal address should not be flagged as non-address."""
        is_non, _ = detect_non_address(
            "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066"
        )
        assert is_non is False


# =====================================================================
# AMBIGUITY DETECTION
# =====================================================================

class TestAmbiguityDetection:
    def test_landmark_only_address(self):
        """Address #4: landmark-only should be flagged as ambiguous."""
        is_ambig, _ = detect_ambiguity("near big temple, opp SBI ATM, Malviya Nagar")
        assert is_ambig is True

    def test_normal_address_not_ambiguous(self):
        is_ambig, _ = detect_ambiguity("Flat 302, Tower B, Prestige Lakeside")
        assert is_ambig is False


# =====================================================================
# PLUS CODE DETECTION
# =====================================================================

class TestPlusCodeDetection:
    def test_plus_code_detected(self):
        """Address #11: Plus Code format should be detected."""
        has_plus, warning = detect_plus_code("7GQ8+3M Noida, Uttar Pradesh")
        assert has_plus is True
        assert "Plus Code" in warning

    def test_normal_address_no_plus_code(self):
        has_plus, _ = detect_plus_code("Flat 302, Tower B, Bangalore 560066")
        assert has_plus is False


# =====================================================================
# SENSITIVE DATA DETECTION
# =====================================================================

class TestSensitiveDataDetection:
    def test_gate_code_detected(self):
        """Address #13: gate code should be flagged."""
        has_sensitive, _ = detect_sensitive_data(
            "Plot 15, DLF Phase 3, Nathupur, Gurugram — 122002 (gate code: 4455#)"
        )
        assert has_sensitive is True

    def test_normal_address_no_sensitive(self):
        has_sensitive, _ = detect_sensitive_data("Flat 302, Tower B, Bangalore 560066")
        assert has_sensitive is False


# =====================================================================
# REQUIRED FIELDS
# =====================================================================

class TestRequiredFields:
    def test_complete_address(self):
        result = ClaudeParseResult(
            house="Flat 302", locality="Whitefield",
            city="Bengaluru", state="Karnataka", pin="560066",
            confidence=0.95,
        )
        has_min, warnings = check_required_fields(result)
        assert has_min is True

    def test_no_city_no_locality(self):
        """Should flag when both city and locality are missing."""
        result = ClaudeParseResult(confidence=0.1)
        has_min, warnings = check_required_fields(result)
        assert has_min is False
        assert any("cannot be routed" in w for w in warnings)

    def test_missing_pin_warns(self):
        result = ClaudeParseResult(city="Bengaluru", confidence=0.6)
        has_min, warnings = check_required_fields(result)
        assert has_min is True  # Still routable
        assert any("PIN" in w for w in warnings)


# =====================================================================
# FULL VALIDATION — END-TO-END SCENARIOS
# =====================================================================

class TestFullValidation:
    def test_valid_complete_address(self):
        """Address #1: Should pass all validation."""
        raw = "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066"
        claude = ClaudeParseResult(
            house="Flat 302, Tower B", locality="Prestige Lakeside, Whitefield",
            city="Bengaluru", state="Karnataka", pin="560066",
            confidence=0.95,
        )
        result = validate_address(raw, claude)
        assert result.pin_valid is True
        assert result.pin_city_consistent is True
        assert result.is_non_address is False

    def test_contradictory_pin_address_8(self):
        """Address #8: Bangalore address with Delhi PIN — must flag contradiction."""
        raw = "23, 2nd Cross, 5th Main, Koramangala 5th Block, Bangalore - 110001"
        claude = ClaudeParseResult(
            house="23", street="2nd Cross, 5th Main",
            locality="Koramangala 5th Block", city="Bengaluru",
            state="Karnataka", pin="110001",
            confidence=0.7, needs_review=True,
            warnings=["PIN 110001 appears to be a Delhi PIN, not Bengaluru"],
        )
        result = validate_address(raw, claude)
        assert result.pin_city_consistent is False
        assert result.override_status == "NEEDS_REVIEW"

    def test_unparseable_non_address(self):
        """Address #10: Conversational text → UNPARSEABLE."""
        raw = "The address is my office on the 3rd floor, I'll come down to collect"
        claude = ClaudeParseResult(confidence=0.05, needs_review=True)
        result = validate_address(raw, claude)
        assert result.is_non_address is True
        assert result.override_status == "UNPARSEABLE"

    def test_unparseable_reference(self):
        """Address #15: 'same as last time' → UNPARSEABLE."""
        raw = "same as last time"
        claude = ClaudeParseResult(confidence=0.05, needs_review=True)
        result = validate_address(raw, claude)
        assert result.is_non_address is True
        assert result.override_status == "UNPARSEABLE"

    def test_plus_code_needs_review(self):
        """Address #11: Plus Code without house → NEEDS_REVIEW."""
        raw = "7GQ8+3M Noida, Uttar Pradesh"
        claude = ClaudeParseResult(
            city="Noida", state="Uttar Pradesh",
            confidence=0.4, needs_review=True,
        )
        result = validate_address(raw, claude)
        assert result.has_plus_code is True
        assert result.override_status == "NEEDS_REVIEW"

    def test_missing_pin_address_3(self):
        """Address #3: Missing PIN → should warn but might still parse."""
        raw = "B-2/403, Vasant Kunj, New Delhi"
        claude = ClaudeParseResult(
            house="B-2/403", locality="Vasant Kunj",
            city="New Delhi", state="Delhi",
            confidence=0.75, needs_review=True,
            warnings=["Missing PIN code"],
        )
        result = validate_address(raw, claude)
        assert any("PIN" in w for w in result.warnings)
