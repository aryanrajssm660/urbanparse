"""
Deterministic address validation — the guardrail layer AFTER Claude parsing.

This module performs checks that should NOT be delegated to an LLM:
  - PIN code format validation (exactly 6 digits)
  - PIN-city consistency (known prefix mappings)
  - Required fields assessment
  - Ambiguity / non-address detection
  - Sensitive data detection
  - Plus Code detection
  - Final status determination

Design principle: Claude extracts, the validator verifies.
A high-confidence LLM response can still contain factual contradictions.
"""

import re
from dataclasses import dataclass, field
from app.schemas.address import ClaudeParseResult


# ---------------------------------------------------------------------------
# Known PIN prefix → city mappings for Indian metros
# Source: India Post PIN code directory (first 2-3 digits)
# This is intentionally limited to benchmark cities; a production system
# would use a full PIN database or India Post API.
# ---------------------------------------------------------------------------
PIN_CITY_MAP: dict[str, list[str]] = {
    "110": ["Delhi", "New Delhi"],
    "120": ["Gurugram", "Gurgaon", "Faridabad"],
    "121": ["Gurugram", "Gurgaon", "Faridabad"],
    "122": ["Gurugram", "Gurgaon"],
    "201": ["Noida", "Ghaziabad"],
    "400": ["Mumbai", "Bombay"],
    "411": ["Pune"],
    "500": ["Hyderabad"],
    "560": ["Bengaluru", "Bangalore"],
    "600": ["Chennai", "Madras"],
    "700": ["Kolkata", "Calcutta"],
}

# Patterns that indicate the input is NOT a real address
NON_ADDRESS_PATTERNS = [
    re.compile(r"\bsame\s+as\s+(last|previous|before)\b", re.IGNORECASE),
    re.compile(r"\blast\s+time\b", re.IGNORECASE),
    re.compile(r"\bprevious\s+(address|order)\b", re.IGNORECASE),
    re.compile(r"\bi['\u2019]ll\s+(come|be)\b", re.IGNORECASE),
    re.compile(r"\bcome\s+down\s+to\s+collect\b", re.IGNORECASE),
    re.compile(r"\bcall\s+me\s+when\b", re.IGNORECASE),
]

# Patterns indicating vague/landmark-only addresses
AMBIGUOUS_PATTERNS = [
    re.compile(r"^(near|opp|opposite|behind|next\s+to|beside|in\s+front\s+of)\b", re.IGNORECASE),
    re.compile(r"^(near|opp)\s+.{3,}$", re.IGNORECASE),
]

# Plus Code pattern: 4-8 alphanumeric + 2-3 alphanumeric (e.g., 7GQ8+3M)
PLUS_CODE_PATTERN = re.compile(r"\b[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3}\b", re.IGNORECASE)

# Gate code / access code patterns
SENSITIVE_PATTERNS = [
    re.compile(r"gate\s*code", re.IGNORECASE),
    re.compile(r"access\s*code", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"pin\s*code\s*[:=]", re.IGNORECASE),
    re.compile(r"otp", re.IGNORECASE),
]


@dataclass
class ValidationResult:
    """Result of deterministic validation."""
    is_valid: bool = True
    warnings: list[str] = field(default_factory=list)
    override_status: str | None = None  # If set, overrides Claude's suggestion
    pin_valid: bool = True
    pin_city_consistent: bool = True
    has_minimum_fields: bool = True
    is_ambiguous: bool = False
    is_non_address: bool = False
    has_plus_code: bool = False
    has_sensitive_data: bool = False


def validate_pin_format(pin: str | None) -> tuple[bool, str | None]:
    """Check if PIN is exactly 6 digits. Returns (is_valid, warning)."""
    if pin is None:
        return True, None  # Missing is handled by required-fields check
    pin = pin.strip()
    if not pin:
        return True, None
    if len(pin) != 6 or not pin.isdigit():
        return False, f"Invalid PIN format: '{pin}' (must be exactly 6 digits)"
    return True, None


def validate_pin_city_consistency(pin: str | None, city: str | None) -> tuple[bool, str | None]:
    """
    Check if the PIN prefix is consistent with the stated city.
    This catches contradictions like "Bangalore - 110001" (110xxx is Delhi).
    """
    if not pin or not city:
        return True, None

    pin = pin.strip()
    if len(pin) != 6 or not pin.isdigit():
        return True, None  # Format issue handled elsewhere

    prefix_3 = pin[:3]
    prefix_2 = pin[:2]

    # Check 3-digit prefix first (more specific), then 2-digit
    for prefix in [prefix_3, prefix_2]:
        if prefix in PIN_CITY_MAP:
            expected_cities = [c.lower() for c in PIN_CITY_MAP[prefix]]
            if city.lower() not in expected_cities:
                expected = ", ".join(PIN_CITY_MAP[prefix])
                return False, (
                    f"PIN {pin} (prefix {prefix}) is associated with {expected}, "
                    f"but city is '{city}'. Possible contradiction."
                )
            return True, None

    return True, None  # Unknown prefix — can't validate


