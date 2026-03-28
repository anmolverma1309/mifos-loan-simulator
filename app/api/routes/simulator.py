"""
FastAPI route handlers for all loan simulation endpoints.
Every endpoint checks Redis cache before computing.
Cache miss → compute → store → return.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException

from app.core.calculator import (
    calculate_declining_balance_emi,
    calculate_flat_rate_emi,
    generate_amortisation_schedule,
    simulate_prepayment,
    simulate_rate_change,
)
from app.models.schemas import (
    AmortisationRequest,
    AmortisationResponse,
    EMIRequest,
    EMIResponse,
    PrepaymentRequest,
    RateChangeRequest,
    WhatIfResult,
    RepaymentMethod,
)
from app.services.cache import get_cached, set_cached, make_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Loan Simulator"])


# ─── EMI Calculator ────────────────────────────────────────────────────────────

@router.post(
    "/emi",
    response_model=EMIResponse,
    summary="Calculate EMI",
    description="Calculate monthly EMI for given loan parameters. Supports flat rate and declining balance methods.",
)
async def calculate_emi(request: EMIRequest):
    cache_key = make_cache_key("emi", request.model_dump())
    cached = await get_cached(cache_key)
    if cached:
        return EMIResponse(**cached)

    try:
        if request.method == RepaymentMethod.DECLINING_BALANCE:
            emi = calculate_declining_balance_emi(
                request.principal, request.annual_rate, request.tenure_months
            )
        else:
            emi = calculate_flat_rate_emi(
                request.principal, request.annual_rate, request.tenure_months
            )

        total_payment = float(emi) * request.tenure_months
        total_interest = total_payment - request.principal

        result = EMIResponse(
            principal=request.principal,
            annual_rate=request.annual_rate,
            tenure_months=request.tenure_months,
            method=request.method,
            emi=float(emi),
            total_payment=round(total_payment, 2),
            total_interest=round(total_interest, 2),
        )

        await set_cached(cache_key, result.model_dump())
        return result

    except Exception as e:
        logger.error(f"EMI calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Full Amortisation Schedule ────────────────────────────────────────────────

@router.post(
    "/amortisation",
    response_model=AmortisationResponse,
    summary="Generate Amortisation Schedule",
    description="Generate complete month-by-month amortisation schedule with principal/interest breakdown.",
)
async def get_amortisation_schedule(request: AmortisationRequest):
    cache_key = make_cache_key("schedule", request.model_dump())
    cached = await get_cached(cache_key)
    if cached:
        return AmortisationResponse(**cached)

    try:
        schedule = generate_amortisation_schedule(
            principal=request.principal,
            annual_rate=request.annual_rate,
            tenure_months=request.tenure_months,
            method=request.method,
            moratorium_months=request.moratorium_months,
        )

        if request.method == RepaymentMethod.DECLINING_BALANCE:
            emi = calculate_declining_balance_emi(
                request.principal, request.annual_rate, request.tenure_months
            )
        else:
            emi = calculate_flat_rate_emi(
                request.principal, request.annual_rate, request.tenure_months
            )

        total_payment = sum(e.payment for e in schedule)
        total_interest = sum(e.interest for e in schedule)
        total_principal = sum(e.principal for e in schedule)

        result = AmortisationResponse(
            principal=request.principal,
            annual_rate=request.annual_rate,
            tenure_months=request.tenure_months,
            method=request.method,
            emi=float(emi),
            total_payment=round(total_payment, 2),
            total_interest=round(total_interest, 2),
            total_principal=round(total_principal, 2),
            moratorium_months=request.moratorium_months,
            schedule=schedule,
        )

        await set_cached(cache_key, result.model_dump())
        return result

    except Exception as e:
        logger.error(f"Schedule generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── What-If: Prepayment Simulation ───────────────────────────────────────────

@router.post(
    "/simulate/prepayment",
    response_model=WhatIfResult,
    summary="Simulate Prepayment",
    description="What-if scenario: Calculate savings and revised schedule if borrower makes a lump-sum prepayment.",
)
async def simulate_prepayment_scenario(request: PrepaymentRequest):
    cache_key = make_cache_key("prepayment", request.model_dump())
    cached = await get_cached(cache_key)
    if cached:
        return WhatIfResult(**cached)

    try:
        result = simulate_prepayment(
            principal=request.principal,
            annual_rate=request.annual_rate,
            tenure_months=request.tenure_months,
            prepayment_amount=request.prepayment_amount,
            prepayment_month=request.prepayment_month,
            method=request.method,
        )
        await set_cached(cache_key, result.model_dump())
        return result

    except Exception as e:
        logger.error(f"Prepayment simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── What-If: Rate Change Simulation ──────────────────────────────────────────

@router.post(
    "/simulate/rate-change",
    response_model=WhatIfResult,
    summary="Simulate Rate Change",
    description="What-if scenario: Calculate impact of interest rate change mid-loan tenure.",
)
async def simulate_rate_change_scenario(request: RateChangeRequest):
    cache_key = make_cache_key("rate_change", request.model_dump())
    cached = await get_cached(cache_key)
    if cached:
        return WhatIfResult(**cached)

    try:
        result = simulate_rate_change(
            principal=request.principal,
            original_rate=request.original_rate,
            new_rate=request.new_rate,
            tenure_months=request.tenure_months,
            rate_change_month=request.rate_change_month,
            method=request.method,
        )
        await set_cached(cache_key, result.model_dump())
        return result

    except Exception as e:
        logger.error(f"Rate change simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
