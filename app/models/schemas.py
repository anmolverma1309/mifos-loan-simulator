"""
Pydantic v2 models for request/response validation.
All financial values use float for JSON serialization
but are processed internally as Decimal.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RepaymentMethod(str, Enum):
    DECLINING_BALANCE = "declining_balance"
    FLAT_RATE = "flat_rate"


# ─── Request Models ────────────────────────────────────────────────────────────

class AmortisationRequest(BaseModel):
    principal: float = Field(..., gt=0, description="Loan principal amount")
    annual_rate: float = Field(..., gt=0, le=100, description="Annual interest rate in %")
    tenure_months: int = Field(..., gt=0, le=360, description="Loan tenure in months")
    method: RepaymentMethod = Field(
        RepaymentMethod.DECLINING_BALANCE,
        description="Repayment method"
    )
    moratorium_months: int = Field(
        0, ge=0, description="Moratorium period in months (interest only)"
    )

    @field_validator("moratorium_months")
    @classmethod
    def moratorium_less_than_tenure(cls, v, info):
        if "tenure_months" in info.data and v >= info.data["tenure_months"]:
            raise ValueError("Moratorium months must be less than tenure months")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "principal": 50000,
                "annual_rate": 12.5,
                "tenure_months": 24,
                "method": "declining_balance",
                "moratorium_months": 0,
            }
        }
    }


class PrepaymentRequest(BaseModel):
    principal: float = Field(..., gt=0)
    annual_rate: float = Field(..., gt=0, le=100)
    tenure_months: int = Field(..., gt=0, le=360)
    prepayment_amount: float = Field(..., gt=0, description="Lump sum prepayment amount")
    prepayment_month: int = Field(..., gt=0, description="Month at which prepayment is made")
    method: RepaymentMethod = RepaymentMethod.DECLINING_BALANCE

    model_config = {
        "json_schema_extra": {
            "example": {
                "principal": 100000,
                "annual_rate": 10.0,
                "tenure_months": 36,
                "prepayment_amount": 20000,
                "prepayment_month": 12,
                "method": "declining_balance",
            }
        }
    }


class RateChangeRequest(BaseModel):
    principal: float = Field(..., gt=0)
    original_rate: float = Field(..., gt=0, le=100)
    new_rate: float = Field(..., gt=0, le=100)
    tenure_months: int = Field(..., gt=0, le=360)
    rate_change_month: int = Field(..., gt=0, description="Month from which new rate applies")
    method: RepaymentMethod = RepaymentMethod.DECLINING_BALANCE

    model_config = {
        "json_schema_extra": {
            "example": {
                "principal": 75000,
                "original_rate": 12.0,
                "new_rate": 10.5,
                "tenure_months": 48,
                "rate_change_month": 13,
                "method": "declining_balance",
            }
        }
    }


class EMIRequest(BaseModel):
    principal: float = Field(..., gt=0)
    annual_rate: float = Field(..., gt=0, le=100)
    tenure_months: int = Field(..., gt=0, le=360)
    method: RepaymentMethod = RepaymentMethod.DECLINING_BALANCE

    model_config = {
        "json_schema_extra": {
            "example": {
                "principal": 50000,
                "annual_rate": 12.5,
                "tenure_months": 24,
                "method": "declining_balance",
            }
        }
    }


# ─── Response Models ───────────────────────────────────────────────────────────

class AmortisationEntry(BaseModel):
    month: int
    payment: float
    principal: float
    interest: float
    balance: float
    is_moratorium: bool = False


class AmortisationResponse(BaseModel):
    principal: float
    annual_rate: float
    tenure_months: int
    method: RepaymentMethod
    emi: float
    total_payment: float
    total_interest: float
    total_principal: float
    moratorium_months: int
    schedule: List[AmortisationEntry]


class EMIResponse(BaseModel):
    principal: float
    annual_rate: float
    tenure_months: int
    method: RepaymentMethod
    emi: float
    total_payment: float
    total_interest: float


class WhatIfResult(BaseModel):
    scenario: str
    original_total_payment: float
    revised_total_payment: float
    interest_saved: float
    months_saved: int
    revised_schedule: List[AmortisationEntry]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    cache_connected: bool
