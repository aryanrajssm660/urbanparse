"""
Claude API integration for address parsing.

Responsibilities:
  - Sends raw address to Claude with the structured prompt
  - Parses Claude's JSON response into a ClaudeParseResult
  - Handles API errors, timeouts, malformed responses gracefully
  - Never modifies the database directly

Design: This is a pure extraction service — it returns structured data
that the address_service will then validate and persist.
"""

import json
import logging
import time

import anthropic

from app.config import get_settings
from app.prompts.address_prompt import SYSTEM_PROMPT, build_user_prompt, PROMPT_VERSION
from app.schemas.address import ClaudeParseResult

logger = logging.getLogger(__name__)

# Sanitize log output — never log full API keys
_LOG_KEY_PREFIX_LEN = 8


class ClaudeParserError(Exception):
    """Raised when Claude parsing fails irrecoverably."""
    pass


class ClaudeParser:
    """
    Calls the Anthropic API to parse a raw address into structured fields.
    Returns a ClaudeParseResult on success, raises ClaudeParserError on failure.
    """

    def __init__(self):
        self.settings = get_settings()
        self.prompt_version = PROMPT_VERSION
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            if not self.settings.has_claude_key:
                raise ClaudeParserError(
                    "Anthropic API key not configured. Set ANTHROPIC_API_KEY in .env"
                )
            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                timeout=30.0,
            )
        return self._client

    def parse(self, raw_address: str) -> tuple[ClaudeParseResult, str, int]:
        """
        Parse a raw address using Claude.

        Returns:
            Tuple of (parsed_result, raw_response_text, duration_ms)

        Raises:
            ClaudeParserError: If parsing fails for any reason.
        """
        start_time = time.monotonic()

        try:
            response = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": build_user_prompt(raw_address)}
                ],
                temperature=0.0,  # Deterministic extraction
            )

            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Extract text from Claude's response
            raw_text = ""
            for block in response.content:
                if block.type == "text":
                    raw_text += block.text

            if not raw_text.strip():
                raise ClaudeParserError("Claude returned empty response")

            # Parse JSON from Claude's response
            # Handle potential markdown code fences Claude might wrap around JSON
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                # Remove ```json ... ``` wrapper
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            try:
                parsed_dict = json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.error("Claude returned invalid JSON: %s", str(e)[:200])
                raise ClaudeParserError(f"Claude returned invalid JSON: {e}")

            # Validate against our strict Pydantic schema
            try:
                result = ClaudeParseResult(**parsed_dict)
            except Exception as e:
                logger.error("Claude output failed schema validation: %s", str(e)[:200])
                raise ClaudeParserError(f"Claude output failed schema validation: {e}")

            return result, raw_text, duration_ms

        except anthropic.APIConnectionError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            raise ClaudeParserError("Cannot connect to Anthropic API — check network connectivity")

        except anthropic.RateLimitError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            raise ClaudeParserError("Anthropic API rate limit exceeded — please retry later")

        except anthropic.APIStatusError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            # Don't log the full error which might contain key info
            raise ClaudeParserError(f"Anthropic API error (status {e.status_code})")

        except ClaudeParserError:
            raise  # Re-raise our own errors

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Unexpected error during Claude parsing: %s", type(e).__name__)
            raise ClaudeParserError(f"Unexpected parsing error: {type(e).__name__}")


# ---------------------------------------------------------------------------
# Fallback parser for when Claude API key is not configured
# ---------------------------------------------------------------------------

