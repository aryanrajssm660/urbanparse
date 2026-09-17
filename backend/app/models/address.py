"""
SQLAlchemy ORM models for the address parsing system.

Two tables:
  - addresses: stores raw input + parsed/structured fields + status
  - parse_logs: audit trail of every parsing attempt (model, prompt version, duration)
"""

import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_address = Column(Text, nullable=False)

    # Structured fields — all nullable because parsing may fail
    house = Column(String(255), nullable=True)
    street = Column(String(255), nullable=True)
    locality = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pin = Column(String(6), nullable=True)

    # Parsing result metadata
    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )  # PENDING | PARSED | NEEDS_REVIEW | UNPARSEABLE | ERROR
    confidence = Column(Float, nullable=True)
    # Warnings stored as JSON array string, e.g. '["Missing PIN", "City alias normalized"]'
    warnings = Column(Text, nullable=True, default="[]")

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationship to parse logs
    parse_logs = relationship("ParseLog", back_populates="address", cascade="all, delete-orphan")

    @property
    def warnings_list(self) -> list[str]:
        """Deserialize warnings JSON string into a Python list."""
        if not self.warnings:
            return []
        try:
            return json.loads(self.warnings)
        except (json.JSONDecodeError, TypeError):
            return []

    @warnings_list.setter
    def warnings_list(self, value: list[str]):
        self.warnings = json.dumps(value)

    def __repr__(self) -> str:
        return f"<Address id={self.id} status={self.status} city={self.city}>"


class ParseLog(Base):
    """
    Audit trail for every parsing attempt.
    Allows understanding what model/prompt produced a given result,
    and how long it took.
    """
    __tablename__ = "parse_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False, index=True)

    model_used = Column(String(100), nullable=True)       # e.g. "claude-sonnet-4-20250514"
    prompt_version = Column(String(50), nullable=True)     # e.g. "v1.0"
    raw_response = Column(Text, nullable=True)             # Claude's raw JSON response
    parsed_successfully = Column(Boolean, nullable=False, default=False)
    validation_result = Column(Text, nullable=True)        # JSON: deterministic validation output
    parsing_duration_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=_utcnow)

    address = relationship("Address", back_populates="parse_logs")

    def __repr__(self) -> str:
        return f"<ParseLog id={self.id} address_id={self.address_id} success={self.parsed_successfully}>"
