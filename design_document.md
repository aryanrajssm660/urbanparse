# Design Document — UrbanDash Address Parser

## Problem Understanding

UrbanDash is a quick-commerce platform delivering in 10–30 minutes across Indian metros. Customers enter delivery addresses as free text, but the routing system requires structured address records. ~15% of orders have address issues causing delivery failures.

**The core challenge:** Indian addresses are uniquely difficult to parse — they use multiple languages, informal abbreviations, inconsistent formats, city aliases, and often contain non-address content mixed in (delivery instructions, gate codes, recipient names).

**What we're building:** A system that accepts raw text, uses AI (Claude) for intelligent extraction, applies deterministic validation as a guardrail, and provides a review UI for human operators to inspect and correct flagged addresses.

---

## Architecture

```
┌──────────────────┐
│  React + Vite    │  ← TypeScript, premium dark UI
│  (Frontend)      │
└────────┬─────────┘
         │ HTTP (Vite proxy in dev)
         ▼
┌──────────────────┐
│  FastAPI + Pydantic │  ← Request validation, error handling, CORS
│  (API Layer)        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Address Service  │  ← Business logic orchestration
│  (Orchestrator)   │
└───┬──────────┬───┘
    │          │
    ▼          ▼
┌────────┐ ┌──────────────┐
│ Claude │ │ Deterministic │
│ Parser │ │ Validator     │
└───┬────┘ └──────┬───────┘
    │             │
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │ SQLite DB    │  ← addresses + parse_logs
    └─────────────┘
```

### Data Flow

1. User submits raw address via UI or API
2. FastAPI validates input (length, emptiness)
3. Address Service creates a DB record (status: PENDING)
4. Claude Parser sends raw text to Claude with structured prompt
5. Claude returns JSON with extracted fields, confidence, and warnings
6. Pydantic validates Claude's output against strict schema
7. Deterministic Validator runs independent checks (PIN, city, ambiguity)
8. Address Service merges Claude's and validator's warnings
9. Final status determined by combined assessment
10. Address record updated, parse log created
11. Response returned to frontend

### Why This Architecture

- **Separation of extraction and validation:** Claude is excellent at understanding messy text but shouldn't be the sole arbiter of factual correctness. Deterministic checks (PIN format, city-PIN consistency) are more reliable as code.
- **Audit trail:** Every parse attempt is logged with model used, prompt version, raw response, and duration. This enables debugging and prompt iteration.
- **Fallback capability:** The system works (with reduced accuracy) even without a Claude API key, using a rule-based parser.

---

## Database Schema

### `addresses` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-incrementing primary key |
| `raw_address` | TEXT NOT NULL | Original customer input, preserved exactly |
| `house` | VARCHAR(255) | Flat/apartment/house number, floor, tower |
| `street` | VARCHAR(255) | Road name, cross, main |
| `locality` | VARCHAR(255) | Area, sector, colony, apartment complex |
| `city` | VARCHAR(100) | Normalized city name |
| `state` | VARCHAR(100) | Full state name |
| `pin` | VARCHAR(6) | 6-digit PIN code |
| `status` | VARCHAR(20) | PENDING \| PARSED \| NEEDS_REVIEW \| UNPARSEABLE \| ERROR |
| `confidence` | FLOAT | 0.0 – 1.0 confidence score |
| `warnings` | TEXT | JSON array of warning strings |
| `created_at` | DATETIME | Record creation timestamp (UTC) |
| `updated_at` | DATETIME | Last modification timestamp (UTC) |

