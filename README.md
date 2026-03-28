# Mifos Loan Amortisation & What-if Simulator

> **GSoC 2026 Prototype** — The Mifos Initiative  
> A standalone Python microservice for flexible loan amortisation calculations and what-if simulations, designed to integrate with the Mifos X ecosystem.

---

## Problem Statement

Loan officers and clients using Mifos X across 65+ countries currently have no way to:
- Simulate how a rate change will affect future EMIs
- Calculate savings from a lump-sum prepayment
- Model moratorium period impact on total repayment
- Compare flat rate vs declining balance for the same loan

This microservice fills that gap — a lightweight, API-first simulation engine that plugs directly into Mifos X web app and android client.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Mifos Ecosystem                     │
│                                                     │
│   ┌──────────────┐      ┌──────────────────────┐   │
│   │  Mifos X     │      │  Android Client      │   │
│   │  Web App     │      │  (android-client)    │   │
│   └──────┬───────┘      └──────────┬───────────┘   │
│          │                         │                │
│          └──────────┬──────────────┘                │
│                     │ HTTP REST                     │
└─────────────────────┼─────────────────────────────-─┘
                      │
          ┌───────────▼───────────┐
          │  Loan Simulator API   │
          │  (FastAPI + Python)   │
          │                       │
          │  ┌─────────────────┐  │
          │  │ Calculation     │  │
          │  │ Engine          │  │
          │  │ (decimal math)  │  │
          │  └────────┬────────┘  │
          │           │           │
          │  ┌────────▼────────┐  │
          │  │  Redis Cache    │  │
          │  └─────────────────┘  │
          └───────────┬───────────┘
                      │ Optional
          ┌───────────▼───────────┐
          │  Apache Fineract API  │
          │  (Live loan fetch)    │
          └───────────────────────┘
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/emi` | Calculate monthly EMI |
| `POST` | `/api/v1/amortisation` | Generate full schedule |
| `POST` | `/api/v1/simulate/prepayment` | Prepayment what-if |
| `POST` | `/api/v1/simulate/rate-change` | Rate change what-if |
| `GET`  | `/api/v1/health` | Health check |
| `GET`  | `/docs` | Swagger UI |
| `GET`  | `/redoc` | ReDoc UI |

---

## Supported Repayment Methods

### Declining Balance (Reducing Balance)
The most common method in microfinance institutions. Interest is calculated on the outstanding principal balance — so as you repay, your interest reduces.

```
EMI = P × r × (1+r)ⁿ / ((1+r)ⁿ - 1)

Where:
  P = Principal
  r = Monthly interest rate (annual_rate / 12 / 100)
  n = Tenure in months
```

### Flat Rate
Interest is calculated on the original principal throughout the entire tenure.

```
EMI = (P + P × r × n) / (n × 12)

Where:
  P = Principal
  r = Annual interest rate / 100
  n = Tenure in months
```

> **Why `decimal.Decimal` and not `float`?**  
> Python's `float` uses IEEE 754 binary arithmetic — `0.1 + 0.2 ≠ 0.3`.  
> Financial calculations require exact decimal precision.  
> This service uses `decimal.Decimal` with `ROUND_HALF_UP` throughout — the same rounding standard used by Apache Fineract.

---

## Quick Start

### Option 1 — Docker (Recommended)
```bash
git clone https://github.com/YOUR_USERNAME/mifos-loan-simulator.git
cd mifos-loan-simulator
docker-compose up --build
```
Service runs at: http://localhost:8000  
Swagger docs at: http://localhost:8000/docs

### Option 2 — Local Setup
```bash
git clone https://github.com/YOUR_USERNAME/mifos-loan-simulator.git
cd mifos-loan-simulator

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env       # Configure your environment

uvicorn main:app --reload
```

---

## Example API Calls

### Calculate EMI
```bash
curl -X POST http://localhost:8000/api/v1/emi \
  -H "Content-Type: application/json" \
  -d '{
    "principal": 100000,
    "annual_rate": 12.5,
    "tenure_months": 24,
    "method": "declining_balance"
  }'
