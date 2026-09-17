"""
FastAPI router for address endpoints.

Endpoints:
  POST   /api/addresses           — Create + auto-parse a new address
  GET    /api/addresses           — List with filtering & pagination
  GET    /api/addresses/{id}      — Get single address detail
  POST   /api/addresses/{id}/parse — Re-parse an existing address
  PATCH  /api/addresses/{id}      — Manual edit (human review)
  GET    /api/stats               — Dashboard statistics
  POST   /api/addresses/seed      — Load benchmark data
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.address import (
    AddressCreate, AddressUpdate, AddressResponse,
    AddressListResponse, StatsResponse, MessageResponse,
)
from app.services.address_service import AddressService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["addresses"])


def _to_response(address) -> AddressResponse:
    """Convert SQLAlchemy Address model to Pydantic response."""
    return AddressResponse.model_validate(address)


# -------------------------------------------------------------------
# POST /api/addresses — Create and auto-parse
# -------------------------------------------------------------------

@router.post("/addresses", response_model=AddressResponse, status_code=201)
def create_address(
    data: AddressCreate,
    db: Session = Depends(get_db),
):
    """
    Accept a raw address, create a record, and parse it using Claude.
    Returns the parsed result with status, confidence, and warnings.
    """
    service = AddressService(db)
    address = service.create_address(data, auto_parse=True)
    return _to_response(address)


# -------------------------------------------------------------------
# GET /api/addresses — List with filtering
# -------------------------------------------------------------------

@router.get("/addresses", response_model=AddressListResponse)
def list_addresses(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List all addresses with optional status filter and pagination."""
    service = AddressService(db)
    addresses, total = service.list_addresses(page=page, page_size=page_size, status=status)
    return AddressListResponse(
        items=[_to_response(a) for a in addresses],
        total=total,
        page=page,
        page_size=page_size,
    )


# -------------------------------------------------------------------
# GET /api/addresses/{id} — Detail view
# -------------------------------------------------------------------

@router.get("/addresses/{address_id}", response_model=AddressResponse)
def get_address(
    address_id: int,
    db: Session = Depends(get_db),
):
    """Get a single address with all parsed fields and parse history."""
    service = AddressService(db)
    address = service.get_address(address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return _to_response(address)


# -------------------------------------------------------------------
# POST /api/addresses/{id}/parse — Re-parse
# -------------------------------------------------------------------

@router.post("/addresses/{address_id}/parse", response_model=AddressResponse)
def parse_address(
    address_id: int,
    db: Session = Depends(get_db),
):
    """
    Re-parse an existing address.
    Useful after updating the Claude prompt or for retrying after errors.
    """
    service = AddressService(db)
    address = service.get_address(address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    try:
        address = service.parse_address(address_id)
    except Exception as e:
        logger.error("Parse request failed for address %d: %s", address_id, str(e)[:200])
        raise HTTPException(
            status_code=502,
            detail="Address parsing failed — please retry later",
        )

    return _to_response(address)


# -------------------------------------------------------------------
# PATCH /api/addresses/{id} — Manual edit
# -------------------------------------------------------------------

@router.patch("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: int,
    data: AddressUpdate,
    db: Session = Depends(get_db),
):
    """
    Manually edit parsed address fields.
    Used during human review to correct parsing results.
    """
    service = AddressService(db)
    address = service.update_address(address_id, data)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return _to_response(address)


# -------------------------------------------------------------------
# GET /api/stats — Dashboard statistics
# -------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Get aggregate statistics by status for the dashboard."""
    service = AddressService(db)
    return service.get_stats()


# -------------------------------------------------------------------
# POST /api/addresses/seed — Load benchmark data
# -------------------------------------------------------------------

@router.post("/addresses/seed", response_model=MessageResponse)
def seed_addresses(db: Session = Depends(get_db)):
    """
    Load the 15 benchmark addresses and parse them.
    Convenience endpoint for the reviewer to populate test data.
    """
    service = AddressService(db)
    count = service.seed_benchmark_data()
    return MessageResponse(
        message=f"Successfully seeded and parsed {count} benchmark addresses",
        count=count,
    )
