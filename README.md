# UrbanDash Address Parser

AI-powered Indian address parsing system for quick-commerce delivery operations.

## Overview

UrbanDash Technologies handles thousands of free-text delivery addresses daily across Indian metros. Approximately 15% of orders fail due to address issues. This system:

1. **Accepts** raw customer addresses (Hindi, English, mixed, messy)
2. **Parses** them into structured fields using Claude AI
3. **Validates** results deterministically (PIN format, city consistency, ambiguity detection)
4. **Flags** problematic addresses for human review
5. **Provides** a reviewer UI for inspecting and correcting parsed addresses

### Architecture

```
React + TypeScript + Vite (Frontend)
        ↓
FastAPI + Pydantic (Backend API)
        ↓
Address Service (Orchestration)
        ↓
┌───────────────┐     ┌─────────────────────┐
│ Claude Parser │ ──→ │ Deterministic        │
│ (NLP Extract) │     │ Validator (Guardrail)│
└───────────────┘     └─────────────────────┘
        ↓                       ↓
              SQLite Database
```

**Key design principle:** Claude extracts, the backend validates. Claude's high-confidence output can still contain factual contradictions (e.g., Bangalore address with Delhi PIN), so deterministic validation is always applied independently.

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **Anthropic API Key** (optional — falls back to rule-based parser without it)

---

## Installation

### Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

---

## Environment Variables

Copy the example and fill in your API key:

```bash
cd backend
cp .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
DATABASE_URL=sqlite:///./urbandash.db
CORS_ORIGINS=http://localhost:5173
CLAUDE_MODEL=claude-sonnet-4-20250514
```

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | No* | Anthropic API key for Claude. Falls back to rule-based parser if not set. |
| `DATABASE_URL` | No | SQLite connection string (default: `sqlite:///./urbandash.db`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `http://localhost:5173`) |
| `CLAUDE_MODEL` | No | Claude model identifier (default: `claude-sonnet-4-20250514`) |
| `MAX_ADDRESS_LENGTH` | No | Max characters for input address (default: `1000`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

*Without the API key, the system uses a fallback rule-based parser which provides basic extraction but lower accuracy.

---

## Database Setup

The SQLite database is automatically created on first startup. No manual migration needed.

To reset the database, delete `urbandash.db` and restart the backend.

---

## Running

### Backend

```bash
cd backend
# Activate virtualenv first
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

API docs: `http://localhost:8000/docs` (Swagger UI)

### Frontend

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173`.

The Vite dev server proxies `/api/*` requests to `http://localhost:8000`.

---

## Loading Benchmark Data

Seed the 15 benchmark addresses using the API:

```bash
curl -X POST http://localhost:8000/api/addresses/seed
```

Or click the **"📋 Seed 15 Benchmark"** button in the UI.

---

## Test Commands

```bash
cd backend
# Activate virtualenv first
pytest tests/ -v
```

Test categories:
- `test_validator.py` — PIN format, city consistency, non-address detection, ambiguity, Plus Codes, sensitive data
- `test_claude_parser.py` — JSON parsing, malformed responses, code fences, schema validation, fallback parser
- `test_api.py` — All API endpoints, validation, pagination, persistence, error cases

---

## API Documentation

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/addresses` | Create & auto-parse a new address |
| `GET` | `/api/addresses` | List addresses (paginated, filterable) |
| `GET` | `/api/addresses/{id}` | Get single address with parse history |
| `POST` | `/api/addresses/{id}/parse` | Re-parse an existing address |
| `PATCH` | `/api/addresses/{id}` | Manually edit parsed fields |
| `GET` | `/api/stats` | Dashboard statistics |
| `POST` | `/api/addresses/seed` | Load 15 benchmark addresses |
| `GET` | `/api/health` | Health check |

### Sample API Calls

```bash
# Create and parse an address
curl -X POST http://localhost:8000/api/addresses \
  -H "Content-Type: application/json" \
  -d '{"raw_address": "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066"}'

# List all addresses
curl http://localhost:8000/api/addresses

# Filter by status
curl "http://localhost:8000/api/addresses?status=NEEDS_REVIEW"

# Get specific address with parse history
curl http://localhost:8000/api/addresses/1

# Re-parse an address
curl -X POST http://localhost:8000/api/addresses/1/parse

# Manually correct an address
curl -X PATCH http://localhost:8000/api/addresses/8 \
  -H "Content-Type: application/json" \
  -d '{"pin": "560034", "status": "PARSED"}'

# Get dashboard stats
curl http://localhost:8000/api/stats
```

---

## Claude Configuration

The system uses Claude for natural language address extraction. The prompt:

- Instructs Claude to extract only information present in the input
- Normalizes Indian city aliases (Bangalore→Bengaluru, Bombay→Mumbai)
- Handles Hindi/Devanagari text
- Separates address fields from delivery instructions
- Returns null for uncertain fields (never hallucinates)
- Provides confidence scores and warnings
- Uses temperature=0.0 for deterministic extraction

The prompt is versioned (`v1.0`) and the version is stored in parse logs for auditability.

---

## Known Limitations

1. **PIN-city mapping is limited**: Only covers major Indian metros (Delhi, Bengaluru, Mumbai, etc.). A production system would use India Post's full PIN database.
2. **Fallback parser is basic**: Without Claude, extraction quality is significantly lower.
3. **No address history linking**: "same as last time" is correctly flagged but we don't look up previous orders.
4. **No Plus Code resolution**: Plus Codes are detected but not resolved to street addresses (would require Google Maps API).
5. **SQLite for simplicity**: Not suitable for production concurrency — would need PostgreSQL.
6. **No authentication**: The API is open. Production would need auth + rate limiting.
7. **No geocoding**: Addresses are not validated against a geocoding service.

---

## Project Structure

```
UrbanAddress/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point, CORS, lifecycle
│   │   ├── config.py            # Pydantic Settings from env vars
│   │   ├── database.py          # SQLAlchemy engine, session, Base
│   │   ├── models/
│   │   │   └── address.py       # Address + ParseLog ORM models
│   │   ├── schemas/
│   │   │   └── address.py       # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   └── addresses.py     # API endpoints
│   │   ├── services/
│   │   │   ├── address_service.py  # Business logic orchestration
│   │   │   └── claude_parser.py    # Claude API + fallback parser
│   │   ├── validators/
│   │   │   └── address_validator.py  # Deterministic validation
│   │   └── prompts/
│   │       └── address_prompt.py    # Claude prompt template
│   ├── tests/
│   │   ├── conftest.py          # Test fixtures (in-memory SQLite)
│   │   ├── test_api.py          # API endpoint tests
│   │   ├── test_validator.py    # Validation logic tests
│   │   └── test_claude_parser.py # Parser tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main application
│   │   ├── index.css            # Design system
│   │   ├── api/client.ts        # Typed API client
│   │   ├── types/address.ts     # TypeScript types
│   │   └── components/
│   │       ├── Dashboard.tsx    # Stats cards
│   │       ├── AddressForm.tsx  # Input + seed
│   │       ├── AddressList.tsx  # Filterable table
│   │       ├── AddressDetail.tsx # Review/edit panel
│   │       └── StatusBadge.tsx  # Status badges
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── README.md
├── prompt.md
└── design_document.md
```
