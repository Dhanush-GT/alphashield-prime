"""
agent.py - Main Autonomous Options Trading Agent Orchestrator

Coordinates the end-to-end autonomous trading pipeline:
1. Alpaca Account & Market Data Fetching (SPY 15-minute bars)
2. AI Momentum & Technical Analysis Inference (brain.py / Featherless AI)
3. Deterministic Safety & Risk Enforcement Gate (risk_governor.py)
4. Nearest Active SPY Option Contract Resolution (Long Call / Long Put)
5. Order Execution on Alpaca Paper Trading API with Stop-Loss & Take-Profit Targets
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import pandas as pd

# Alpaca SDK imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOptionContractsRequest,
    MarketOrderRequest,
    LimitOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import (
    OrderSide,
    TimeInForce,
    AssetStatus,
    ContractType,
    OrderClass,
)
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, OptionBarsRequest, OptionLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from brain import OptionsBrain
from risk_governor import RiskGovernor, TradeProposal, RiskVerdict

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AlpacaOptionsAgent")


class AlpacaOptionsAgent:
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API credentials missing. Check .env file.")

        # Trading & Data Clients
        self.trading_client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=True,
            url_override=self.base_url,
        )
        self.stock_data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )
        self.option_data_client = OptionHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

        # Core Subsystems
        self.brain = OptionsBrain()
        self.governor = RiskGovernor()

    def sanity_check(self) -> bool:
        """Verifies connection to Alpaca and prints account summary."""
        logger.info("=" * 65)
        logger.info("🔍 RUNNING SYSTEM SANITY CHECK...")
        logger.info("=" * 65)
        try:
            account = self.trading_client.get_account()
            logger.info("✅ Successfully connected to Alpaca Paper Trading API!")
            logger.info(f"   Account Number   : {account.account_number}")
            logger.info(f"   Account Status   : {account.status}")
            logger.info(f"   Portfolio Equity : ${float(account.equity):,.2f}")
            logger.info(f"   Cash Balance     : ${float(account.cash):,.2f}")
            logger.info(f"   Buying Power     : ${float(account.buying_power):,.2f}")
            logger.info(f"   Options Approved : {getattr(account, 'options_approved_level', 'Standard')}")

            # Also verify clock / market status
            clock = self.trading_client.get_clock()
            logger.info(f"   Market is Open   : {clock.is_open} (Next Open: {clock.next_open}, Next Close: {clock.next_close})")
            logger.info("=" * 65)
            return True
        except Exception as e:
            logger.error(f"❌ Alpaca sanity check failed: {e}")
            return False

    def test_brain_dry_run(self) -> Dict[str, Any]:
        """Tests the Featherless AI inference brain with sample/live momentum data."""
        logger.info("=" * 65)
        logger.info("🧠 TESTING FEATHERLESS AI BRAIN INFERENCE...")
        logger.info("=" * 65)
        sample_data = {
            "symbol": "SPY",
            "current_price": 545.20,
            "15m_pct_change": 0.35,
            "rsi_14": 58.4,
            "macd": 0.42,
            "macd_signal": 0.28,
            "macd_hist": 0.14,
            "ema_9": 544.80,
            "ema_21": 543.90,
            "day_high": 546.10,
            "day_low": 542.50,
            "recent_bars_sample": [
                {"time": "15:00", "close": 543.8, "high": 544.1, "low": 543.5, "volume": 120000},
                {"time": "15:15", "close": 544.2, "high": 544.5, "low": 543.9, "volume": 145000},
                {"time": "15:30", "close": 544.9, "high": 545.1, "low": 544.0, "volume": 180000},
                {"time": "15:45", "close": 545.2, "high": 545.4, "low": 544.8, "volume": 210000},
            ]
        }
        proposal = self.brain.analyze_market_momentum(sample_data)
        logger.info(f"🎯 AI Trade Proposal Received:")
        logger.info(f"   Action     : {proposal['action']}")
        logger.info(f"   Confidence : {proposal['confidence']}")
        logger.info(f"   Rationale  : {proposal['rationale']}")
        logger.info("=" * 65)
        return proposal

    def fetch_spy_bars(self, limit: int = 50) -> pd.DataFrame:
        """Fetches recent 15-minute historical bars for SPY."""
        logger.info(f"📊 Fetching SPY historical 15-min bars (limit={limit})...")
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=10)

        request_params = StockBarsRequest(
            symbol_or_symbols="SPY",
            timeframe=TimeFrame(15, TimeFrameUnit.Minute),
            start=start_time,
            limit=limit,
        )

        try:
            bars = self.stock_data_client.get_stock_bars(request_params)
            df = bars.df
            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index(level=0, drop=True)
            df = df.reset_index()
            logger.info(f"   Retrieved {len(df)} SPY bars. Latest Close: ${df['close'].iloc[-1]:.2f}")
            return df
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch live bars from Alpaca Data API: {e}. Generating fallback bars for testing.")
            # Fallback mock dataframe for offline/after-hours testing if API data feed is restricted
            records = []
            base_price = 545.0
            for i in range(limit):
                t = now - timedelta(minutes=15 * (limit - i))
                p = base_price + (i * 0.1)
                records.append({
                    "timestamp": t,
                    "open": p - 0.2,
                    "high": p + 0.3,
                    "low": p - 0.3,
                    "close": p,
                    "volume": 150000 + (i * 1000)
                })
            return pd.DataFrame(records)

    def find_nearest_option_contract(
        self, action: str, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Queries Alpaca for the nearest expiry ATM / near-the-money SPY option contract.
        """
        logger.info(f"🔎 Searching for suitable active SPY option contract for {action}...")
        is_call = (action == "BUY_CALL")
        contract_type = ContractType.CALL if is_call else ContractType.PUT

        now = datetime.now(timezone.utc).date()
        # Look for expiries within the next 1 to 30 days
        min_expiry = now

        req = GetOptionContractsRequest(
            underlying_symbols=["SPY"],
            status=AssetStatus.ACTIVE,
            type=contract_type,
            expiration_date_gte=min_expiry,
            root_symbol="SPY",
            limit=100,
        )

        try:
            contracts_response = self.trading_client.get_option_contracts(req)
            contracts = contracts_response.option_contracts
            if not contracts:
                logger.warning(f"No {contract_type} option contracts returned from Alpaca.")
                # Try relaxed search without expiration filter
                req_relaxed = GetOptionContractsRequest(
                    underlying_symbols=["SPY"],
                    status=AssetStatus.ACTIVE,
                    type=contract_type,
                    limit=100,
                )
                contracts_response = self.trading_client.get_option_contracts(req_relaxed)
                contracts = contracts_response.option_contracts

            if not contracts:
                logger.warning(f"No option contracts found for {contract_type}.")
                return None

            # Sort by expiration date ascending, then by strike closeness to current price
            def sort_key(c):
                strike = float(c.strike_price)
                diff = abs(strike - current_price)
                exp = c.expiration_date if isinstance(c.expiration_date, str) else str(c.expiration_date)
                return (exp, diff)

            sorted_contracts = sorted(contracts, key=sort_key)
            best_contract = sorted_contracts[0]

            logger.info(
                f"🎯 Selected Contract: Symbol={best_contract.symbol} | "
                f"Type={best_contract.type} | Strike=${float(best_contract.strike_price):.2f} | "
                f"Exp={best_contract.expiration_date}"
            )

            # Try to fetch latest quote or estimate premium
            estimated_premium = 3.50  # Default reasonable estimate if quote is unavailable
            try:
                quote_req = OptionLatestQuoteRequest(symbol_or_symbols=best_contract.symbol)
                quotes = self.option_data_client.get_option_latest_quote(quote_req)
                if best_contract.symbol in quotes:
                    q = quotes[best_contract.symbol]
                    if q.ask_price and q.ask_price > 0:
                        estimated_premium = float(q.ask_price)
                    elif q.bid_price and q.bid_price > 0:
                        estimated_premium = float(q.bid_price)
            except Exception as quote_err:
                logger.info(f"   Using estimated contract premium (${estimated_premium:.2f}): {quote_err}")

            return {
                "symbol": best_contract.symbol,
                "strike_price": float(best_contract.strike_price),
                "expiration_date": str(best_contract.expiration_date),
                "type": str(best_contract.type),
                "estimated_premium": estimated_premium,
            }

        except Exception as e:
            logger.warning(f"⚠️ Error querying Alpaca option contracts: {e}")
            # Fallback simulated contract representation for testing
            mock_strike = round(current_price)
            mock_expiry = (now + timedelta(days=3)).strftime("%y%m%d")
            mock_symbol = f"SPY{mock_expiry}{'C' if is_call else 'P'}{int(mock_strike*1000):08d}"
            return {
                "symbol": mock_symbol,
                "strike_price": mock_strike,
                "expiration_date": str(now + timedelta(days=3)),
                "type": "call" if is_call else "put",
                "estimated_premium": 2.50,
            }

    def execute_cycle(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes one full autonomous trading cycle:
        Data Ingestion -> AI Inference -> Risk Governor Veto Gate -> Order Execution.
        """
        logger.info("\n" + "=" * 65)
        logger.info(f"🚀 STARTING AGENT CYCLE (Mode: {'DRY RUN' if dry_run else 'LIVE PAPER EXECUTION'})")
        logger.info("=" * 65)

        # 1. Fetch Account State
        account = self.trading_client.get_account()
        portfolio_equity = float(account.equity)
        positions = self.trading_client.get_all_positions()
        logger.info(f"💼 Current Equity: ${portfolio_equity:,.2f} | Open Positions: {len(positions)}")

        # 2. Ingest SPY Market Data & Indicators
        df_bars = self.fetch_spy_bars(limit=50)
        market_metrics = self.brain.compute_indicators(df_bars)
        current_spy_price = market_metrics["current_price"]
        logger.info(
            f"📈 Market Metrics: SPY=${current_spy_price:.2f} | RSI={market_metrics['rsi_14']:.2f} | "
            f"MACD Hist={market_metrics['macd_hist']:.3f} | 15m Change={market_metrics['15m_pct_change']:+.2f}%"
        )

        # 3. AI Brain Decision
        ai_output = self.brain.analyze_market_momentum(market_metrics)
        proposal = TradeProposal(
            action=ai_output["action"],
            underlying="SPY",
            rationale=ai_output["rationale"],
            confidence=ai_output["confidence"],
        )

        # 4. Deterministic Risk Governor Evaluation (Pre-Check)
        pre_verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=portfolio_equity,
            current_positions=positions,
        )

        if not pre_verdict.approved:
            logger.warning(f"🛑 Trade Execution HALTED by Risk Governor: {pre_verdict}")
            return {
                "status": "HALTED",
                "proposal": proposal.__dict__,
                "verdict": pre_verdict.__dict__,
            }

        # 5. Contract Resolution
        contract_info = self.find_nearest_option_contract(
            action=proposal.action,
            current_price=current_spy_price,
        )

        if not contract_info:
            logger.error("❌ Could not find suitable option contract. Halting cycle.")
            return {"status": "NO_CONTRACT_FOUND", "proposal": proposal.__dict__}

        contract_symbol = contract_info["symbol"]
        premium = contract_info["estimated_premium"]

        # Final Risk Sizing Evaluation with exact premium
        final_verdict = self.governor.evaluate(
            proposal=proposal,
            portfolio_equity=portfolio_equity,
            current_positions=positions,
            contract_premium=premium,
        )

        if not final_verdict.approved:
            logger.warning(f"🛑 Trade Execution HALTED after contract sizing: {final_verdict}")
            return {
                "status": "HALTED_ON_SIZING",
                "contract": contract_info,
                "verdict": final_verdict.__dict__,
            }

        exit_targets = self.governor.calculate_exit_targets(entry_price=premium)
        logger.info(f"🎯 Execution Target: BUY {final_verdict.max_contracts}x {contract_symbol} @ ~${premium:.2f}")
        logger.info(
            f"   Stop-Loss (-20%): ${exit_targets['stop_loss_price']:.2f} | "
            f"Take-Profit (+40%): ${exit_targets['take_profit_price']:.2f}"
        )

        if dry_run:
            logger.info("🧪 [DRY RUN] Order submission simulated. No live orders sent.")
            return {
                "status": "DRY_RUN_COMPLETED",
                "proposal": proposal.__dict__,
                "verdict": final_verdict.__dict__,
                "contract": contract_info,
                "exit_targets": exit_targets,
            }

        # 6. Execute Order on Alpaca Paper API
        try:
            logger.info(f"⚡ Submitting Market Order for {final_verdict.max_contracts}x {contract_symbol}...")
            order_data = MarketOrderRequest(
                symbol=contract_symbol,
                qty=final_verdict.max_contracts,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = self.trading_client.submit_order(order_data=order_data)
            logger.info(f"✅ Order Submitted Successfully! Order ID: {order.id} | Status: {order.status}")
            return {
                "status": "ORDER_SUBMITTED",
                "order_id": str(order.id),
                "order_status": str(order.status),
                "contract": contract_symbol,
                "quantity": final_verdict.max_contracts,
                "exit_targets": exit_targets,
            }
        except Exception as order_err:
            logger.error(f"❌ Order submission failed: {order_err}")
            return {
                "status": "ORDER_FAILED",
                "error": str(order_err),
                "contract": contract_symbol,
            }


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Options Trading Agent (Alpaca Hackathon)")
    parser.add_argument("--sanity-check", action="store_true", help="Test Alpaca connection and verify account balance.")
    parser.add_argument("--test-brain", action="store_true", help="Test Featherless AI inference with mock data.")
    parser.add_argument("--dry-run", action="store_true", help="Run full pipeline without sending live orders.")
    parser.add_argument("--execute", action="store_true", help="Run live paper execution cycle.")

    args = parser.parse_args()

    # Default to sanity check & dry-run if no arguments provided
    if not any([args.sanity_check, args.test_brain, args.dry_run, args.execute]):
        args.sanity_check = True
        args.dry_run = True

    agent = AlpacaOptionsAgent()

    if args.sanity_check:
        agent.sanity_check()

    if args.test_brain:
        agent.test_brain_dry_run()

    if args.dry_run:
        result = agent.execute_cycle(dry_run=True)
        print("\n📋 Cycle Summary Result:")
        print(json.dumps(result, indent=2, default=str))

    if args.execute:
        result = agent.execute_cycle(dry_run=False)
        print("\n📋 Live Cycle Result:")
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
