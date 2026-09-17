"""
Address service — orchestration layer between API, Claude, validator, and database.

This is the core business logic module. It coordinates:
  1. Creating address records
  2. Calling Claude for parsing
  3. Running deterministic validation
  4. Determining final status
  5. Persisting results with audit logs

Design: The service layer owns the workflow. Neither the router nor
the parser nor the validator should know about each other directly.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.address import Address, ParseLog
from app.schemas.address import (
    AddressCreate, AddressUpdate, AddressResponse,
    ClaudeParseResult, StatsResponse,
)
from app.services.claude_parser import get_parser, ClaudeParserError
from app.validators.address_validator import validate_address

logger = logging.getLogger(__name__)


class AddressService:
    """Stateless service — receives a DB session per operation."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------

    def create_address(self, data: AddressCreate, auto_parse: bool = True) -> Address:
        """
        Create a new address record and optionally parse it immediately.
        """
        address = Address(
            raw_address=data.raw_address,
            status="PENDING",
            warnings="[]",
        )
        self.db.add(address)
        self.db.commit()
        self.db.refresh(address)

        if auto_parse:
            self.parse_address(address.id)
            self.db.refresh(address)

        return address

    # -------------------------------------------------------------------
    # PARSE
    # -------------------------------------------------------------------

    def parse_address(self, address_id: int) -> Address:
        """
        Parse (or re-parse) an address using Claude + deterministic validation.

        Flow:
          1. Get the raw address
          2. Call Claude (or fallback parser)
          3. Run deterministic validation on Claude's output
          4. Merge warnings from both Claude and validator
          5. Determine final status
          6. Update address record
          7. Create audit log entry
        """
        address = self.db.query(Address).filter(Address.id == address_id).first()
        if not address:
            raise ValueError(f"Address {address_id} not found")

        parser = get_parser()
        parse_log = ParseLog(
            address_id=address.id,
            model_used=getattr(parser, "settings", None) and parser.settings.claude_model or "fallback",
            prompt_version=parser.prompt_version,
        )

        try:
            # Step 1: Claude extraction
            claude_result, raw_response, duration_ms = parser.parse(address.raw_address)
            parse_log.raw_response = raw_response
            parse_log.parsing_duration_ms = duration_ms
            parse_log.parsed_successfully = True

            # Step 2: Deterministic validation
            validation = validate_address(address.raw_address, claude_result)

            # Step 3: Merge warnings (Claude + validator, deduplicated)
            all_warnings = list(claude_result.warnings)  # Claude's warnings first
            for w in validation.warnings:
                if w not in all_warnings:
                    all_warnings.append(w)

            # Step 4: Determine final status
            final_status = validation.override_status or "NEEDS_REVIEW"

            # Step 5: Update address record
            address.house = claude_result.house
            address.street = claude_result.street
            address.locality = claude_result.locality
            address.city = claude_result.city
            address.state = claude_result.state
            address.pin = claude_result.pin
            address.confidence = claude_result.confidence
            address.warnings = json.dumps(all_warnings)
            address.status = final_status
            address.updated_at = datetime.now(timezone.utc)

            # Step 6: Save validation result in parse log
            parse_log.validation_result = json.dumps({
                "pin_valid": validation.pin_valid,
                "pin_city_consistent": validation.pin_city_consistent,
                "has_minimum_fields": validation.has_minimum_fields,
                "is_ambiguous": validation.is_ambiguous,
                "is_non_address": validation.is_non_address,
                "has_plus_code": validation.has_plus_code,
                "has_sensitive_data": validation.has_sensitive_data,
                "final_status": final_status,
            })

        except ClaudeParserError as e:
            logger.error("Parsing failed for address %d: %s", address_id, str(e)[:200])
            parse_log.parsed_successfully = False
            parse_log.raw_response = str(e)[:500]
            address.status = "ERROR"
            address.warnings = json.dumps([f"Parsing error: {str(e)[:200]}"])
            address.updated_at = datetime.now(timezone.utc)

        # Save everything
        self.db.add(parse_log)
        self.db.commit()
        self.db.refresh(address)
        return address

    # -------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------

    def get_address(self, address_id: int) -> Address | None:
        return self.db.query(Address).filter(Address.id == address_id).first()

    def list_addresses(
        self,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> tuple[list[Address], int]:
        """List addresses with optional filtering and pagination."""
        query = self.db.query(Address)

        if status:
            query = query.filter(Address.status == status.upper())

        total = query.count()
        addresses = (
            query
            .order_by(Address.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return addresses, total

    # -------------------------------------------------------------------
    # UPDATE (manual edit)
    # -------------------------------------------------------------------

    def update_address(self, address_id: int, data: AddressUpdate) -> Address | None:
        """
        Manually update parsed address fields (human review workflow).
        Only updates fields that are explicitly provided.
        """
        address = self.db.query(Address).filter(Address.id == address_id).first()
        if not address:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field_name, value in update_data.items():
            setattr(address, field_name, value)

        address.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(address)
        return address

    # -------------------------------------------------------------------
    # STATS
    # -------------------------------------------------------------------

    def get_stats(self) -> StatsResponse:
        """Aggregate counts by status for the dashboard."""
        rows = (
            self.db.query(Address.status, func.count(Address.id))
            .group_by(Address.status)
            .all()
        )
        stats = StatsResponse()
        for status, count in rows:
            status_lower = status.lower() if status else "pending"
            if hasattr(stats, status_lower):
                setattr(stats, status_lower, count)
            stats.total += count
        return stats

    # -------------------------------------------------------------------
    # SEED
    # -------------------------------------------------------------------

    def seed_benchmark_data(self) -> int:
        """
        Load the 15 benchmark addresses and parse them.
        Returns the number of addresses created.
        """
        benchmark_addresses = [
            "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066",
            "H.No. 45, Sector 21, Noida, UP 201301",
            "B-2/403, Vasant Kunj, New Delhi",
            "near big temple, opp SBI ATM, Malviya Nagar",
            "टावर A, फ्लैट 12, सेक्टर 62, नोएडा 201309",
            "WeWork Galaxy, 43 Residency Rd, Shanthala Nagar, Ashok Nagar, Bengaluru, Karnataka 560025",
            "Sector 21, Gurgaon, Haryana 122016",
            "23, 2nd Cross, 5th Main, Koramangala 5th Block, Bangalore - 110001",
            "c/o Rahul Verma, 14 MG Road, Pune 411001",
            "The address is my office on the 3rd floor, I'll come down to collect",
            "7GQ8+3M Noida, Uttar Pradesh",
            "Flat 4A, Sunshine Apts, Bombay 400053",
            "Plot 15, DLF Phase 3, Nathupur, Gurugram — 122002 (gate code: 4455#)",
            "#42, 1st Floor, 100 Feet Road, Indiranagar, BLR 560038",
            "same as last time",
        ]

        count = 0
        for raw in benchmark_addresses:
            data = AddressCreate(raw_address=raw)
            self.create_address(data, auto_parse=True)
            count += 1

        return count
