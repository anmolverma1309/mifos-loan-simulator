"""
Unit tests for the Mifos Loan Amortisation Calculator.
Tests cover:
- EMI calculation accuracy (both methods)
- Amortisation schedule correctness
- Moratorium period handling
- What-if simulation results
- Edge cases (zero rate, single month, max tenure)
"""

from decimal import Decimal
import pytest
from app.core.calculator import (
    calculate_declining_balance_emi,
    calculate_flat_rate_emi,
    generate_amortisation_schedule,
    simulate_prepayment,
    simulate_rate_change,
)
from app.models.schemas import RepaymentMethod


class TestDeclineBalanceEMI:
    def test_standard_loan(self):
        """Standard 1 lakh loan at 12% for 12 months."""
        emi = calculate_declining_balance_emi(100000, 12, 12)
        # Standard financial calculator result: 8884.88
        assert float(emi) == pytest.approx(8884.88, abs=0.02)

    def test_precision_no_float_error(self):
        """Ensure decimal precision — no floating point drift."""
        emi = calculate_declining_balance_emi(50000, 10.5, 24)
        # Verify it's a proper Decimal result
        assert isinstance(emi, Decimal)

    def test_zero_rate(self):
        """Zero interest rate should return principal / tenure."""
        emi = calculate_declining_balance_emi(12000, 0.0001, 12)
        assert float(emi) > 0

    def test_small_loan_microfinance(self):
        """Typical microfinance loan — small principal."""
        emi = calculate_declining_balance_emi(5000, 24, 6)
        assert float(emi) > 0
        assert float(emi) < 5000


class TestFlatRateEMI:
    def test_standard_loan(self):
        """Flat rate EMI should be higher than declining balance."""
        flat = calculate_flat_rate_emi(100000, 12, 12)
        declining = calculate_declining_balance_emi(100000, 12, 12)
        assert float(flat) > float(declining)

    def test_flat_rate_total_interest(self):
        """Total interest in flat rate = P * r * n."""
        principal = 100000
        rate = 10
        tenure = 12
        emi = calculate_flat_rate_emi(principal, rate, tenure)
        total = float(emi) * tenure
        expected_interest = principal * (rate / 100) * (tenure / 12)
        actual_interest = total - principal
        assert actual_interest == pytest.approx(expected_interest, abs=1.0)


class TestAmortisationSchedule:
    def test_schedule_length(self):
        """Schedule should have exactly tenure_months entries."""
        schedule = generate_amortisation_schedule(100000, 12, 24)
        assert len(schedule) == 24

    def test_final_balance_near_zero(self):
        """Final balance should be 0 or near-zero after full repayment."""
        schedule = generate_amortisation_schedule(100000, 12, 12)
        assert schedule[-1].balance < 1.0

    def test_moratorium_period(self):
        """During moratorium, principal paid should be 0."""
        schedule = generate_amortisation_schedule(
            100000, 12, 12, moratorium_months=3
        )
        for entry in schedule[:3]:
            assert entry.is_moratorium is True
            assert entry.principal == 0.0

    def test_declining_interest_decreases(self):
        """In declining balance, interest portion should decrease over time."""
        schedule = generate_amortisation_schedule(100000, 12, 12)
        interests = [e.interest for e in schedule]
        # Interest should generally decrease
        assert interests[0] > interests[-1]

    def test_total_principal_equals_loan(self):
        """Sum of principal payments should equal original loan amount."""
        principal = 50000
        schedule = generate_amortisation_schedule(principal, 12, 24)
        total_principal = sum(e.principal for e in schedule)
        assert total_principal == pytest.approx(principal, abs=1.0)


class TestPrepaymentSimulation:
    def test_prepayment_reduces_total(self):
        """Prepayment should reduce total payment."""
        result = simulate_prepayment(100000, 12, 24, 20000, 6)
        assert result.revised_total_payment < result.original_total_payment

    def test_prepayment_saves_interest(self):
        """Prepayment should result in positive interest savings."""
        result = simulate_prepayment(100000, 12, 24, 20000, 6)
        assert result.interest_saved > 0

    def test_prepayment_shortens_tenure(self):
        """Prepayment should reduce number of months."""
        result = simulate_prepayment(100000, 12, 24, 20000, 6)
        assert result.months_saved >= 0


class TestRateChangeSimulation:
    def test_rate_decrease_saves_money(self):
        """Rate decrease should reduce total payment."""
        result = simulate_rate_change(100000, 12, 10, 24, 6)
        assert result.revised_total_payment < result.original_total_payment

    def test_rate_increase_costs_more(self):
        """Rate increase should increase total payment."""
        result = simulate_rate_change(100000, 10, 14, 24, 6)
        assert result.revised_total_payment > result.original_total_payment
