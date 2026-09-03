"""
test_risk_governor.py - Unit test suite for Risk Governor deterministic safety layers
"""

import unittest
from risk_governor import RiskGovernor, TradeProposal, RiskVerdict


class TestRiskGovernor(unittest.TestCase):
    def setUp(self):
        self.governor = RiskGovernor(
            max_allocation_pct=0.05,
            hard_capital_ceiling=5000.0,
            max_concurrent_positions=2,
            min_confidence=0.60,
        )
        self.portfolio_equity = 100000.0

    def test_approve_valid_buy_call(self):
        proposal = TradeProposal(
            action="BUY_CALL",
            underlying="SPY",
            rationale="Strong bullish breakout on RSI & MACD",
            confidence=0.75,
        )
        verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=self.portfolio_equity,
            current_positions=[],
            contract_premium=3.00,  # $300 per contract
        )
        self.assertTrue(verdict.approved)
        self.assertEqual(verdict.action, "BUY_CALL")
        self.assertEqual(verdict.max_contracts, 16)  # $5,000 / $300 = 16 contracts ($4,800)
        self.assertEqual(verdict.stop_loss_pct, 0.20)
        self.assertEqual(verdict.take_profit_pct, 0.40)

    def test_approve_valid_buy_put(self):
        proposal = TradeProposal(
            action="BUY_PUT",
            underlying="SPY",
            rationale="Bearish breakdown below 9 EMA",
            confidence=0.70,
        )
        verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=self.portfolio_equity,
            current_positions=[],
            contract_premium=2.50,
        )
        self.assertTrue(verdict.approved)
        self.assertEqual(verdict.action, "BUY_PUT")
        self.assertEqual(verdict.max_contracts, 20)  # $5,000 / $250 = 20 contracts ($5,000)

    def test_veto_naked_short_selling(self):
        proposal = TradeProposal(
            action="SELL_CALL",  # Naked call writing
            underlying="SPY",
            rationale="Attempting naked call sell",
            confidence=0.85,
        )
        verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=self.portfolio_equity,
            current_positions=[],
        )
        self.assertFalse(verdict.approved)
        self.assertTrue(any("naked" in r.lower() or "prohibited" in r.lower() for r in verdict.veto_reasons))

    def test_veto_unauthorized_ticker(self):
        proposal = TradeProposal(
            action="BUY_CALL",
            underlying="TSLA",  # Non-SPY ticker
            rationale="Bullish momentum on unapproved ticker",
            confidence=0.85,
        )
        verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=self.portfolio_equity,
            current_positions=[],
        )
        self.assertFalse(verdict.approved)
        self.assertTrue(any("unauthorized" in r.lower() for r in verdict.veto_reasons))

    def test_veto_low_confidence(self):
        proposal = TradeProposal(
            action="BUY_CALL",
            underlying="SPY",
            rationale="Uncertain signal",
            confidence=0.52,  # Below 0.60 threshold
        )
        verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=self.portfolio_equity,
            current_positions=[],
        )
        self.assertFalse(verdict.approved)
        self.assertTrue(any("confidence" in r.lower() for r in verdict.veto_reasons))

    def test_veto_max_concurrent_positions(self):
        proposal = TradeProposal(
            action="BUY_CALL",
            underlying="SPY",
            rationale="Strong signal",
            confidence=0.80,
        )
        existing_positions = ["POS_1", "POS_2"]  # 2 already open
        verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=self.portfolio_equity,
            current_positions=existing_positions,
        )
        self.assertFalse(verdict.approved)
        self.assertTrue(any("concurrent" in r.lower() for r in verdict.veto_reasons))

    def test_exit_targets_calculation(self):
        targets = self.governor.calculate_exit_targets(entry_price=10.00)
        self.assertEqual(targets["entry_price"], 10.00)
        self.assertEqual(targets["stop_loss_price"], 8.00)   # -20%
        self.assertEqual(targets["take_profit_price"], 14.00) # +40%


if __name__ == "__main__":
    unittest.main()
