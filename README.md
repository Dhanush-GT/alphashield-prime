# Autonomous AI Options Trading Agent (Alpaca Hackathon)

An autonomous quantitative options trading system built for the Alpaca Hackathon. The system couples deep probabilistic reasoning from **Featherless AI** (`zai-org/GLM-5.2`) with deterministic code-level safety guarantees via the **Risk Governor** and executes paper trades on the **Alpaca Paper Trading API**.

---

## 🏛️ System Architecture: The "Reason-Before-Execution" Dual-Veto Framework

Autonomous AI agents in financial markets cannot operate unchecked. This architecture establishes a strict **Separation of Concerns** between *market perception & reasoning* and *capital execution & risk governance*:

```
               ┌────────────────────────────────────────────────────────┐
               │              Alpaca Market Data Stream                 │
               │         (SPY 15-Min Bars, RSI, MACD, Quotes)           │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │               Layer 1: AI Brain (LLM)                  │
               │   Featherless AI (OpenAI-compatible / zai-org/GLM-5.2) │
               │   • Momentum & Divergence Analysis                     │
               │   • Outputs Strict JSON: Action, Rationale, Confidence │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           │ [Trade Proposal]
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │          Layer 2: Deterministic Risk Governor          │
               │                     (VETO GATE)                        │
               │   • 5% Max Portfolio Allocation ($5k Hard Cap)         │
               │   • Max 2 Concurrent Open Positions                    │
               │   • Defined-Risk Whitelist (Long SPY Calls/Puts ONLY)   │
               │   • Naked Selling / Short Writing Hard Block           │
               │   • 20% Stop-Loss & 40% Take-Profit Target Engine      │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           │ [Approved Sizing & Contract]
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │           Layer 3: Execution Orchestrator              │
               │           Alpaca Paper Trading API v2                  │
               │   • Active Option Contract Search (ATM / Nearest DTE)  │
               │   • Bracket / Market Order Dispatch                    │
               └────────────────────────────────────────────────────────┘
```

---

## 🛡️ Deterministic Risk Governor Parameters

| Rule | Parameter | Purpose |
|---|---|---|
| **Max Allocation per Trade** | `5%` of equity (Hard cap: `$5,000`) | Eliminates single-trade catastrophic drawdown risk |
| **Max Concurrent Positions** | `2` positions | Enforces portfolio diversification and prevents over-leveraging |
| **Strategy Constraint** | Long Calls & Long Puts (`BUY_CALL`, `BUY_PUT`) | Strict defined-risk profiles with maximum loss capped at premium paid |
| **Prohibited Actions** | Naked Selling / Short Options Writing | Hard-vetoed at the code layer before order dispatch |
| **Confidence Threshold** | `≥ 0.60` (60%) | Suppresses low-conviction signals and market chop |
| **Risk Management Brackets** | `-20%` Stop Loss / `+40%` Take Profit | Asymmetric 2:1 Reward-to-Risk ratio |

---

## 📁 Repository Structure

```
alpaca-options-agent/
├── .env                  # API keys and endpoint configurations
├── requirements.txt      # Project dependencies (alpaca-py, requests, pandas, etc.)
├── risk_governor.py      # Deterministic code veto layer enforcing sizing & safety
├── brain.py              # Technical indicator engine & Featherless AI inference
├── agent.py              # End-to-end execution orchestrator & CLI runner
└── README.md             # Project overview, architecture, and documentation
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Alpaca Paper Trading Account
- Featherless AI API Access

### 2. Environment Setup
```bash
# Navigate to the project directory
cd /Users/kingleo/.gemini/antigravity/scratch/alpaca-options-agent

# Create Python virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration (`.env`)
Ensure your `.env` contains the required keys:
```ini
ALPACA_API_KEY=PKE6DDMT64HXPPTR7FOQAXHVVK
ALPACA_SECRET_KEY=EwiSz9QYmwZe5DJV7QTP9RDAzofcoEc9RiFgqqDfEU95
ALPACA_BASE_URL=https://paper-api.alpaca.markets
FEATHERLESS_API_KEY=rc_ce5ecf6146ce06cd8296372002840bfef12ab00e3643b185333836e763ec6524
FEATHERLESS_BASE_URL=https://api.featherless.ai/v1
FEATHERLESS_MODEL=zai-org/GLM-5.2
```

---

## 💻 CLI Usage

### Sanity Check (Verify Alpaca Account & $100k Balance)
```bash
python agent.py --sanity-check
```

### Test Featherless AI Inference Brain
```bash
python agent.py --test-brain
```

### Full Dry-Run Cycle (Market Data → AI Thesis → Risk Veto Check)
```bash
python agent.py --dry-run
```

### Live Paper Order Execution
```bash
python agent.py --execute
```

---

## 📊 Sample AI Output Schema

```json
{
  "action": "BUY_CALL",
  "rationale": "SPY has broken above the 9 EMA with a bullish MACD histogram expansion (+0.14) and healthy RSI momentum at 58.4 indicating upward continuation toward resistance.",
  "confidence": 0.78
}
```
