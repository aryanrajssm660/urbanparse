# UrbanDash Address Parsing System — Implementation Plan

## Problem Understanding

UrbanDash is a quick-commerce platform where customers enter free-text delivery addresses. ~15% of orders fail due to address issues. We need a system that parses raw addresses into structured fields, flags problematic ones for human review, and provides a reviewer UI — all powered by Claude for NLP extraction with deterministic backend validation as the guardrail.

---

## Phase 1: Benchmark Address Analysis

### Address-by-Address Breakdown

| # | Raw Address | Expected Status | Key Issues | Expected Fields |
|---|-------------|-----------------|------------|-----------------|
| 1 | `Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066` | **PARSED** | City alias (Bangalore→Bengaluru) | house: "Flat 302, Tower B", street: null, locality: "Prestige Lakeside, Whitefield", city: "Bengaluru", state: "Karnataka", pin: "560066" |
| 2 | `H.No. 45, Sector 21, Noida, UP 201301` | **PARSED** | State abbreviation (UP→Uttar Pradesh) | house: "H.No. 45", street: null, locality: "Sector 21", city: "Noida", state: "Uttar Pradesh", pin: "201301" |
| 3 | `B-2/403, Vasant Kunj, New Delhi` | **NEEDS_REVIEW** | Missing PIN | house: "B-2/403", locality: "Vasant Kunj", city: "New Delhi", state: "Delhi", pin: null |
| 4 | `near big temple, opp SBI ATM, Malviya Nagar` | **NEEDS_REVIEW** | No house, no city, no PIN, landmark-only | house: null, street: null, locality: "Malviya Nagar", city: null, state: null, pin: null |
| 5 | `टावर A, फ्लैट 12, सेक्टर 62, नोएडा 201309` | **PARSED** | Hindi text — Tower A, Flat 12, Sector 62, Noida 201309 | house: "Tower A, Flat 12", locality: "Sector 62", city: "Noida", state: "Uttar Pradesh", pin: "201309" |
| 6 | `WeWork Galaxy, 43 Residency Rd, Shanthala Nagar, Ashok Nagar, Bengaluru, Karnataka 560025` | **PARSED** | Complete, well-structured | house: "WeWork Galaxy, 43", street: "Residency Road", locality: "Shanthala Nagar, Ashok Nagar", city: "Bengaluru", state: "Karnataka", pin: "560025" |
| 7 | `Sector 21, Gurgaon, Haryana 122016` | **NEEDS_REVIEW** | No house number; city alias (Gurgaon→Gurugram) | house: null, locality: "Sector 21", city: "Gurugram", state: "Haryana", pin: "122016" |
| 8 | `23, 2nd Cross, 5th Main, Koramangala 5th Block, Bangalore - 110001` | **NEEDS_REVIEW** | **PIN contradiction** — 110001 is Delhi, not Bangalore/Bengaluru | house: "23", street: "2nd Cross, 5th Main", locality: "Koramangala 5th Block", city: "Bengaluru", state: "Karnataka", pin: "110001" |
| 9 | `c/o Rahul Verma, 14 MG Road, Pune 411001` | **PARSED** | Contains recipient name (should be stripped/noted); "c/o" is delivery instruction | house: "14", street: "MG Road", city: "Pune", state: "Maharashtra", pin: "411001" |
| 10 | `The address is my office on the 3rd floor, I'll come down to collect` | **UNPARSEABLE** | Conversational text, not an address | All fields null |
| 11 | `7GQ8+3M Noida, Uttar Pradesh` | **NEEDS_REVIEW** | Plus Code — no house/street/locality; only city/state derivable | house: null, street: null, locality: null, city: "Noida", state: "Uttar Pradesh", pin: null |
| 12 | `Flat 4A, Sunshine Apts, Bombay 400053` | **PARSED** | City alias (Bombay→Mumbai) | house: "Flat 4A", street: null, locality: "Sunshine Apts", city: "Mumbai", state: "Maharashtra", pin: "400053" |
| 13 | `Plot 15, DLF Phase 3, Nathupur, Gurugram — 122002 (gate code: 4455#)` | **PARSED** | Gate code should be stripped, not stored in address fields | house: "Plot 15", locality: "DLF Phase 3, Nathupur", city: "Gurugram", state: "Haryana", pin: "122002" |
| 14 | `#42, 1st Floor, 100 Feet Road, Indiranagar, BLR 560038` | **PARSED** | City abbreviation (BLR→Bengaluru) | house: "#42, 1st Floor", street: "100 Feet Road", locality: "Indiranagar", city: "Bengaluru", state: "Karnataka", pin: "560038" |
| 15 | `same as last time` | **UNPARSEABLE** | Reference to previous address, not parseable | All fields null |

