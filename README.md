# AlphaShield AI: Autonomous Options Alpha Quant Terminal
**Lablab.ai × Alpaca AI Trading Agents Hackathon**  
**Paper Account ID:** `PA3CMCT5LP09` | **Starting Capital:** `$100,000.00`

---

## 🏛️ 1. System Architecture: The "Dual-Veto" Philosophy
Pure LLM trading systems fail in live markets due to hallucinations, unconstrained position sizing, and emotional overtrading. Traditional algorithmic bots, conversely, cannot adapt to shifting volatility regimes.

AlphaShield AI resolves this through a strict **separation of cognitive intelligence and deterministic risk execution**:

```
               ┌────────────────────────────────────────────────────────┐
               │           Alpaca Market Data & Options CLI             │
               │   (SPY 15-Min Bars, RSI, MACD, Option Contracts Chain) │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │           Layer 1: Cognitive Brain (LLM)               │
               │   Featherless AI (OpenAI-compatible / zai-org/GLM-5.2) │
               │   • Momentum, Divergence & Dynamic Strike Analysis     │
               │   • Targets specific SPY Call/Put Contract Symbols     │
               │   • Strict JSON: action, contract_symbol, conf, reason │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           │ [Trade Proposal]
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │        Layer 2: Deterministic Risk Governor            │
               │                     (VETO GATE)                        │
               │   • 5% Max Portfolio Allocation ($5,000 Hard Ceiling)  │
               │   • Max 2 Concurrent Open Options Positions            │
               │   • Defined-Risk Whitelist (Long SPY Calls/Puts ONLY)   │
               │   • Naked Short Selling / Writing Hard Block           │
               │   • Mathematical Brackets (-20% SL / +40% TP Targets)  │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           │ [Approved Sizing & Contract]
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │        Layer 3: Execution Broker (Alpaca CLI)          │
               │             Alpaca CLI Subprocess Wrapper              │
               │   • Queries Active Options (`alpaca option contracts`) │
               │   • Submits Market & Bracket Protection Orders         │
               │   • 15-Minute Market-Hours Background Cron Loop        │
               └────────────────────────────────────────────────────────┘
```

---

## 🛡️ 2. Risk Controls & Safety Bounds

| Rule | Parameter | Purpose |
|---|---|---|
| **Capital Preservation** | `5%` of equity (Hard cap: `$5,000`) | Eliminates single-trade catastrophic drawdown risk |
| **Max Concurrent Positions** | `2` positions max | Enforces portfolio diversification and prevents over-leveraging |
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
├── .env                  # Environment variables & API credentials
├── .gitignore            # Git ignore configuration
├── requirements.txt      # Project dependencies (streamlit, plotly, requests, pandas, schedule)
├── alpaca_cli.py         # Subprocess CLI Wrapper for Alpaca Commands
├── risk_governor.py      # Deterministic code veto layer enforcing sizing & safety
├── brain.py              # Technical indicator engine, option candidate selector & Featherless AI
├── agent.py              # End-to-end execution orchestrator & 15-minute cron runner
├── app.py                # High-end Quant Terminal Streamlit UI
├── test_risk_governor.py # Unit tests for safety constraints & veto checks
├── test_brain.py         # Unit tests for options brain, indicators & candidate generation
└── test_agent.py         # Unit & mock integration tests for agent orchestrator
```

---

## 💻 CLI Usage Guide

### Sanity Check (Alpaca Account & Balance Verification via CLI)
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

### Live Paper Order Execution Cycle
```bash
python agent.py --execute
```

### Run 15-Minute Background Cron Loop
```bash
python agent.py --cron --interval 15
```

### Launch High-End Quant Terminal Streamlit Dashboard
```bash
streamlit run app.py --server.port 8501
```

### Run Complete Test Suite
```bash
python -m unittest discover -v
```
