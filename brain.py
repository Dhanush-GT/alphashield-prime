"""
brain.py - AI Reasoning Brain powered by Featherless AI (zai-org/GLM-5.2)

Ingests recent SPY momentum data (RSI, MACD, 15-minute price action summary),
synthesizes market context, and calls Featherless AI's OpenAI-compatible API
to produce a structured JSON trade thesis:
{
    "action": "BUY_CALL" | "BUY_PUT" | "HOLD",
    "rationale": "...",
    "confidence": 0.0 - 1.0
}
"""

import os
import re
import json
import logging
import requests
import pandas as pd
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("OptionsBrain")


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))


def calculate_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, pd.Series]:
    """Calculates MACD Line, Signal Line, and MACD Histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
    }


class OptionsBrain:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("FEATHERLESS_API_KEY", "")
        self.base_url = (base_url or os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")).rstrip("/")
        self.model = model or os.getenv("FEATHERLESS_MODEL", "zai-org/GLM-5.2")

        if not self.api_key:
            logger.warning("⚠️ FEATHERLESS_API_KEY is not set. Inference calls will fail.")

    def compute_indicators(self, df_bars: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes RSI, MACD, Moving Averages, and summarizes 15-min bar momentum.
        Expects df_bars with columns: ['timestamp'/'time', 'open', 'high', 'low', 'close', 'volume'].
        """
        if df_bars.empty or len(df_bars) < 15:
            raise ValueError(f"Insufficient bars to compute indicators. Need >= 15 bars, got {len(df_bars)}.")

        df = df_bars.copy()
        # Normalize column names to lowercase
        df.columns = [str(c).lower() for c in df.columns]

        df["rsi"] = calculate_rsi(df["close"], period=14)
        macd_dict = calculate_macd(df["close"])
        df["macd"] = macd_dict["macd_line"]
        df["macd_signal"] = macd_dict["signal_line"]
        df["macd_hist"] = macd_dict["histogram"]
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        latest_close = float(latest["close"])
        prev_close = float(prev["close"])
        pct_change = ((latest_close - prev_close) / prev_close) * 100

        # Summarize last 5 bars of 15m price action
        recent_bars = []
        for _, row in df.tail(5).iterrows():
            recent_bars.append({
                "time": str(row.get("timestamp", row.name)),
                "close": round(float(row["close"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "volume": int(row.get("volume", 0)),
            })

        indicators = {
            "symbol": "SPY",
            "current_price": latest_close,
            "15m_pct_change": round(pct_change, 3),
            "rsi_14": round(float(latest["rsi"]), 2) if not pd.isna(latest["rsi"]) else 50.0,
            "macd": round(float(latest["macd"]), 3) if not pd.isna(latest["macd"]) else 0.0,
            "macd_signal": round(float(latest["macd_signal"]), 3) if not pd.isna(latest["macd_signal"]) else 0.0,
            "macd_hist": round(float(latest["macd_hist"]), 3) if not pd.isna(latest["macd_hist"]) else 0.0,
            "ema_9": round(float(latest["ema_9"]), 2),
            "ema_21": round(float(latest["ema_21"]), 2),
            "day_high": round(float(df["high"].max()), 2),
            "day_low": round(float(df["low"].min()), 2),
            "recent_bars_sample": recent_bars,
        }
        return indicators

    def analyze_market_momentum(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends structured momentum metrics to Featherless AI and returns parsed JSON trade proposal.
        """
        system_prompt = (
            "You are an elite quantitative options trading AI operating under strict risk protocols.\n"
            "Your objective is to evaluate short-term momentum and technical indicators for SPY to decide on defined-risk option entries.\n"
            "You MUST respond ONLY with a single valid JSON object adhering strictly to this schema:\n"
            "{\n"
            '  "action": "BUY_CALL" | "BUY_PUT" | "HOLD",\n'
            '  "rationale": "<2-3 sentence technical rationale citing RSI, MACD, and price action>",\n'
            '  "confidence": <float between 0.0 and 1.0>\n'
            "}\n"
            "Rules for actions:\n"
            "- 'BUY_CALL': Bullish momentum, positive MACD divergence, RSI bouncing from oversold or breaking resistance.\n"
            "- 'BUY_PUT': Bearish momentum, negative MACD divergence, RSI turning over from overbought or breaking support.\n"
            "- 'HOLD': Choppy market, conflicting signals, low volume, or low conviction (<0.60 confidence).\n"
            "DO NOT wrap in explanation text outside the JSON block."
        )

        user_prompt = (
            f"SPY Real-Time Momentum & Technical Analysis:\n"
            f"- Current SPY Price: ${market_data.get('current_price', 0):.2f}\n"
            f"- 15-Minute Bar Price Change: {market_data.get('15m_pct_change', 0):+.2f}%\n"
            f"- RSI (14-period): {market_data.get('rsi_14', 50):.2f}\n"
            f"- MACD Line: {market_data.get('macd', 0):.3f} | Signal Line: {market_data.get('macd_signal', 0):.3f} | Histogram: {market_data.get('macd_hist', 0):.3f}\n"
            f"- EMA 9: ${market_data.get('ema_9', 0):.2f} | EMA 21: ${market_data.get('ema_21', 0):.2f}\n"
            f"- Session High: ${market_data.get('day_high', 0):.2f} | Session Low: ${market_data.get('day_low', 0):.2f}\n"
            f"- Last 5 Bars (15m): {json.dumps(market_data.get('recent_bars_sample', []))}\n\n"
            f"Based on the technical momentum above, provide your JSON trade proposal."
        )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        logger.info(f"🧠 Querying Featherless AI ({self.model})...")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            raw_content = message.get("content") or ""
            reasoning = message.get("reasoning") or ""

            logger.info(f"🧠 Raw AI Response Content:\n{raw_content}")
            if reasoning:
                logger.info(f"🧠 Model Reasoning:\n{reasoning[:200]}...")

            target_text = raw_content if raw_content.strip() else reasoning
            parsed_proposal = self._parse_json_response(target_text)
            return parsed_proposal
        except Exception as e:
            logger.error(f"❌ Error communicating with Featherless AI: {e}")
            # Safe fallback to HOLD on any error
            return {
                "action": "HOLD",
                "rationale": f"Featherless inference error / fallback: {str(e)}",
                "confidence": 0.0,
            }

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extracts and validates JSON trade proposal from raw model output."""
        # Try direct JSON parsing
        try:
            res = json.loads(text)
            return self._validate_and_normalize(res)
        except json.JSONDecodeError:
            pass

        # Try regex search for markdown ```json ... ``` or { ... }
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                res = json.loads(match.group(0))
                return self._validate_and_normalize(res)
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse valid JSON from output. Defaulting to HOLD.")
        return {
            "action": "HOLD",
            "rationale": f"Unparseable AI output: {text[:150]}...",
            "confidence": 0.0,
        }

    def _validate_and_normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        action = str(data.get("action", "HOLD")).upper().strip()
        if action not in ["BUY_CALL", "BUY_PUT", "HOLD"]:
            action = "HOLD"

        try:
            confidence = float(data.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.0

        rationale = str(data.get("rationale", "No rationale provided.")).strip()

        return {
            "action": action,
            "rationale": rationale,
            "confidence": confidence,
        }
