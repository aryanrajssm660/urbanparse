"""
Pydantic schemas for request/response validation and Claude output parsing.

Separated from SQLAlchemy models to keep API contract independent of DB schema.
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Claude output schema — strict contract for LLM response
# ---------------------------------------------------------------------------

class ClaudeParseResult(BaseModel):
    """
    Strict schema for Claude's address parsing output.
    Every field is optional (null) because Claude must return null
    rather than hallucinating a value it cannot determine.
    """
    house: str | None = None
    street: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    pin: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)
    needs_review: bool = False


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AddressCreate(BaseModel):
    """Input schema for creating a new address."""
    raw_address: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Raw address text to parse",
    )

    @field_validator("raw_address")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Address cannot be empty or whitespace-only")
        return v


class AddressUpdate(BaseModel):
    """
    Schema for manually editing parsed address fields.
    All fields optional — only provided fields are updated.
    """
    house: str | None = None
    street: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    pin: str | None = None
    status: str | None = None
    confidence: float | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"PARSED", "NEEDS_REVIEW", "UNPARSEABLE", "ERROR", "PENDING"}
            if v.upper() not in allowed:
                raise ValueError(f"Status must be one of {allowed}")
            return v.upper()
        return v

    @field_validator("pin")
    @classmethod
    def validate_pin_format(cls, v: str | None) -> str | None:
        if v is not None and v != "":
            v = v.strip()
            if v and (len(v) != 6 or not v.isdigit()):
                raise ValueError("PIN must be exactly 6 digits")
        return v if v else None


class AddressBatchCreate(BaseModel):
    """Schema for seeding multiple addresses at once."""
    addresses: list[str] = Field(..., min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ParseLogResponse(BaseModel):
    """Response schema for a single parse log entry."""
    id: int
    model_used: str | None
    prompt_version: str | None
    parsed_successfully: bool
    parsing_duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AddressResponse(BaseModel):
    """Full address response with all fields."""
    id: int
    raw_address: str
    house: str | None
    street: str | None
    locality: str | None
    city: str | None
    state: str | None
    pin: str | None
    status: str
    confidence: float | None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    parse_logs: list[ParseLogResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_validator("warnings", mode="before")
    @classmethod
    def deserialize_warnings(cls, v):
        """Handle warnings stored as JSON string in DB."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        if v is None:
            return []
        return v


class AddressListResponse(BaseModel):
    """Paginated list of addresses."""
    items: list[AddressResponse]
    total: int
    page: int
    page_size: int


class StatsResponse(BaseModel):
    """Dashboard statistics."""
    total: int = 0
    parsed: int = 0
    needs_review: int = 0
    unparseable: int = 0
    error: int = 0
    pending: int = 0


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    count: int | None = None