**Design notes:**
- `warnings` is stored as a JSON string rather than a separate table because warnings are always read/written together with the address, and the list is small.
- `pin` is VARCHAR(6) not INTEGER because leading zeros are significant (though Indian PINs don't start with 0, this is defensive design).
- `status` is indexed for efficient filtering on the dashboard.

### `parse_logs` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-incrementing primary key |
| `address_id` | INTEGER FK | References addresses.id |
| `model_used` | VARCHAR(100) | Claude model name (e.g., "claude-sonnet-4-20250514") |
| `prompt_version` | VARCHAR(50) | Prompt template version (e.g., "v1.0") |
| `raw_response` | TEXT | Claude's raw JSON response (for debugging) |
| `parsed_successfully` | BOOLEAN | Whether parsing succeeded |
| `validation_result` | TEXT | JSON of deterministic validation results |
| `parsing_duration_ms` | INTEGER | How long the parse took |
| `created_at` | DATETIME | Parse attempt timestamp |

**Why a separate table:** Multiple parse attempts can exist for one address (re-parsing after prompt changes). This gives full audit history without mutating the main record.

---

## API Design

### POST /api/addresses
**Create and auto-parse a new address.**

Request:
```json
{"raw_address": "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066"}
```

Response (201):
```json
{
  "id": 1,
  "raw_address": "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066",
  "house": "Flat 302, Tower B",
  "street": null,
  "locality": "Prestige Lakeside, Whitefield",
  "city": "Bengaluru",
  "state": "Karnataka",
  "pin": "560066",
  "status": "PARSED",
  "confidence": 0.95,
  "warnings": ["City alias normalized: Bangalore → Bengaluru"],
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00",
  "parse_logs": [...]
}
```

### GET /api/addresses
**List with pagination and filtering.**

Query params: `page`, `page_size`, `status`

### GET /api/addresses/{id}
**Get full detail including parse_logs.**

### POST /api/addresses/{id}/parse
**Re-parse an existing address.** Creates a new parse_log entry.

### PATCH /api/addresses/{id}
**Manual edit.** Accepts partial updates for any structured field or status.

### GET /api/stats
**Dashboard counts by status.**

Response:
```json
{"total": 15, "parsed": 5, "needs_review": 6, "unparseable": 2, "error": 0, "pending": 2}
```

### POST /api/addresses/seed
**Load benchmark data.** Creates and parses all 15 benchmark addresses.

---

## Claude Strategy

### What Claude Does
- Understands free-form text in English and Hindi
- Extracts house, street, locality, city, state, PIN
- Normalizes city aliases and state abbreviations
- Detects delivery instructions vs. address components
- Provides initial confidence assessment
- Flags ambiguity with specific warnings

### What Claude Does NOT Do
- Validate PIN format (deterministic check)
- Check PIN-city consistency (deterministic check)
- Determine final address status (business logic)
- Write to the database
- Make routing decisions

### Output Schema
Claude must return exactly this JSON structure:
```json
{
  "house": "string or null",
  "street": "string or null",
  "locality": "string or null",
  "city": "string or null",
  "state": "string or null",
  "pin": "string or null",
  "confidence": 0.0,
  "warnings": [],
  "needs_review": false
}
```

The output is validated by Pydantic's `ClaudeParseResult` schema. Invalid responses (wrong types, confidence > 1.0, etc.) are caught and the address is marked ERROR.

### Prompt Strategy
- **System prompt** establishes context, rules, and output format
- **User prompt** wraps the raw address with extraction instruction
- **Temperature 0.0** for deterministic extraction
- **Version tracked** for reproducibility

---

## Edge Cases

### Case A — Normal Valid Address (#1, #2, #6)
Status: PARSED. All fields extracted, high confidence, no warnings (except optional alias normalization).

### Case B — Missing PIN (#3)
Status: NEEDS_REVIEW. PIN is null, warning added. City and locality are present so address is partially routable.

### Case C — Missing House/Street (#7)
Status: NEEDS_REVIEW. House is null. Address has city, state, and PIN but lacks street-level precision.

### Case D — City Alias (#1, #7, #12, #14)
Bangalore→Bengaluru, Bombay→Mumbai, Gurgaon→Gurugram, BLR→Bengaluru. Claude normalizes in extraction; a warning notes the normalization.

### Case E — Hindi Address (#5)
Claude transliterates: टावर A→Tower A, फ्लैट 12→Flat 12, सेक्टर 62→Sector 62, नोएडा→Noida. All fields extracted normally.

### Case F — Contradictory PIN (#8)
Koramangala, Bangalore with PIN 110001 (which is Delhi). Both Claude AND the deterministic validator flag this independently. Status: NEEDS_REVIEW with explicit warning about the contradiction.

### Case G — Plus Code (#11)
"7GQ8+3M Noida, Uttar Pradesh" — Detected as a Plus Code. City/state extracted, but no house/street/locality. Status: NEEDS_REVIEW because a Plus Code alone cannot be used for street-level delivery without resolution.

### Case H — Not an Address (#10)
"The address is my office on the 3rd floor, I'll come down to collect" — Detected as conversational text by both Claude (low confidence) and validator (non-address pattern match). Status: UNPARSEABLE.

### Case I — Previous Reference (#15)
"same as last time" — Detected by non-address pattern regex. Status: UNPARSEABLE. We don't have previous order data to look up.

### Case J — Gate Code (#13)
"(gate code: 4455#)" — Detected by sensitive data pattern. Warning added. Gate code is NOT stored in any address field. Address itself is parsed normally.

### Case K — Recipient Name (#9)
"c/o Rahul Verma" — Claude separates the name from the address. Warning notes the recipient name. Address fields contain only the actual address.

---

## Technical Decisions

### 1. SQLite instead of PostgreSQL
**Why:** Assessment simplicity. No external database to install.
**Trade-off:** Limited concurrent write performance. Not production-grade.
**Mitigation:** WAL mode enabled for better read concurrency.

### 2. Fallback Parser instead of Fail-on-No-Key
**Why:** The reviewer should be able to test the system immediately without an API key.
**Trade-off:** Fallback parser provides lower accuracy (capped at 0.65 confidence).
**Alternative considered:** Require API key and fail with a clear error. Chosen approach is more reviewer-friendly.

### 3. Deterministic Validation as Separate Layer
**Why:** LLMs can be overconfident. A PIN format check is trivially correct as code but unreliable as an LLM judgment.
**Alternative considered:** Let Claude do all validation. Rejected because Claude can accept "Bangalore 110001" as valid if the rest of the address is convincing.

### 4. JSON Warnings in Address Table
**Why:** Warnings are always read/written with the address. A separate warnings table adds joins without benefit for this data size.
**Alternative considered:** Separate `address_warnings` table with foreign key. Appropriate for production scale but over-engineered here.

### 5. Single parse_logs Table for Audit
**Why:** Enables prompt iteration tracking and debugging. When the prompt changes, you can compare results across versions.
**Alternative considered:** No logging — just overwrite. Rejected because audit trail is valuable for prompt engineering.

### 6. Pydantic for Both API and LLM Validation
**Why:** Same validation library enforces the contract at the API boundary AND the Claude output boundary. No duplicate schemas.

### 7. Monolithic Architecture
**Why:** The assessment explicitly warns against over-engineering (no microservices, no Kafka, etc.). A clean modular monolith is appropriate for this scope.

---

## Production Improvements

### Database
- **PostgreSQL** for concurrent writes, full-text search, JSONB fields
- **Alembic** for schema migrations

### Parsing Pipeline
- **Queue-based parsing** (Redis/Celery) to handle burst traffic without blocking the API
- **Retry strategy** with exponential backoff for Claude API failures
- **Batch parsing** endpoint for bulk address ingestion

### Observability
- **Structured logging** (JSON format for log aggregation)
- **Metrics** (parsing latency, success rate, status distribution)
- **Alerting** on error rate spikes

### Address Quality
- **Geocoding integration** (Google Maps, Mapbox) to validate addresses against real-world data
- **Plus Code resolution** using Google Maps API
- **Full PIN database** from India Post for comprehensive validation
- **Address history** to resolve "same as last time" references

### Security
- **Authentication** (JWT/OAuth2) for API access
- **Rate limiting** (per-IP and per-user)
- **Input sanitization** beyond length checks
- **Audit logging** for all manual edits

### Frontend
- **Pagination controls** in the UI
- **Bulk edit** workflow
- **Export** to CSV/Excel
- **Real-time updates** via WebSocket
- **Address map visualization**

### Infrastructure
- **Docker** compose for single-command setup
- **CI/CD** pipeline with automated testing
- **Health monitoring** and auto-restart
