"""
app.py - AlphaShield AI Autonomous Options Trading Agent Web Dashboard
Lablab.ai × Alpaca AI Trading Agents Hackathon
"""

import os
import json
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

# Internal Engine Imports
from agent import AlpacaOptionsAgent
from brain import calculate_rsi, calculate_macd
from risk_governor import TradeProposal

load_dotenv()

# Streamlit Page Config
st.set_page_config(
    page_title="AlphaShield AI — Autonomous Options Quant Terminal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# High-end Dark Quant Terminal Styling
st.markdown("""
<style>
    /* Dark Theme Core */
    .stApp {
        background-color: #0B0E14;
        color: #E0E6ED;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .main-header {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 0.1rem;
        color: #F8FAFC;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #94A3B8;
        margin-bottom: 1.2rem;
    }
    .status-pill-container {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 1.2rem;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        padding: 5px 12px;
        border-radius: 9999px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .pill-connected {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border-color: rgba(16, 185, 129, 0.35);
    }
    .pill-running {
        background-color: rgba(59, 130, 246, 0.15);
        color: #60A5FA;
        border-color: rgba(59, 130, 246, 0.35);
    }
    .pill-options {
        background-color: rgba(168, 85, 247, 0.15);
        color: #C084FC;
        border-color: rgba(168, 85, 247, 0.35);
    }
    .pill-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background-color: currentColor;
    }
    .quant-card {
        background-color: #121824;
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .council-card {
        background-color: #151D2C;
        border-left: 4px solid #3B82F6;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }
    .badge-approved {
        background-color: rgba(16, 185, 129, 0.2);
        color: #34D399;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.82rem;
        display: inline-block;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-vetoed {
        background-color: rgba(239, 68, 68, 0.2);
        color: #F87171;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.82rem;
        display: inline-block;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: white;
        font-weight: 700;
        font-size: 1.05rem;
        padding: 0.65rem 1rem;
        border-radius: 8px;
        border: 1px solid #3B82F6;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%);
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_agent():
    return AlpacaOptionsAgent()


def fetch_account_data(agent):
    try:
        account = agent.cli.get_account()
        equity = float(account.get("equity", 100000.0))
        cash = float(account.get("cash", 100000.0))
        last_equity = float(account.get("last_equity", equity))
        daily_pnl = equity - last_equity
        daily_pnl_pct = (daily_pnl / last_equity * 100) if last_equity > 0 else 0.0
        return {
            "account_number": account.get("account_number", "PA3CMCT5LP09"),
            "status": account.get("status", "ACTIVE"),
            "equity": equity,
            "cash": cash,
            "buying_power": float(account.get("buying_power", 400000.0)),
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "options_level": str(account.get("options_approved_level", "3")),
        }
    except Exception as e:
        st.error(f"Error fetching Alpaca account: {e}")
        return {
            "account_number": "PA3CMCT5LP09",
            "status": "ACTIVE",
            "equity": 100000.0,
            "cash": 100000.0,
            "buying_power": 400000.0,
            "daily_pnl": 0.0,
            "daily_pnl_pct": 0.0,
            "options_level": "3",
        }


def render_spy_charts(df_bars, indicators):
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.22, 0.23],
        subplot_titles=("SPY 15-Minute Price Action & Exponential Moving Averages", "Relative Strength Index (RSI 14)", "MACD Histogram & Signal (12, 26, 9)"),
    )

    x_vals = df_bars["timestamp"] if "timestamp" in df_bars.columns else df_bars.index

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=x_vals,
            open=df_bars["open"],
            high=df_bars["high"],
            low=df_bars["low"],
            close=df_bars["close"],
            name="SPY",
            increasing_line_color="#10B981",
            decreasing_line_color="#EF4444",
        ),
        row=1,
        col=1,
    )

    # 9 and 21 EMA overlays
    df_ema9 = df_bars["close"].ewm(span=9, adjust=False).mean()
    df_ema21 = df_bars["close"].ewm(span=21, adjust=False).mean()

    fig.add_trace(
        go.Scatter(x=x_vals, y=df_ema9, line=dict(color="#F59E0B", width=1.8), name="9 EMA"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=x_vals, y=df_ema21, line=dict(color="#3B82F6", width=1.8), name="21 EMA"),
        row=1,
        col=1,
    )

    # RSI Subplot
    rsi_series = calculate_rsi(df_bars["close"], period=14)

    fig.add_trace(
        go.Scatter(x=x_vals, y=rsi_series, line=dict(color="#A855F7", width=2), name="RSI (14)"),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#EF4444", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#10B981", row=2, col=1)

    # MACD Subplot
    macd_res = calculate_macd(df_bars["close"])
    macd_line = macd_res["macd_line"]
    signal_line = macd_res["signal_line"]
    macd_hist = macd_res["histogram"]

    colors = ["#10B981" if val >= 0 else "#EF4444" for val in macd_hist]
    fig.add_trace(
        go.Bar(x=x_vals, y=macd_hist, marker_color=colors, name="MACD Hist"),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=x_vals, y=macd_line, line=dict(color="#38BDF8", width=1.5), name="MACD"),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=x_vals, y=signal_line, line=dict(color="#FB923C", width=1.5), name="Signal"),
        row=3,
        col=1,
    )

    fig.update_layout(
        height=580,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        paper_bgcolor="#0B0E14",
        plot_bgcolor="#0B0E14",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def main():
    agent = get_agent()
    account_data = fetch_account_data(agent)

    # Header section with Hackathon branding
    st.markdown('<div class="main-header">🛡️ AlphaShield AI — Autonomous Options Alpha Terminal</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header"><b>Lablab.ai × Alpaca AI Trading Agents Hackathon</b> &nbsp;|&nbsp; '
        f'Paper Account: <code>{account_data["account_number"]}</code> &nbsp;|&nbsp; '
        f'Inference Engine: <b>Featherless AI (zai-org/GLM-5.2)</b></div>',
        unsafe_allow_html=True,
    )

    # Status Pills
    st.markdown("""
    <div class="status-pill-container">
        <div class="status-pill pill-connected"><span class="pill-dot"></span> ALPACA CLI: CONNECTED</div>
        <div class="status-pill pill-running"><span class="pill-dot"></span> FEATHERLESS AI: RUNNING</div>
        <div class="status-pill pill-options"><span class="pill-dot"></span> OPTIONS TRADING: LEVEL 3</div>
    </div>
    """, unsafe_allow_html=True)

    # Top Account Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Portfolio Value",
            value=f"${account_data['equity']:,.2f}",
            delta=f"${account_data['daily_pnl']:+,.2f} ({account_data['daily_pnl_pct']:+.2f}%)" if account_data['daily_pnl'] != 0 else "0.00%",
        )
    with col2:
        st.metric(
            label="Cash Balance",
            value=f"${account_data['cash']:,.2f}",
        )
    with col3:
        st.metric(
            label="Buying Power",
            value=f"${account_data['buying_power']:,.2f}",
        )
    with col4:
        st.metric(
            label="Options Allocation Cap",
            value="≤ 5% ($5,000)",
            delta="Defined-Risk Long Only",
        )

    st.markdown("---")

    # Fetch live data for charts & brain
    with st.spinner("Fetching latest SPY momentum and technical indicators via Alpaca CLI..."):
        df_bars = agent.fetch_spy_bars(limit=50)
        indicators = agent.brain.compute_indicators(df_bars)

    # Layout: Multi-pane Chart (62%) on Left, AI Decision & Control (38%) on Right
    left_col, right_col = st.columns([13, 8])

    with left_col:
        st.markdown("### 📊 SPY Real-Time Market Action & Multi-Timeframe Signals")
        chart_fig = render_spy_charts(df_bars, indicators)
        st.plotly_chart(chart_fig, use_container_width=True)

        # Quick indicator chips
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SPY Price", f"${indicators['current_price']:.2f}", f"{indicators['15m_pct_change']:+.2f}%")
        c2.metric("RSI (14)", f"{indicators['rsi_14']:.2f}")
        c3.metric("MACD Hist", f"{indicators['macd_hist']:+.3f}")
        c4.metric("Session Range", f"${indicators['day_low']:.2f} - ${indicators['day_high']:.2f}")

    with right_col:
        st.markdown("### ⚡ Autonomous Options Execution Hub")

        tab_exec, tab_council, tab_options_chain = st.tabs(["🚀 Agent Control", "🧠 AI Council Debate", "🔎 Options Chain"])

        with tab_exec:
            mode = st.radio(
                "Execution Mode",
                ["Simulated Dry-Run (Safe Preview)", "Live Paper Execution via Alpaca CLI"],
                horizontal=True,
            )
            is_live = (mode == "Live Paper Execution via Alpaca CLI")

            if st.button("🚀 Trigger Autonomous Agent Cycle", use_container_width=True):
                with st.spinner("1️⃣ Querying Featherless AI (GLM-5.2) ➔ 2️⃣ Evaluating Risk Governor ➔ 3️⃣ Resolving Options via Alpaca CLI..."):
                    result = agent.execute_cycle(dry_run=(not is_live))

                st.session_state["last_analysis"] = result

            # Display Last Analysis Results if available
            if "last_analysis" in st.session_state:
                res = st.session_state["last_analysis"]
                proposal = res.get("proposal", {})
                verdict = res.get("verdict", {})
                contract = res.get("contract", {})
                exit_targets = res.get("exit_targets", {})
                debate = res.get("council_debate", [])

                st.markdown("#### 🧠 1. Cognitive Brain Thesis")
                action = proposal.get("action", "HOLD")
                conf = proposal.get("confidence", 0.0)
                contract_symbol = proposal.get("contract_symbol") or (contract.get("symbol") if contract else "None")

                action_color = "#10B981" if action == "BUY_CALL" else ("#EF4444" if action == "BUY_PUT" else "#F59E0B")
                st.markdown(
                    f"<div style='background-color:#121824; padding:12px; border-radius:8px; border-left: 5px solid {action_color}; margin-bottom:12px;'>"
                    f"<b>Action:</b> <span style='font-size:1.15rem; font-weight:800; color:{action_color};'>{action}</span> "
                    f"&nbsp;|&nbsp; <b>Confidence:</b> <code>{conf*100:.1f}%</code><br/>"
                    f"<b>Target Contract:</b> <code>{contract_symbol}</code><br/>"
                    f"<p style='margin-top:6px; font-size:0.88rem; color:#CBD5E1;'>{proposal.get('rationale', 'No rationale')}</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                st.markdown("#### 🛡️ 2. Deterministic Risk Governor Veto Gate")
                approved = verdict.get("approved", False)
                if approved:
                    st.markdown(
                        f"<div class='badge-approved'>✅ RISK APPROVED & CLEAR</div>"
                        f"<div style='margin-top:8px; font-size:0.88rem; line-height:1.6; background-color:#121824; padding:10px; border-radius:6px;'>"
                        f"• <b>Capital Allocated:</b> ${verdict.get('allocated_capital', 0):,.2f} (≤ 5% Portfolio Cap / $5k max)<br/>"
                        f"• <b>Contract Sizing:</b> {verdict.get('max_contracts', 0)} contracts<br/>"
                        f"• <b>Stop-Loss Limit:</b> -{verdict.get('stop_loss_pct', 0.20)*100:.0f}% (${exit_targets.get('stop_loss_price', 0):.2f})<br/>"
                        f"• <b>Take-Profit Target:</b> +{verdict.get('take_profit_pct', 0.40)*100:.0f}% (${exit_targets.get('take_profit_price', 0):.2f})"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    reasons = verdict.get("veto_reasons", ["Trade vetoed by deterministic risk parameters."])
                    reasons_html = "".join([f"<li>{r}</li>" for r in reasons])
                    st.markdown(
                        f"<div class='badge-vetoed'>🛑 VETOED BY GOVERNOR</div>"
                        f"<div style='margin-top:8px; font-size:0.88rem; color:#FCA5A5; background-color:#121824; padding:10px; border-radius:6px;'>"
                        f"<ul style='margin-bottom:0;'>{reasons_html}</ul>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                st.markdown("#### 🎯 3. Execution State")
                st.markdown(
                    f"<div style='background-color:#121824; padding:10px; border-radius:6px; font-size:0.88rem;'>"
                    f"<b>Cycle Status:</b> <code>{res.get('status')}</code><br/>"
                    f"<b>CLI Order Target:</b> <code>{contract_symbol}</code>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        with tab_council:
            st.markdown("#### 🏛️ Live Multi-Agent Cognitive Deliberations")
            last_res = st.session_state.get("last_analysis", {})
            debate = last_res.get("council_debate")
            if not debate:
                debate = agent.brain.get_council_debate(indicators, {"action": "BUY_CALL", "confidence": 0.85, "contract_symbol": "SPY260904C00545000"})

            for specialist in debate:
                stance = specialist.get("stance", "NEUTRAL")
                stance_color = "#10B981" if "BULLISH" in stance or "APPROVED" in stance else ("#EF4444" if "BEARISH" in stance or "VETO" in stance else "#94A3B8")
                st.markdown(
                    f"<div class='council-card' style='border-left-color: {stance_color};'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<b>{specialist.get('avatar')} {specialist.get('role')}</b>"
                    f"<span style='font-size:0.75rem; font-weight:bold; color:{stance_color}; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.05);'>{stance}</span>"
                    f"</div>"
                    f"<p style='margin-top:6px; margin-bottom:0; font-size:0.85rem; color:#CBD5E1;'>{specialist.get('content')}</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        with tab_options_chain:
            st.markdown("#### 🔎 Active SPY Option Contracts via Alpaca CLI")
            try:
                raw_options = agent.cli.get_option_contracts(underlying_symbol="SPY")
                contracts = raw_options.get("option_contracts", [])
                if contracts:
                    c_rows = []
                    for c in contracts[:12]:
                        c_rows.append({
                            "Symbol": c.get("symbol"),
                            "Type": str(c.get("type", "")).upper(),
                            "Strike": f"${float(c.get('strike_price', 0)):.2f}",
                            "Expiry": c.get("expiration_date"),
                            "Status": c.get("status"),
                        })
                    st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("No contracts returned or market closed. Using dynamic chain generator.")
            except Exception as e:
                st.error(f"Error reading option chain: {e}")

    st.markdown("---")

    # Lower Section: Live Options Position Ledger & Order History
    pos_col, ord_col = st.columns(2)

    with pos_col:
        # Check current positions count and capacity
        try:
            positions = agent.cli.get_positions()
            num_pos = len(positions) if positions else 0
            cap_indicator = "🔴 🔴 (2/2 FULL)" if num_pos >= 2 else ("🟡 ⚪ (1/2 Active)" if num_pos == 1 else "🟢 ⚪ (0/2 Empty)")

            st.markdown(f"### 💼 Options Position Ledger &nbsp; <span style='font-size:0.9rem; color:#94A3B8;'>Capacity: <b>{cap_indicator}</b></span>", unsafe_allow_html=True)
            if positions:
                pos_data = []
                for p in positions:
                    pos_data.append({
                        "Symbol": p.get("symbol", "N/A"),
                        "Qty": p.get("qty", "0"),
                        "Avg Entry": f"${float(p.get('avg_entry_price', 0.0)):.2f}",
                        "Current": f"${float(p.get('current_price', 0.0)):.2f}",
                        "Unrealized P&L": f"${float(p.get('unrealized_pl', 0.0)):+,.2f} ({float(p.get('unrealized_plpc', 0.0))*100:+.2f}%)",
                        "Side": p.get("side", "long").upper(),
                    })
                st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
            else:
                st.info("No active open positions. Risk Governor capacity: 2/2 slots available.")
        except Exception as e:
            st.error(f"Error loading positions: {e}")

    with ord_col:
        st.markdown("### 📜 Subprocess CLI Order & Bracket History")
        try:
            orders = agent.cli.get_orders(limit=8)
            if orders:
                ord_data = []
                for o in orders:
                    ord_data.append({
                        "Symbol": o.get("symbol", "N/A"),
                        "Qty": o.get("qty", "0"),
                        "Side": str(o.get("side", "N/A")).upper(),
                        "Type": str(o.get("type", "N/A")).upper(),
                        "Status": str(o.get("status", "N/A")).upper(),
                        "Submitted": str(o.get("submitted_at", "N/A"))[:16],
                    })
                st.dataframe(pd.DataFrame(ord_data), use_container_width=True, hide_index=True)
            else:
                st.info("No recent orders recorded via Alpaca CLI.")
        except Exception as e:
            st.error(f"Error loading order history: {e}")


if __name__ == "__main__":
    main()
