"""
Tests for the Claude parser module.

Tests both the response parsing logic and error handling.
Uses mocked Claude responses to avoid API calls during testing.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.claude_parser import ClaudeParser, ClaudeParserError, FallbackParser
from app.schemas.address import ClaudeParseResult


class TestClaudeResponseParsing:
    """Test that Claude's JSON responses are correctly parsed into ClaudeParseResult."""

    def test_valid_json_response(self):
        """Simulates a well-formed Claude response."""
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "house": "Flat 302, Tower B",
            "street": None,
            "locality": "Prestige Lakeside, Whitefield",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pin": "560066",
            "confidence": 0.95,
            "warnings": [],
            "needs_review": False,
        })
        mock_response.content = [mock_text_block]

        parser = ClaudeParser()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        parser._client = mock_client
        result, raw, duration = parser.parse("Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066")

        assert isinstance(result, ClaudeParseResult)
        assert result.city == "Bengaluru"
        assert result.pin == "560066"
        assert result.confidence == 0.95

    def test_malformed_json_raises_error(self):
        """Claude returns text that isn't valid JSON."""
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "I'm sorry, I cannot parse this address."
        mock_response.content = [mock_text_block]

        parser = ClaudeParser()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        parser._client = mock_client
        with pytest.raises(ClaudeParserError, match="invalid JSON"):
            parser.parse("some address")

    def test_json_with_code_fences(self):
        """Claude wraps JSON in ```json ... ``` — should still be parsed."""
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = '```json\n{"house": "42", "street": null, "locality": null, "city": "Delhi", "state": "Delhi", "pin": "110001", "confidence": 0.6, "warnings": [], "needs_review": false}\n```'
        mock_response.content = [mock_text_block]

        parser = ClaudeParser()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        parser._client = mock_client
        result, _, _ = parser.parse("42, Delhi 110001")

        assert result.city == "Delhi"
        assert result.pin == "110001"

    def test_empty_response_raises_error(self):
        """Claude returns empty content."""
        mock_response = MagicMock()
        mock_response.content = []

        parser = ClaudeParser()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        parser._client = mock_client
        with pytest.raises(ClaudeParserError, match="empty response"):
            parser.parse("some address")

    def test_invalid_schema_raises_error(self):
        """Claude returns JSON but with invalid field values (e.g., confidence > 1.0)."""
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({
            "house": None, "street": None, "locality": None,
            "city": None, "state": None, "pin": None,
            "confidence": 5.0,  # Invalid: must be 0.0–1.0
            "warnings": [], "needs_review": False,
        })
        mock_response.content = [mock_text_block]

        parser = ClaudeParser()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        parser._client = mock_client
        with pytest.raises(ClaudeParserError, match="schema validation"):
            parser.parse("some address")


class TestFallbackParser:
    """Test the rule-based fallback parser."""

    def test_extracts_pin(self):
        parser = FallbackParser()
        result, _, _ = parser.parse("Flat 302, Bangalore 560066")
        assert result.pin == "560066"

    def test_detects_city_alias(self):
        parser = FallbackParser()
        result, _, _ = parser.parse("Flat 302, Bombay 400053")
        assert result.city == "Mumbai"
        assert result.state == "Maharashtra"

    def test_non_address_detected(self):
        parser = FallbackParser()
        result, _, _ = parser.parse("same as last time")
        assert result.confidence < 0.2
        assert result.needs_review is True

    def test_conversational_non_address(self):
        parser = FallbackParser()
        result, _, _ = parser.parse("I'll come down to collect")
        assert result.needs_review is True

    def test_hindi_city(self):
        parser = FallbackParser()
        result, _, _ = parser.parse("टावर A, फ्लैट 12, सेक्टर 62, नोएडा 201309")
        assert result.city == "Noida"
        assert result.pin == "201309"
