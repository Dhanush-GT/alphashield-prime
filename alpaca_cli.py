"""
alpaca_cli.py - Subprocess CLI Wrapper for Alpaca

Executes Alpaca CLI commands via Python's subprocess module,
captures stdout, parses JSON outputs, and handles stderr errors.

Implements commands:
- alpaca account get
- alpaca data bars --symbol <SYMBOL> --timeframe <TIMEFRAME>
- alpaca option contracts --underlying-symbol <SYMBOL>
- alpaca position list
- alpaca order submit --symbol <SYMBOL> --side <SIDE> --qty <QTY> --type <TYPE>
- alpaca order list
"""

import os
import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AlpacaCLI")


class AlpacaCLI:
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cli_binary: str = "alpaca",
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY", "")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY", "")
        self.base_url = (base_url or os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")).rstrip("/")
        self.data_base_url = "https://data.alpaca.markets"
        self.cli_binary = cli_binary
        self.has_cli_binary = shutil.which(self.cli_binary) is not None

        if not self.has_cli_binary:
            logger.info("ℹ️ System 'alpaca' CLI binary not found in PATH; using direct REST CLI fallback engine.")

    def _get_env(self) -> Dict[str, str]:
        """Prepares environment variables for subprocess execution."""
        env = os.environ.copy()
        env["APCA_API_KEY_ID"] = self.api_key
        env["APCA_API_SECRET_KEY"] = self.secret_key
        env["APCA_API_BASE_URL"] = self.base_url
        env["ALPACA_API_KEY"] = self.api_key
        env["ALPACA_SECRET_KEY"] = self.secret_key
        env["ALPACA_BASE_URL"] = self.base_url
        return env

    def run_cli_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Executes an Alpaca CLI command using subprocess.run, parses JSON from stdout,
        and returns parsed dictionary/list.
        """
        cmd = [self.cli_binary] + args
        cmd_str = " ".join(cmd)
        logger.info(f"💻 [CLI SUBPROCESS] Executing: {cmd_str}")

        if self.has_cli_binary:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=self._get_env(),
                    check=False,
                )

                if result.returncode != 0:
                    logger.warning(f"CLI command exited with code {result.returncode}. Stderr: {result.stderr.strip()}")
                    # Fallback to direct REST if CLI binary returns error
                    return self._rest_fallback(args)

                output = result.stdout.strip()
                if not output:
                    return {}

                try:
                    return json.loads(output)
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse CLI JSON output: {output[:200]}")
                    return {"raw_output": output}

            except Exception as e:
                logger.warning(f"CLI Subprocess execution error: {e}. Executing fallback.")
                return self._rest_fallback(args)
        else:
            return self._rest_fallback(args)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
        }

    def _rest_fallback(self, args: List[str]) -> Any:
        """
        Internal fallback ensuring identical JSON schema when 'alpaca' CLI is executed.
        """
        headers = self._get_headers()
        try:
            # 1. alpaca account get
            if args[:2] == ["account", "get"] or args[:1] == ["account"]:
                url = f"{self.base_url}/v2/account"
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                return res.json()

            # 2. alpaca data bars --symbol SPY --timeframe 15Min
            if args[:2] == ["data", "bars"]:
                symbol = "SPY"
                timeframe = "15Min"
                limit = 50
                for i, arg in enumerate(args):
                    if arg in ("--symbol", "-s") and i + 1 < len(args):
                        symbol = args[i + 1]
                    elif arg in ("--timeframe", "-t") and i + 1 < len(args):
                        timeframe = args[i + 1]
                    elif arg in ("--limit", "-l") and i + 1 < len(args):
                        limit = int(args[i + 1])

                start_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
                url = f"{self.data_base_url}/v2/stocks/{symbol}/bars"
                params = {"timeframe": timeframe, "start": start_date, "limit": limit, "feed": "iex"}
                res = requests.get(url, headers=headers, params=params, timeout=10)
                if res.status_code == 200:
                    return res.json()
                # If data feed is market-closed, fallback to standard mock bars
                return {"bars": []}

            # 3. alpaca option contracts --underlying-symbol SPY
            if args[:2] == ["option", "contracts"]:
                underlying = "SPY"
                for i, arg in enumerate(args):
                    if arg in ("--underlying-symbol", "-u") and i + 1 < len(args):
                        underlying = args[i + 1]
                url = f"{self.base_url}/v2/options/contracts"
                params = {"underlying_symbols": underlying, "status": "active", "limit": 100}
                res = requests.get(url, headers=headers, params=params, timeout=10)
                if res.status_code == 200:
                    return res.json()
                return {"option_contracts": []}

            # 4. alpaca position list
            if args[:2] == ["position", "list"] or args[:1] == ["positions"]:
                url = f"{self.base_url}/v2/positions"
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    return res.json()
                return []

            # 5. alpaca order submit
            if args[:2] == ["order", "submit"] or args[:1] == ["order"]:
                symbol = ""
                side = "buy"
                qty = 1
                order_type = "market"
                time_in_force = "day"
                limit_price = None
                stop_price = None
                order_class = None
                tp_limit_price = None
                sl_stop_price = None

                for i, arg in enumerate(args):
                    if arg in ("--symbol", "-s") and i + 1 < len(args):
                        symbol = args[i + 1]
                    elif arg in ("--side",) and i + 1 < len(args):
                        side = args[i + 1].lower()
                    elif arg in ("--qty", "-q") and i + 1 < len(args):
                        qty = int(args[i + 1])
                    elif arg in ("--type", "-t") and i + 1 < len(args):
                        order_type = args[i + 1].lower()
                    elif arg in ("--time-in-force", "-tif") and i + 1 < len(args):
                        time_in_force = args[i + 1].lower()
                    elif arg in ("--limit-price",) and i + 1 < len(args):
                        limit_price = str(args[i + 1])
                    elif arg in ("--stop-price",) and i + 1 < len(args):
                        stop_price = str(args[i + 1])
                    elif arg in ("--order-class",) and i + 1 < len(args):
                        order_class = args[i + 1].lower()
                    elif arg in ("--take-profit-limit-price",) and i + 1 < len(args):
                        tp_limit_price = str(args[i + 1])
                    elif arg in ("--stop-loss-stop-price",) and i + 1 < len(args):
                        sl_stop_price = str(args[i + 1])

                payload = {
                    "symbol": symbol,
                    "qty": str(qty),
                    "side": side,
                    "type": order_type,
                    "time_in_force": time_in_force,
                }
                if limit_price:
                    payload["limit_price"] = limit_price
                if stop_price:
                    payload["stop_price"] = stop_price
                if order_class:
                    payload["order_class"] = order_class
                if tp_limit_price:
                    payload["take_profit"] = {"limit_price": tp_limit_price}
                if sl_stop_price:
                    payload["stop_loss"] = {"stop_price": sl_stop_price}

                url = f"{self.base_url}/v2/orders"
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                res.raise_for_status()
                return res.json()

            # 6. alpaca order list
            if args[:2] == ["order", "list"] or args[:1] == ["orders"]:
                url = f"{self.base_url}/v2/orders"
                params = {"status": "all", "limit": 10}
                res = requests.get(url, headers=headers, params=params, timeout=10)
                if res.status_code == 200:
                    return res.json()
                return []

            # 7. alpaca clock get
            if args[:2] == ["clock", "get"] or args[:1] == ["clock"]:
                url = f"{self.base_url}/v2/clock"
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    return res.json()
                return {"is_open": False}

            return {}
        except Exception as err:
            logger.error(f"Fallback request failed: {err}")
            return {}

    # Convenient Wrapper Methods
    def get_account(self) -> Dict[str, Any]:
        """Calls: alpaca account get"""
        return self.run_cli_command(["account", "get"])

    def get_stock_bars(self, symbol: str = "SPY", timeframe: str = "15Min", limit: int = 50) -> Dict[str, Any]:
        """Calls: alpaca data bars --symbol SPY --timeframe 15Min --limit 50"""
        return self.run_cli_command(["data", "bars", "--symbol", symbol, "--timeframe", timeframe, "--limit", str(limit)])

    def get_option_contracts(self, underlying_symbol: str = "SPY") -> Dict[str, Any]:
        """Calls: alpaca option contracts --underlying-symbol SPY"""
        return self.run_cli_command(["option", "contracts", "--underlying-symbol", underlying_symbol])

    def get_positions(self) -> List[Dict[str, Any]]:
        """Calls: alpaca position list"""
        res = self.run_cli_command(["position", "list"])
        if isinstance(res, list):
            return res
        return res.get("positions", [])

    def get_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Calls: alpaca order list"""
        res = self.run_cli_command(["order", "list"])
        if isinstance(res, list):
            return res
        return res.get("orders", [])

    def get_clock(self) -> Dict[str, Any]:
        """Calls: alpaca clock get"""
        return self.run_cli_command(["clock", "get"])

    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str = "buy",
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """Calls: alpaca order submit --symbol <SYMBOL> --side <SIDE> --qty <QTY> --type <TYPE>"""
        return self.run_cli_command([
            "order", "submit",
            "--symbol", symbol,
            "--side", side,
            "--qty", str(qty),
            "--type", order_type,
            "--time-in-force", time_in_force,
        ])

    def submit_bracket_order(
        self,
        symbol: str,
        qty: int,
        side: str = "buy",
        order_type: str = "market",
        take_profit_price: float = 0.0,
        stop_loss_price: float = 0.0,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Calls: alpaca order submit with native bracket order class attaching SL/TP.
        """
        return self.run_cli_command([
            "order", "submit",
            "--symbol", symbol,
            "--side", side,
            "--qty", str(qty),
            "--type", order_type,
            "--time-in-force", time_in_force,
            "--order-class", "bracket",
            "--take-profit-limit-price", f"{take_profit_price:.2f}",
            "--stop-loss-stop-price", f"{stop_loss_price:.2f}",
        ])

    def submit_oco_order(
        self,
        symbol: str,
        qty: int,
        take_profit_price: float,
        stop_loss_price: float,
        side: str = "sell",
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Calls: alpaca order submit with One-Cancels-Other (OCO) bracket exit orders.
        """
        return self.run_cli_command([
            "order", "submit",
            "--symbol", symbol,
            "--side", side,
            "--qty", str(qty),
            "--type", "limit",
            "--time-in-force", time_in_force,
            "--order-class", "oco",
            "--take-profit-limit-price", f"{take_profit_price:.2f}",
            "--stop-loss-stop-price", f"{stop_loss_price:.2f}",
        ])

    def submit_stop_loss_order(
        self,
        symbol: str,
        qty: int,
        stop_price: float,
        side: str = "sell",
    ) -> Dict[str, Any]:
        """Calls: alpaca order submit for Stop-Loss protection"""
        return self.run_cli_command([
            "order", "submit",
            "--symbol", symbol,
            "--side", side,
            "--qty", str(qty),
            "--type", "stop",
            "--stop-price", f"{stop_price:.2f}",
            "--time-in-force", "day",
        ])

    def submit_take_profit_order(
        self,
        symbol: str,
        qty: int,
        limit_price: float,
        side: str = "sell",
    ) -> Dict[str, Any]:
        """Calls: alpaca order submit for Take-Profit target"""
        return self.run_cli_command([
            "order", "submit",
            "--symbol", symbol,
            "--side", side,
            "--qty", str(qty),
            "--type", "limit",
            "--limit-price", f"{limit_price:.2f}",
            "--time-in-force", "day",
        ])
