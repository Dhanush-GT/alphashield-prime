# AlphaShield AI: Dual-Veto Autonomous Options Trading Agent
**Lablab.ai × Alpaca AI Trading Agents Hackathon**  
**Paper Account ID:** `PA3CMCT5LP09` | **Starting Capital:** `$100,000.00`

---

## 🏛️ 1. System Architecture: The "Dual-Veto" Philosophy
Pure LLM trading systems fail in live markets due to hallucinations, unconstrained position sizing, and emotional overtrading. Traditional algorithmic bots, conversely, cannot adapt to shifting macro volatility regimes.

AlphaShield AI resolves this dilemma through a strict **separation of intelligence and execution**:

```
               ┌────────────────────────────────────────────────────────┐
               │              Alpaca Market Data Stream                 │
               │         (SPY 15-Min Bars, RSI, MACD, Quotes)           │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │           Layer 1: Cognitive Brain (LLM)               │
               │   Featherless AI (OpenAI-compatible / zai-org/GLM-5.2) │
               │   • Momentum & Divergence Analysis                     │
               │   • Outputs Strict JSON: Action, Rationale, Confidence │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           │ [Trade Proposal]
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │        Layer 2: Deterministic Risk Governor            │
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
               │           Layer 3: Execution Broker (Alpaca CLI)       │
               │             Alpaca CLI Subprocess Wrapper              │
               │   • Active Option Contract Search (OTM / Nearest DTE)  │
               │   • Bracket & Market Order Dispatch via CLI            │
               │   • 15-Minute Market-Hours Cron Scheduler Loop         │
               └────────────────────────────────────────────────────────┘
```

1. **Cognitive Brain (Featherless AI):** Synthesizes technical momentum (15-min SPY RSI-14 and MACD histogram trends) into structured directional theses using open-source serverless inference (`zai-org/GLM-5.2`).
2. **Deterministic Risk Governor (Python):** An independent algorithmic veto layer that evaluates the AI's proposal against hard mathematical risk constraints before any order can touch the broker.
3. **Execution Broker (Alpaca CLI Subprocess):** Direct options contract resolution, submission, bracket execution (SL/TP), and state tracking via Alpaca CLI subprocess commands (`alpaca account get`, `alpaca data bars`, `alpaca option contracts`, `alpaca order submit`).

---

## 🔄 2. Decision Logic & Signal Flow

1. **Market Ingestion:** Every cycle, [`agent.py`](file:///Users/kingleo/.gemini/antigravity/scratch/alpaca-options-agent/agent.py) pulls recent SPY 15-minute historical bars via the Alpaca Market Data API.
2. **Indicator Synthesis:** The agent calculates RSI momentum (14-period) and MACD signal differentials (12, 26, 9).
3. **Structured Prompting:** Data is formatted into an OpenAI-compatible payload sent to Featherless AI. The LLM must output strict JSON:
   ```json
   {
     "action": "BUY_CALL" | "BUY_PUT" | "HOLD",
     "rationale": "...",
     "confidence": 0.0 - 1.0
   }
   ```
4. **Governor Veto Evaluation:** If the LLM proposes an action:
   - Evaluates portfolio buying power and restricts order size to $\le 5\%$ (\$5,000 max).
   - Verifies that total active open positions do not exceed 2.
   - Rejects any naked writing or complex multi-leg margin traps; permits **ONLY** defined-risk long Call or long Put purchases.
   - Attaches strict bracket targets: **20% Stop-Loss** and **40% Take-Profit**.
5. **Contract Resolution & Execution:** Resolves the nearest active Out-Of-The-Money (OTM) or near-the-money contract matching the expiration window and executes via Alpaca Paper API.

---

## 🛡️ 3. Risk Controls & Safety Bounds

| Rule | Parameter | Purpose |
|---|---|---|
| **Capital Preservation** | `5%` of equity (Hard cap: `$5,000`) | Eliminates single-trade catastrophic drawdown risk |
| **Max Concurrent Positions** | `2` positions | Enforces portfolio diversification and prevents over-leveraging |
| **Strategy Constraint** | Long Calls & Long Puts (`BUY_CALL`, `BUY_PUT`) | Strict defined-risk profiles with maximum loss capped at premium paid |
| **Prohibited Actions** | Naked Selling / Short Options Writing | Hard-vetoed at the code layer before order dispatch |
| **Confidence Threshold** | `≥ 0.60` (60%) | Suppresses low-conviction signals and market chop |
| **Risk Management Brackets** | `-20%` Stop Loss / `+40%` Take Profit | Asymmetric 2:1 Reward-to-Risk ratio |
| **Fail-Safe Circuit Breaker** | Fallback to `HOLD` | On API timeout, rate limit, or invalid JSON, agent safely defaults to `HOLD` |
| **Auditability** | Complete JSON logging | Every decision—including vetoed trades—is logged with timestamps & rationales |

---

## 📁 Repository Structure

```
alpaca-options-agent/
├── .env.example          # Environment variable template
├── .gitignore            # Protects credentials and local caches (.env, .venv)
├── requirements.txt      # Project dependencies (alpaca-py, requests, pandas)
├── risk_governor.py      # Deterministic code veto layer enforcing sizing & safety
├── brain.py              # Technical indicator engine & Featherless AI inference
├── agent.py              # End-to-end execution orchestrator & CLI runner
├── test_risk_governor.py # Unit tests for safety constraints & veto checks
└── README.md             # Project architecture & documentation
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+ (or Python 3.9+)
- Alpaca Paper Trading Account
- Featherless AI API Access

### 2. Environment Setup
```bash
# Clone and navigate to repository
cd alpaca-options-agent

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration (`.env`)
Copy `.env.example` to `.env` and insert your credentials:
```bash
cp .env.example .env
```

```ini
ALPACA_API_KEY=PKE6DDMT64HXPPTR7FOQAXHVVK
ALPACA_SECRET_KEY=EwiSz9QYmwZe5DJV7QTP9RDAzofcoEc9RiFgqqDfEU95
ALPACA_BASE_URL=https://paper-api.alpaca.markets
FEATHERLESS_API_KEY=rc_ce5ecf6146ce06cd8296372002840bfef12ab00e3643b185333836e763ec6524
FEATHERLESS_BASE_URL=https://api.featherless.ai/v1
FEATHERLESS_MODEL=zai-org/GLM-5.2
```

---

## 💻 CLI Usage Guide

### Sanity Check (Alpaca Account & Balance Verification)
```bash
python agent.py --sanity-check
```

### Test Featherless AI Inference Brain
```bash
python agent.py --test-brain
```

### Full Dry-Run Cycle (Market Data → AI Thesis → Risk Governor Veto Gate)
```bash
python agent.py --dry-run
```

### Live Paper Order Execution
```bash
python agent.py --execute
```

### Run Safety Unit Tests
```bash
python test_risk_governor.py
```