class FallbackParser:
    """
    Rule-based fallback parser used when Claude API is unavailable.
    Provides basic extraction using regex patterns — NOT a replacement
    for Claude, but allows the system to function for testing.
    """

    prompt_version = "fallback-v1.0"

    def parse(self, raw_address: str) -> tuple[ClaudeParseResult, str, int]:
        import re
        start_time = time.monotonic()

        warnings: list[str] = ["Parsed using fallback rule-based parser (Claude API not configured)"]

        # City alias mapping
        city_aliases: dict[str, tuple[str, str]] = {
            "bangalore": ("Bengaluru", "Karnataka"),
            "bengaluru": ("Bengaluru", "Karnataka"),
            "blr": ("Bengaluru", "Karnataka"),
            "bombay": ("Mumbai", "Maharashtra"),
            "mumbai": ("Mumbai", "Maharashtra"),
            "gurgaon": ("Gurugram", "Haryana"),
            "gurugram": ("Gurugram", "Haryana"),
            "noida": ("Noida", "Uttar Pradesh"),
            "new delhi": ("New Delhi", "Delhi"),
            "delhi": ("Delhi", "Delhi"),
            "pune": ("Pune", "Maharashtra"),
            "chennai": ("Chennai", "Tamil Nadu"),
            "kolkata": ("Kolkata", "West Bengal"),
            "hyderabad": ("Hyderabad", "Telangana"),
            "नोएडा": ("Noida", "Uttar Pradesh"),
        }

        # State abbreviations
        state_abbrevs = {
            "up": "Uttar Pradesh", "mp": "Madhya Pradesh",
            "ap": "Andhra Pradesh", "tn": "Tamil Nadu",
            "wb": "West Bengal", "hr": "Haryana",
            "ka": "Karnataka", "mh": "Maharashtra",
            "dl": "Delhi",
        }

        # Extract PIN (6-digit number)
        pin_match = re.search(r"\b(\d{6})\b", raw_address)
        pin = pin_match.group(1) if pin_match else None

        # Detect non-address patterns
        non_address_patterns = [
            r"\bsame\s+as\s+(last|previous)",
            r"\bi['\u2019]ll\s+come",
            r"\bcome\s+down\s+to\s+collect",
        ]
        for pat in non_address_patterns:
            if re.search(pat, raw_address, re.IGNORECASE):
                duration_ms = int((time.monotonic() - start_time) * 1000)
                result = ClaudeParseResult(
                    confidence=0.05,
                    warnings=["Input is not a routable address"],
                    needs_review=True,
                )
                return result, "{}", duration_ms

        # Try to find city
        city = None
        state = None
        addr_lower = raw_address.lower()

        for alias, (norm_city, norm_state) in city_aliases.items():
            if alias in addr_lower:
                city = norm_city
                state = norm_state
                break

        # Try to find state abbreviation
        if not state:
            for abbr, full_state in state_abbrevs.items():
                if re.search(r"\b" + abbr + r"\b", raw_address, re.IGNORECASE):
                    state = full_state
                    break

        # Basic field extraction — very rough
        house = None
        street = None
        locality = None

        # Look for flat/house patterns
        house_match = re.search(
            r"((?:flat|h\.?no\.?|house|plot|#)\s*[\w\-/]+(?:,?\s*(?:tower|floor|block)\s*[\w]+)?)",
            raw_address,
            re.IGNORECASE,
        )
        if house_match:
            house = house_match.group(1).strip().rstrip(",")

        # Confidence based on completeness
        fields_present = sum(1 for f in [house, city, pin] if f)
        confidence = min(0.3 + (fields_present * 0.2), 0.65)  # Cap at 0.65 for fallback

        if not pin:
            warnings.append("Missing PIN code")
        if not house:
            warnings.append("Missing house/flat number")
        if not city:
            warnings.append("Could not determine city")

        needs_review = confidence < 0.5 or not city

        duration_ms = int((time.monotonic() - start_time) * 1000)
        result = ClaudeParseResult(
            house=house,
            street=street,
            locality=locality,
            city=city,
            state=state,
            pin=pin,
            confidence=confidence,
            warnings=warnings,
            needs_review=needs_review,
        )
        raw_response = json.dumps(result.model_dump())
        return result, raw_response, duration_ms


def get_parser() -> ClaudeParser | FallbackParser:
    """Factory that returns the appropriate parser based on configuration."""
    settings = get_settings()
    if settings.has_claude_key:
        return ClaudeParser()
    else:
        logger.warning("Anthropic API key not configured — using fallback parser")
        return FallbackParser()