```

**Response:**
```json
{
  "principal": 100000.0,
  "annual_rate": 12.5,
  "tenure_months": 24,
  "method": "declining_balance",
  "emi": 4729.17,
  "total_payment": 113500.08,
  "total_interest": 13500.08
}
```

---

### Generate Amortisation Schedule (with Moratorium)
```bash
curl -X POST http://localhost:8000/api/v1/amortisation \
  -H "Content-Type: application/json" \
  -d '{
    "principal": 50000,
    "annual_rate": 10.0,
    "tenure_months": 12,
    "method": "declining_balance",
    "moratorium_months": 2
  }'
```

---

### Simulate Prepayment
```bash
curl -X POST http://localhost:8000/api/v1/simulate/prepayment \
  -H "Content-Type: application/json" \
  -d '{
    "principal": 100000,
    "annual_rate": 12.0,
    "tenure_months": 36,
    "prepayment_amount": 20000,
    "prepayment_month": 12,
    "method": "declining_balance"
  }'
```

**Response:**
```json
{
  "scenario": "prepayment",
  "original_total_payment": 119851.20,
  "revised_total_payment": 108432.50,
  "interest_saved": 11418.70,
  "months_saved": 4,
  "revised_schedule": [...]
}
```

---

### Simulate Rate Change
```bash
curl -X POST http://localhost:8000/api/v1/simulate/rate-change \
  -H "Content-Type: application/json" \
  -d '{
    "principal": 75000,
    "original_rate": 14.0,
    "new_rate": 10.5,
    "tenure_months": 48,
    "rate_change_month": 13,
    "method": "declining_balance"
  }'
```

---

## Running Tests
```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

---

## Project Structure

```
mifos-loan-simulator/
├── main.py                        # FastAPI app entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── app/
│   ├── core/
│   │   ├── calculator.py          # Core calculation engine (decimal math)
│   │   └── config.py              # App configuration
│   ├── models/
│   │   └── schemas.py             # Pydantic request/response models
│   ├── services/
│   │   └── cache.py               # Redis caching service
│   └── api/
│       └── routes/
│           └── simulator.py       # API route handlers
└── tests/
    └── test_calculator.py         # Unit tests
```

---

## Redis Caching Strategy

Loan calculations with identical parameters always produce identical results — making them perfect candidates for caching.

- Cache key = SHA256 hash of sorted request parameters
- TTL = 1 hour (configurable via `CACHE_TTL_SECONDS`)
- Cache miss → compute → store → return
- Cache hit → return immediately (no computation)
- Graceful degradation — if Redis is unavailable, service continues without cache

---

## Planned Features (Full GSoC Implementation)

- [ ] Missed payment simulation
- [ ] Live Mifos X loan fetch via Fineract API
- [ ] Python client SDK (`pip install mifos-loan-sdk`)
- [ ] Mifos X web-app integration
- [ ] Android client integration
- [ ] Amortisation schedule export (CSV/PDF)
- [ ] Multi-currency support
- [ ] Loan restructuring simulator

---

## Why This Service Matters

Mifos X serves microfinance institutions across 65+ countries helping the 3 billion unbanked access financial services. Loan officers today make restructuring decisions without simulation tools — this service gives them the ability to model "what if" scenarios before committing clients to new terms.

---

## Related Mifos Repositories

- [openMF/web-app](https://github.com/openMF/web-app) — Mifos X Angular Web App
- [openMF/android-client](https://github.com/openMF/android-client) — Mifos X Android App
- [apache/fineract](https://github.com/apache/fineract) — Apache Fineract (Mifos X backend)

---

## GSoC 2026

This prototype was built as part of the Google Summer of Code 2026 application for **The Mifos Initiative**.

**Project:** Intelligent Loan Amortisation & What-if Simulator Service  
**Mentors:** Priyanshu Tiwari, Akshat Sharma, Rahul Goel  
**Slack:** #mifos-x-dev | #wg-ai-for-all

---

## License

Apache License 2.0 — consistent with the Mifos Initiative's open source licensing.
