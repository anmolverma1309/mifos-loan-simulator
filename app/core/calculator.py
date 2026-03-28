"""
Mifos Loan Amortisation Calculator
Core calculation engine using Python's decimal module for financial precision.
Supports all repayment methods used in Mifos X / Apache Fineract.
"""

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import List, Optional
from app.models.schemas import (
    AmortisationEntry,
    RepaymentMethod,
    WhatIfResult,
)

# Set high precision for intermediate calculations
getcontext().prec = 28

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
TWELVE = Decimal("12")


def _to_decimal(value) -> Decimal:
    """Safely convert any numeric value to Decimal."""
    return Decimal(str(value))


def _round(value: Decimal) -> Decimal:
    """Round to 2 decimal places using banker-standard ROUND_HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_declining_balance_emi(
    principal: float,
    annual_rate: float,
    tenure_months: int,
) -> Decimal:
    """
    Declining Balance (Reducing Balance) EMI Calculation.
    Formula: EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    Used by most MFIs for fair interest computation.
    """
    p = _to_decimal(principal)
    r = _to_decimal(annual_rate) / HUNDRED / TWELVE
    n = _to_decimal(tenure_months)

    if r == ZERO:
        return _round(p / n)

    factor = (ONE + r) ** int(tenure_months)
    emi = (p * r * factor) / (factor - ONE)
    return _round(emi)


def calculate_flat_rate_emi(
    principal: float,
    annual_rate: float,
    tenure_months: int,
) -> Decimal:
    """
    Flat Rate EMI Calculation.
    Formula: EMI = (P + P*r*n/12) / n
    Interest calculated on original principal throughout tenure.
    Common in some microfinance products.
    """
    p = _to_decimal(principal)
    r = _to_decimal(annual_rate) / HUNDRED
    n = _to_decimal(tenure_months)

    total_interest = p * r * n / TWELVE
    emi = (p + total_interest) / n
    return _round(emi)


def generate_amortisation_schedule(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    method: RepaymentMethod = RepaymentMethod.DECLINING_BALANCE,
    moratorium_months: int = 0,
) -> List[AmortisationEntry]:
    """
    Generate complete month-by-month amortisation schedule.
    Supports both flat rate and declining balance methods.
    Handles moratorium period (interest-only payments).
    """
    schedule = []
    balance = _to_decimal(principal)
    r = _to_decimal(annual_rate) / HUNDRED / TWELVE

    if method == RepaymentMethod.DECLINING_BALANCE:
        # Recalculate EMI on remaining balance after moratorium
        effective_months = tenure_months - moratorium_months
        emi = calculate_declining_balance_emi(principal, annual_rate, effective_months)
    else:
        emi = calculate_flat_rate_emi(principal, annual_rate, tenure_months)

    total_paid = ZERO
    total_interest_paid = ZERO

    for month in range(1, tenure_months + 1):
        interest = _round(balance * r)

        # Moratorium period — interest only, no principal repayment
        if month <= moratorium_months:
            principal_paid = ZERO
            payment = interest
        else:
            if method == RepaymentMethod.DECLINING_BALANCE:
                principal_paid = _round(emi - interest)
            else:
                # Flat rate: equal principal each month
                principal_paid = _round(_to_decimal(principal) / _to_decimal(tenure_months))

            payment = _round(principal_paid + interest)

        balance = _round(max(balance - principal_paid, ZERO))
        total_paid += payment
        total_interest_paid += interest

        schedule.append(
            AmortisationEntry(
                month=month,
                payment=float(payment),
                principal=float(principal_paid),
                interest=float(interest),
                balance=float(balance),
                is_moratorium=(month <= moratorium_months),
            )
        )

    return schedule


def simulate_prepayment(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    prepayment_amount: float,
    prepayment_month: int,
    method: RepaymentMethod = RepaymentMethod.DECLINING_BALANCE,
) -> WhatIfResult:
    """
    What-if simulation: What happens if borrower makes a lump-sum prepayment?
    Returns revised schedule and savings comparison.
    """
    # Original schedule
    original = generate_amortisation_schedule(principal, annual_rate, tenure_months, method)
    original_total = sum(e.payment for e in original)
    original_interest = sum(e.interest for e in original)

    # Build prepayment scenario
    balance = _to_decimal(principal)
    r = _to_decimal(annual_rate) / HUNDRED / TWELVE
    revised_schedule = []
    prepayment_applied = False

    if method == RepaymentMethod.DECLINING_BALANCE:
        emi = calculate_declining_balance_emi(principal, annual_rate, tenure_months)
    else:
        emi = calculate_flat_rate_emi(principal, annual_rate, tenure_months)

    for month in range(1, tenure_months + 1):
        if balance <= ZERO:
            break

        interest = _round(balance * r)

        if method == RepaymentMethod.DECLINING_BALANCE:
            principal_paid = _round(emi - interest)
        else:
            principal_paid = _round(_to_decimal(principal) / _to_decimal(tenure_months))

        payment = _round(principal_paid + interest)

        # Apply prepayment at specified month
        if month == prepayment_month and not prepayment_applied:
            extra = _to_decimal(prepayment_amount)
            balance = _round(max(balance - principal_paid - extra, ZERO))
            payment = _round(payment + extra)
            prepayment_applied = True
        else:
            balance = _round(max(balance - principal_paid, ZERO))

        revised_schedule.append(
            AmortisationEntry(
                month=month,
                payment=float(payment),
                principal=float(principal_paid),
                interest=float(interest),
                balance=float(balance),
                is_moratorium=False,
            )
        )

    revised_total = sum(e.payment for e in revised_schedule)
    revised_interest = sum(e.interest for e in revised_schedule)

    return WhatIfResult(
        scenario="prepayment",
        original_total_payment=float(_round(_to_decimal(original_total))),
        revised_total_payment=float(_round(_to_decimal(revised_total))),
        interest_saved=float(_round(_to_decimal(original_interest - revised_interest))),
        months_saved=len(original) - len(revised_schedule),
        revised_schedule=revised_schedule,
    )


def simulate_rate_change(
    principal: float,
    original_rate: float,
    new_rate: float,
    tenure_months: int,
    rate_change_month: int,
    method: RepaymentMethod = RepaymentMethod.DECLINING_BALANCE,
) -> WhatIfResult:
    """
    What-if simulation: What happens if interest rate changes mid-loan?
    Common in variable-rate microfinance products.
    """
    original = generate_amortisation_schedule(principal, original_rate, tenure_months, method)
    original_total = sum(e.payment for e in original)
    original_interest = sum(e.interest for e in original)

    balance = _to_decimal(principal)
    r = _to_decimal(original_rate) / HUNDRED / TWELVE
    revised_schedule = []

    if method == RepaymentMethod.DECLINING_BALANCE:
        emi = calculate_declining_balance_emi(principal, original_rate, tenure_months)
    else:
        emi = calculate_flat_rate_emi(principal, original_rate, tenure_months)

    for month in range(1, tenure_months + 1):
        if balance <= ZERO:
            break

        # Switch rate at specified month
        if month >= rate_change_month:
            r = _to_decimal(new_rate) / HUNDRED / TWELVE
            remaining = tenure_months - month + 1
            if method == RepaymentMethod.DECLINING_BALANCE and remaining > 0:
                emi = calculate_declining_balance_emi(float(balance), new_rate, remaining)

        interest = _round(balance * r)

        if method == RepaymentMethod.DECLINING_BALANCE:
            principal_paid = _round(emi - interest)
        else:
            principal_paid = _round(_to_decimal(principal) / _to_decimal(tenure_months))

        balance = _round(max(balance - principal_paid, ZERO))
        payment = _round(principal_paid + interest)

        revised_schedule.append(
            AmortisationEntry(
                month=month,
                payment=float(payment),
                principal=float(principal_paid),
                interest=float(interest),
                balance=float(balance),
                is_moratorium=False,
            )
        )

    revised_total = sum(e.payment for e in revised_schedule)
    revised_interest = sum(e.interest for e in revised_schedule)

    return WhatIfResult(
        scenario="rate_change",
        original_total_payment=float(_round(_to_decimal(original_total))),
        revised_total_payment=float(_round(_to_decimal(revised_total))),
        interest_saved=float(_round(_to_decimal(original_interest - revised_interest))),
        months_saved=0,
        revised_schedule=revised_schedule,
    )