### Key Insights

1. **City aliases** are common: Bangalore/BLR→Bengaluru, Bombay→Mumbai, Gurgaon→Gurugram
2. **State abbreviations**: UP→Uttar Pradesh
3. **PIN validation is critical**: Address #8 has Bangalore address with Delhi PIN (110001)
4. **Hindi/multilingual**: Address #5 requires extraction from Devanagari
5. **Non-addresses**: #10 and #15 must be flagged as unparseable
6. **Sensitive data**: Gate codes (#13), recipient names (#9) should not be stored as address fields
7. **Plus Codes**: #11 is a valid location format but not a structured address
8. **Landmark-only**: #4 has only landmarks and locality, insufficient for delivery

---

## Phase 2: Architecture Design

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   React +   │────▶│   FastAPI     │────▶│ Address Service  │
│   Vite +    │◀────│   Backend     │◀────│                  │
│  TypeScript │     │              │     │  ┌─────────────┐ │
└─────────────┘     └──────────────┘     │  │Claude Parser│ │
                                         │  └──────┬──────┘ │
                                         │         │        │
                                         │  ┌──────▼──────┐ │
                                         │  │Deterministic│ │
                                         │  │ Validator   │ │
                                         │  └──────┬──────┘ │
                                         │         │        │
                                         │  ┌──────▼──────┐ │
                                         │  │  SQLite DB   │ │
                                         │  └─────────────┘ │
                                         └─────────────────┘
```

### What Claude Does vs. What It Doesn't

| Claude's Job | NOT Claude's Job |
|---|---|
| Extract structured fields from free text | Validate PIN format |
| Understand Hindi/mixed-language input | Check PIN-city consistency |
| Identify delivery instructions vs. address | Determine final status |
| Normalize abbreviations | Store data in DB |
| Detect ambiguity and provide warnings | Enforce required fields |
| Provide initial confidence score | Make final routability decision |

### Deterministic Validation (Post-Claude)

1. **PIN format**: Must be exactly 6 digits
2. **PIN-city consistency**: Known mapping of PIN prefixes → cities
3. **Required fields check**: At minimum city OR locality needed for routability
4. **Ambiguity detection**: Pattern matching for "same as last time", "near X", etc.
5. **Sensitive data detection**: Gate codes, passwords, personal info
6. **Plus Code detection**: Regex for Plus Code format
7. **Status determination**: Combined Claude output + validation results → final status

---

## Phase 3: Proposed Changes

### Project Structure

```
UrbanAddress/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, lifespan
│   │   ├── config.py            # Settings from env vars
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── address.py       # SQLAlchemy models
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── address.py       # Pydantic schemas
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── addresses.py     # API endpoints
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── address_service.py  # Business logic orchestration
│   │   │   └── claude_parser.py    # Claude API integration
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   └── address_validator.py  # Deterministic validation
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── address_prompt.py    # Claude prompt templates
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_api.py
│   │   ├── test_validator.py
│   │   ├── test_claude_parser.py
│   │   └── test_address_service.py
│   ├── requirements.txt
│   ├── .env.example
│   └── seed_data.py
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── AddressList.tsx
│   │   │   ├── AddressDetail.tsx
│   │   │   ├── AddressForm.tsx
│   │   │   └── StatusBadge.tsx
│   │   ├── types/
│   │   │   └── address.ts
│   │   └── hooks/
│   │       └── useAddresses.ts
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── README.md
├── prompt.md
└── design_document.md
```

---

### Backend Components

#### [NEW] `backend/app/config.py`
- Pydantic Settings for env vars (ANTHROPIC_API_KEY, DB path, CORS origins)
- No hardcoded secrets

#### [NEW] `backend/app/database.py`
- SQLAlchemy engine, session, Base
- SQLite with WAL mode for concurrent reads

#### [NEW] `backend/app/models/address.py`
- `Address` model: id, raw_address, house, street, locality, city, state, pin, status, confidence, warnings (JSON), created_at, updated_at
- `ParseLog` model: id, address_id (FK), model_used, prompt_version, raw_response, parsed_successfully, validation_result (JSON), parsing_duration_ms, created_at

#### [NEW] `backend/app/schemas/address.py`
- `AddressCreate` — input validation (raw_address required, max 1000 chars)
- `AddressResponse` — full response with all fields
- `AddressUpdate` — PATCH schema for manual edits
- `ClaudeParseResult` — strict schema for Claude output
- `StatsResponse` — dashboard stats
- `AddressListResponse` — paginated list

#### [NEW] `backend/app/routers/addresses.py`
- `POST /api/addresses` — create + auto-parse
- `GET /api/addresses` — list with filtering/pagination
- `GET /api/addresses/{id}` — detail
- `POST /api/addresses/{id}/parse` — re-parse
- `PATCH /api/addresses/{id}` — manual edit
- `GET /api/stats` — dashboard stats
- `POST /api/addresses/seed` — load benchmark data

#### [NEW] `backend/app/services/claude_parser.py`
- Calls Claude API with structured prompt
- Parses JSON response into Pydantic model
- Handles API errors, timeouts, malformed responses
- Returns structured result or error

#### [NEW] `backend/app/services/address_service.py`
- Orchestrates: create → Claude parse → validate → determine status → save
- Separates Claude's extraction from deterministic validation
- Handles re-parse flow

#### [NEW] `backend/app/validators/address_validator.py`
- PIN format validation (6 digits)
- PIN-city cross-reference (known mappings for benchmark cities)
- Required fields check
- Ambiguity pattern detection
- Plus Code detection
- Sensitive data detection (gate codes, passwords)
- Non-address detection (conversational patterns)
- Final status determination logic

#### [NEW] `backend/app/prompts/address_prompt.py`
- Versioned prompt template for Claude
- System prompt + user prompt construction
- Prompt version identifier for audit trail

---

### Frontend Components

#### [NEW] `frontend/src/components/Dashboard.tsx`
- Stats cards: total, parsed, needs_review, unparseable, error
- Visual indicators with color coding
- Add new address button

#### [NEW] `frontend/src/components/AddressList.tsx`
- Sortable/filterable table
- Status badges with colors
- Click-through to detail
- Filter by status

#### [NEW] `frontend/src/components/AddressDetail.tsx`
- Side-by-side: raw vs structured
- Warnings displayed prominently
- Editable fields for manual correction
- Save/re-parse buttons
- Status and confidence display

---

### Database Schema

```sql
CREATE TABLE addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_address TEXT NOT NULL,
    house TEXT,
    street TEXT,
    locality TEXT,
    city TEXT,
    state TEXT,
    pin TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',  -- PARSED/NEEDS_REVIEW/UNPARSEABLE/ERROR/PENDING
    confidence REAL,
    warnings TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE parse_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address_id INTEGER NOT NULL REFERENCES addresses(id),
    model_used TEXT,
    prompt_version TEXT,
    raw_response TEXT,
    parsed_successfully BOOLEAN,
    validation_result TEXT,  -- JSON
    parsing_duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Phase 4: Verification Plan

### Automated Tests
- `pytest backend/tests/` — all test modules
- Test categories:
  1. Valid address parsing (addresses 1, 2, 6)
  2. Missing PIN handling (address 3)
  3. City alias normalization (addresses 1, 7, 12, 14)
  4. Hindi address parsing (address 5)
  5. Contradictory PIN detection (address 8)
  6. Plus Code handling (address 11)
  7. Non-address detection (addresses 10, 15)
  8. Gate code stripping (address 13)
  9. Recipient name handling (address 9)
  10. Malformed Claude response handling
  11. API input validation
  12. Database persistence

### Manual Verification
- Seed the 15 benchmark addresses
- Verify dashboard stats
- Review each address in detail view
- Edit a flagged address and save
- Verify re-parse functionality

---

## Open Questions

> [!IMPORTANT]
> **Claude API Key**: Do you already have an Anthropic API key set up, or should I configure the system to work with a mock/fallback parser for testing without an API key?

> [!NOTE]
> **Node.js/Python versions**: The plan assumes Python 3.10+ and Node.js 18+. Please confirm these are available on your system.
