"""
test_brain.py - Unit tests for OptionsBrain
"""

import unittest
import pandas as pd
from brain import OptionsBrain, calculate_rsi, calculate_macd


class TestOptionsBrain(unittest.TestCase):
    def setUp(self):
        self.brain = OptionsBrain()

    def test_compute_indicators(self):
        records = []
        base = 540.0
        for i in range(30):
            records.append({
                'timestamp': f'2026-09-04T10:{i:02d}:00Z',
                'open': base + i * 0.2,
                'high': base + i * 0.2 + 0.3,
                'low': base + i * 0.2 - 0.2,
                'close': base + i * 0.2 + 0.1,
                'volume': 100000 + i * 1000,
            })
        df = pd.DataFrame(records)
        indicators = self.brain.compute_indicators(df)
        self.assertEqual(indicators['symbol'], 'SPY')
        self.assertIn('rsi_14', indicators)
        self.assertIn('macd', indicators)
        self.assertIn('ema_9', indicators)
        self.assertIn('ema_21', indicators)
        self.assertGreater(indicators['current_price'], 540.0)

    def test_generate_candidate_options(self):
        candidates = self.brain.generate_candidate_options(current_price=545.20, exp_days=3)
        self.assertGreater(len(candidates), 0)
        types = {c['type'] for c in candidates}
        self.assertIn('call', types)
        self.assertIn('put', types)
        for c in candidates:
            self.assertTrue(c['symbol'].startswith('SPY'))
            self.assertIn('strike_price', c)

    def test_validate_and_normalize_buy_call(self):
        raw = {
            'action': 'BUY_CALL',
            'contract_symbol': 'SPY260904C00545000',
            'confidence': 0.85,
            'rationale': 'Bullish breakout above 9 EMA',
        }
        res = self.brain._validate_and_normalize(raw)
        self.assertEqual(res['action'], 'BUY_CALL')
        self.assertEqual(res['contract_symbol'], 'SPY260904C00545000')
        self.assertEqual(res['confidence'], 0.85)

    def test_validate_and_normalize_fallback_symbol(self):
        raw = {
            'action': 'BUY_PUT',
            'confidence': 0.75,
            'rationale': 'Bearish momentum breakdown',
        }
        res = self.brain._validate_and_normalize(raw, current_price=545.0)
        self.assertEqual(res['action'], 'BUY_PUT')
        self.assertIsNotNone(res['contract_symbol'])
        self.assertTrue(res['contract_symbol'].startswith('SPY'))

    def test_council_debate_generation(self):
        market_metrics = {
            'current_price': 545.0,
            'rsi_14': 62.5,
            'macd_hist': 0.25,
            '15m_pct_change': 0.40,
        }
        proposal = {
            'action': 'BUY_CALL',
            'confidence': 0.82,
            'contract_symbol': 'SPY260904C00545000',
        }
        debate = self.brain.get_council_debate(market_metrics, proposal)
        self.assertEqual(len(debate), 3)
        roles = [d['role'] for d in debate]
        self.assertIn('Technical Momentum Specialist', roles)
        self.assertIn('Volatility & Options Structurer', roles)
        self.assertIn('Chief Risk Officer (CRO)', roles)


    def test_rsi_flat_prices(self):
        # Flat series where all prices are equal
        flat_series = pd.Series([545.0] * 30)
        rsi = calculate_rsi(flat_series)
        # Should be 50.0 (neutral), not 0.0 or NaN
        self.assertEqual(rsi.iloc[-1], 50.0)

    def test_generate_candidate_options_weekday_normalization(self):
        candidates = self.brain.generate_candidate_options(current_price=545.0, exp_days=3)
        for c in candidates:
            # Verify expiry date is not Saturday (5) or Sunday (6)
            exp_date = pd.to_datetime(c['expiration_date'])
            self.assertIn(exp_date.weekday(), [0, 1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
