"""
test_agent.py - Unit tests for AlpacaOptionsAgent
"""

import unittest
from unittest.mock import MagicMock, patch
from agent import AlpacaOptionsAgent
from risk_governor import TradeProposal


class TestAlpacaOptionsAgent(unittest.TestCase):
    @patch('alpaca_cli.AlpacaCLI.get_account')
    @patch('alpaca_cli.AlpacaCLI.get_clock')
    def test_sanity_check(self, mock_clock, mock_account):
        mock_account.return_value = {
            'account_number': 'PA3CMCT5LP09',
            'status': 'ACTIVE',
            'equity': '100000.00',
            'cash': '100000.00',
            'buying_power': '400000.00',
            'options_approved_level': '3'
        }
        mock_clock.return_value = {'is_open': True}
        agent = AlpacaOptionsAgent()
        self.assertTrue(agent.sanity_check())

    @patch('alpaca_cli.AlpacaCLI.get_stock_bars')
    def test_fetch_spy_bars(self, mock_bars):
        mock_bars.return_value = {'bars': []}  # Tests simulated/fallback generator
        agent = AlpacaOptionsAgent()
        df = agent.fetch_spy_bars(limit=30)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 30)
        for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
            self.assertIn(col, df.columns)

    @patch('alpaca_cli.AlpacaCLI.get_option_contracts')
    def test_find_nearest_option_contract_call(self, mock_contracts):
        mock_contracts.return_value = {
            'option_contracts': [
                {
                    'symbol': 'SPY260904C00545000',
                    'type': 'call',
                    'strike_price': 545.0,
                    'expiration_date': '2026-09-04',
                    'status': 'active',
                }
            ]
        }
        agent = AlpacaOptionsAgent()
        contract = agent.find_nearest_option_contract(action='BUY_CALL', current_price=545.0)
        self.assertIsNotNone(contract)
        self.assertEqual(contract['symbol'], 'SPY260904C00545000')
        self.assertEqual(contract['type'], 'call')
        self.assertEqual(contract['strike_price'], 545.0)

    @patch('alpaca_cli.AlpacaCLI.get_option_contracts')
    def test_find_nearest_option_contract_with_target_symbol(self, mock_contracts):
        mock_contracts.return_value = {
            'option_contracts': [
                {
                    'symbol': 'SPY260904C00540000',
                    'type': 'call',
                    'strike_price': 540.0,
                    'expiration_date': '2026-09-04',
                    'status': 'active',
                },
                {
                    'symbol': 'SPY260904C00550000',
                    'type': 'call',
                    'strike_price': 550.0,
                    'expiration_date': '2026-09-04',
                    'status': 'active',
                }
            ]
        }
        agent = AlpacaOptionsAgent()
        contract = agent.find_nearest_option_contract(
            action='BUY_CALL', current_price=542.0, target_symbol='SPY260904C00550000'
        )
        self.assertIsNotNone(contract)
        self.assertEqual(contract['symbol'], 'SPY260904C00550000')
        self.assertEqual(contract['strike_price'], 550.0)

    @patch('alpaca_cli.AlpacaCLI.run_cli_command')
    def test_submit_bracket_order_cli(self, mock_cmd):
        mock_cmd.return_value = {'id': 'test_bracket_id', 'status': 'submitted'}
        agent = AlpacaOptionsAgent()
        res = agent.cli.submit_bracket_order(
            symbol='SPY260904C00545000',
            qty=5,
            side='buy',
            take_profit_price=3.50,
            stop_loss_price=2.00,
        )
        self.assertEqual(res['id'], 'test_bracket_id')
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        self.assertIn('--order-class', args)
        self.assertIn('bracket', args)
        self.assertIn('--take-profit-limit-price', args)
        self.assertIn('3.50', args)
        self.assertIn('--stop-loss-stop-price', args)
        self.assertIn('2.00', args)

    @patch('alpaca_cli.AlpacaCLI.run_cli_command')
    def test_submit_oco_order_cli(self, mock_cmd):
        mock_cmd.return_value = {'id': 'test_oco_id', 'status': 'submitted'}
        agent = AlpacaOptionsAgent()
        res = agent.cli.submit_oco_order(
            symbol='SPY260904C00545000',
            qty=5,
            take_profit_price=3.50,
            stop_loss_price=2.00,
        )
        self.assertEqual(res['id'], 'test_oco_id')
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        self.assertIn('--order-class', args)
        self.assertIn('oco', args)

    @patch('alpaca_cli.AlpacaCLI.get_account')
    @patch('alpaca_cli.AlpacaCLI.get_positions')
    @patch('alpaca_cli.AlpacaCLI.get_stock_bars')
    @patch('brain.OptionsBrain.analyze_market_momentum')
    def test_execute_cycle_dry_run(self, mock_brain, mock_bars, mock_pos, mock_acc):
        mock_acc.return_value = {'equity': 100000.0}
        mock_pos.return_value = []
        mock_bars.return_value = {'bars': []}
        mock_brain.return_value = {
            'action': 'BUY_CALL',
            'contract_symbol': 'SPY260904C00545000',
            'confidence': 0.85,
            'rationale': 'Strong breakout',
        }

        agent = AlpacaOptionsAgent()
        result = agent.execute_cycle(dry_run=True)
        self.assertEqual(result['status'], 'DRY_RUN_COMPLETED')
        self.assertEqual(result['proposal']['action'], 'BUY_CALL')
        self.assertEqual(result['exit_targets']['stop_loss_pct'], 0.20)
        self.assertEqual(result['exit_targets']['take_profit_pct'], 0.40)
        self.assertEqual(len(result['council_debate']), 3)


if __name__ == '__main__':
    unittest.main()