def check_required_fields(result: ClaudeParseResult) -> tuple[bool, list[str]]:
    """
    Determine whether enough information exists for delivery routing.
    At minimum, we need EITHER (city or locality) to have any chance of routing.
    """
    warnings = []

    has_location = bool(result.city or result.locality)
    has_house = bool(result.house)
    has_pin = bool(result.pin)

    if not has_location:
        warnings.append("Missing both city and locality — address cannot be routed")
        return False, warnings

    if not has_house:
        warnings.append("Missing house/flat number — delivery may be imprecise")

    if not has_pin:
        warnings.append("Missing PIN code")

    if not result.street and not result.locality:
        warnings.append("Missing street and locality — address is very vague")

    # An address with city + locality but no house is usable but needs review
    sufficient = has_location
    return sufficient, warnings


def detect_non_address(raw_address: str) -> tuple[bool, str | None]:
    """Detect input that is conversational text, not an actual address."""
    for pattern in NON_ADDRESS_PATTERNS:
        if pattern.search(raw_address):
            return True, "Input appears to be conversational text or a reference to a previous address, not a routable address"
    return False, None


def detect_ambiguity(raw_address: str) -> tuple[bool, str | None]:
    """Detect landmark-only or vague addresses."""
    for pattern in AMBIGUOUS_PATTERNS:
        if pattern.search(raw_address):
            return True, "Address appears to be landmark-based or vague — may not be sufficient for delivery"
    return False, None


def detect_plus_code(raw_address: str) -> tuple[bool, str | None]:
    """Detect Plus Codes (Open Location Codes)."""
    if PLUS_CODE_PATTERN.search(raw_address):
        return True, "Address contains a Plus Code — this identifies a location but does not provide street-level address details"
    return False, None


def detect_sensitive_data(raw_address: str) -> tuple[bool, str | None]:
    """Detect gate codes, access codes, and other sensitive information."""
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(raw_address):
            return True, "Address contains sensitive access information (e.g., gate code) that should not be stored in address fields"
    return False, None


def determine_final_status(
    claude_result: ClaudeParseResult,
    validation: ValidationResult,
) -> str:
    """
    Determine the final address status based on both Claude's assessment
    and deterministic validation.

    Status hierarchy:
      UNPARSEABLE > NEEDS_REVIEW > PARSED

    Key principle: Claude's needs_review is ADDITIVE — if the validator
    finds issues, it can escalate to NEEDS_REVIEW or UNPARSEABLE,
    but it won't downgrade Claude's flags.
    """
    # Non-address input is always unparseable
    if validation.is_non_address:
        return "UNPARSEABLE"

    # No location info at all → unparseable
    if not validation.has_minimum_fields and not claude_result.city and not claude_result.locality:
        return "UNPARSEABLE"

    # Deterministic issues that require human review
    needs_review = claude_result.needs_review  # Start with Claude's assessment
    if not validation.pin_city_consistent:
        needs_review = True
    if not validation.pin_valid:
        needs_review = True
    if validation.is_ambiguous:
        needs_review = True
    if validation.has_plus_code and not claude_result.house:
        needs_review = True
    if not validation.has_minimum_fields:
        needs_review = True

    # Very low confidence from Claude
    if claude_result.confidence < 0.3:
        needs_review = True

    if needs_review:
        return "NEEDS_REVIEW"

    return "PARSED"


def validate_address(
    raw_address: str,
    claude_result: ClaudeParseResult,
) -> ValidationResult:
    """
    Run all deterministic validations and return a comprehensive result.
    This is the single entry point for the validation layer.
    """
    result = ValidationResult()

    # 1. Non-address detection (on raw input)
    is_non_addr, warning = detect_non_address(raw_address)
    if is_non_addr:
        result.is_non_address = True
        result.is_valid = False
        if warning:
            result.warnings.append(warning)

    # 2. Ambiguity detection (on raw input)
    is_ambiguous, warning = detect_ambiguity(raw_address)
    if is_ambiguous:
        result.is_ambiguous = True
        if warning:
            result.warnings.append(warning)

    # 3. Plus Code detection (on raw input)
    has_plus, warning = detect_plus_code(raw_address)
    if has_plus:
        result.has_plus_code = True
        if warning:
            result.warnings.append(warning)

    # 4. Sensitive data detection (on raw input)
    has_sensitive, warning = detect_sensitive_data(raw_address)
    if has_sensitive:
        result.has_sensitive_data = True
        if warning:
            result.warnings.append(warning)

    # 5. PIN format validation (on Claude's output)
    pin_ok, warning = validate_pin_format(claude_result.pin)
    if not pin_ok:
        result.pin_valid = False
        if warning:
            result.warnings.append(warning)

    # 6. PIN-city consistency (on Claude's output)
    pin_city_ok, warning = validate_pin_city_consistency(claude_result.pin, claude_result.city)
    if not pin_city_ok:
        result.pin_city_consistent = False
        if warning:
            result.warnings.append(warning)

    # 7. Required fields check (on Claude's output)
    has_min, field_warnings = check_required_fields(claude_result)
    result.has_minimum_fields = has_min
    result.warnings.extend(field_warnings)

    # 8. Determine final status
    result.override_status = determine_final_status(claude_result, result)

    return result
