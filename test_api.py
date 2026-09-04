"""
test_api.py - Unit and Integration Tests for AlphaShield FastAPI Backend
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app, get_agent


class TestFastAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_serves_landing_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AlphaShield Prime", response.text)
        self.assertIn("The Autonomous Quantitative Engine for Institutional Options", response.text)
        self.assertIn("/app", response.text)

    def test_app_serves_trading_desk(self):
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AlphaShield Prime", response.text)
        self.assertIn("Options Strategy Darwinism Lab", response.text)

    def test_health_api(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ONLINE")
        self.assertEqual(data["platform"], "AlphaShield Prime — Quantitative Options Desk")

    def test_get_status(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("portfolio_equity", data)
        self.assertIn("cash_balance", data)
        self.assertIn("buying_power", data)
        self.assertIn("account_number", data)
        self.assertIn("status", data)

    def test_get_darwinism(self):
        response = self.client.get("/api/darwinism")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("strategies", data)
        self.assertIn("market_regime", data)
        self.assertEqual(len(data["strategies"]), 3)
        self.assertEqual(data["strategies"][0]["edge_score"], 92)

    def test_get_positions(self):
        response = self.client.get("/api/positions")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_orders(self):
        response = self.client.get("/api/orders?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_market(self):
        response = self.client.get("/api/market")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "SPY")
        self.assertEqual(data["timeframe"], "15m")
        self.assertIn("metrics", data)
        self.assertIn("bars", data)
        self.assertIn("ema_21_series", data)

    def test_get_market_timeframes(self):
        for tf in ["1m", "5m", "15m", "1h", "1D"]:
            response = self.client.get(f"/api/market?timeframe={tf}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["symbol"], "SPY")
            self.assertEqual(data["timeframe"], tf)
            self.assertTrue(len(data["bars"]) > 0)

    def test_post_trigger_dry_run(self):
        response = self.client.post("/api/trigger", json={"dry_run": True})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["mode"], "DRY_RUN")
        self.assertIn("cycle_result", data)
        self.assertIn("council_debate", data["cycle_result"])

    def test_post_liquidate(self):
        response = self.client.post("/api/liquidate")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("message", data)

    def test_get_watchlist(self):
        response = self.client.get("/api/watchlist")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 4)
        symbols = [item["symbol"] for item in data]
        self.assertEqual(symbols, ["SPY", "QQQ", "NVDA", "TSLA"])
        # Verify structure
        spy_item = data[0]
        self.assertEqual(spy_item["symbol"], "SPY")
        self.assertTrue(spy_item["is_whitelisted"])
        self.assertIn("price", spy_item)
        self.assertIn("change_pct", spy_item)
        self.assertIn("sparkline", spy_item)
        self.assertIsInstance(spy_item["sparkline"], list)

    def test_get_portfolio_history_default_1d(self):
        response = self.client.get("/api/portfolio/history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["timeframe"], "1D")
        self.assertEqual(data["base_equity"], 100000.0)
        self.assertIn("current_equity", data)
        self.assertIn("net_pnl", data)
        self.assertIn("points", data)
        self.assertIsInstance(data["points"], list)
        self.assertGreaterEqual(len(data["points"]), 20)
        first_point = data["points"][0]
        self.assertIn("timestamp", first_point)
        self.assertIn("equity", first_point)
        self.assertIn("pnl", first_point)

    def test_get_portfolio_history_1w(self):
        response = self.client.get("/api/portfolio/history?timeframe=1W")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["timeframe"], "1W")
        self.assertEqual(len(data["points"]), 7)

    def test_get_portfolio_history_1m(self):
        response = self.client.get("/api/portfolio/history?timeframe=1M")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["timeframe"], "1M")
        self.assertEqual(len(data["points"]), 30)

    def test_get_portfolio_history_invalid_timeframe(self):
        response = self.client.get("/api/portfolio/history?timeframe=1Y")
        self.assertEqual(response.status_code, 422)  # Validation error on pattern constraint

    def test_get_options_chain(self):
        response = self.client.get("/api/options/chain?symbol=SPY")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "SPY")
        self.assertIn("spot_price", data)
        self.assertIn("calls", data)
        self.assertIn("puts", data)
        self.assertIsInstance(data["calls"], list)
        self.assertIsInstance(data["puts"], list)
        self.assertGreaterEqual(len(data["calls"]), 5)
        self.assertGreaterEqual(len(data["puts"]), 5)

        first_call = data["calls"][0]
        self.assertIn("symbol", first_call)
        self.assertIn("strike", first_call)
        self.assertIn("ask", first_call)
        self.assertIn("bid", first_call)
        self.assertIn("delta", first_call)
        self.assertIn("moneyness", first_call)

    def test_post_orders_valid_call_ticket(self):
        payload = {
            "symbol": "SPY",
            "contract_type": "CALL",
            "strike": 550.0,
            "qty": 1,
            "price": 2.50,
            "bracket_sl": 0.20,
            "bracket_tp": 0.40,
        }
        response = self.client.post("/api/orders", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("order_id", data)
        self.assertEqual(data["quantity"], 1)
        self.assertEqual(data["contract_type"], "CALL")
        self.assertEqual(data["stop_loss_price"], 2.00)
        self.assertEqual(data["take_profit_price"], 3.50)

    def test_post_orders_valid_put_ticket(self):
        payload = {
            "symbol": "SPY",
            "contract_type": "PUT",
            "strike": 548.0,
            "qty": 2,
            "price": 2.10,
            "bracket_sl": 0.20,
            "bracket_tp": 0.40,
        }
        response = self.client.post("/api/orders", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["quantity"], 2)
        self.assertEqual(data["contract_type"], "PUT")
        self.assertEqual(data["stop_loss_price"], 1.68)
        self.assertEqual(data["take_profit_price"], 2.94)

    def test_post_orders_risk_veto_unauthorized_ticker(self):
        payload = {
            "symbol": "TSLA",
            "contract_type": "CALL",
            "strike": 220.0,
            "qty": 1,
            "price": 3.00,
        }
        response = self.client.post("/api/orders", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Risk Governor Veto", data["detail"])

    def test_post_orders_risk_veto_exceeds_cap(self):
        payload = {
            "symbol": "SPY",
            "contract_type": "CALL",
            "strike": 550.0,
            "qty": 20,
            "price": 35.0,  # 20 * 35.0 * 100 = $70,000 > $5,000 cap
        }
        response = self.client.post("/api/orders", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("exceeds maximum allowed", data["detail"])


if __name__ == "__main__":
    unittest.main()


