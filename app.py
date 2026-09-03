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

# Alpaca & Internal Engine Imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

from agent import AlpacaOptionsAgent
from risk_governor import TradeProposal

load_dotenv()

# Streamlit Page Config
st.set_page_config(
    page_title="AlphaShield AI — Autonomous Options Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #888888;
        margin-bottom: 1.5rem;
    }
    .metric-container {
        background-color: #1E222D;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #2A2E39;
    }
    .badge-approved {
        background-color: #0E6251;
        color: #A3E4D7;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-vetoed {
        background-color: #78281F;
        color: #F5B7B1;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .stButton>button {
        width: 100%;
        background-color: #2E86C1;
        color: white;
        font-weight: bold;
        font-size: 1.1rem;
        padding: 0.6rem;
        border-radius: 8px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1B4F72;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_agent():
    return AlpacaOptionsAgent()


def fetch_account_data(agent):
    try:
        account = agent.trading_client.get_account()
        equity = float(account.equity)
        cash = float(account.cash)
        last_equity = float(account.last_equity)
        daily_pnl = equity - last_equity
        daily_pnl_pct = (daily_pnl / last_equity * 100) if last_equity > 0 else 0.0
        return {
            "account_number": account.account_number,
            "status": account.status,
            "equity": equity,
            "cash": cash,
            "buying_power": float(account.buying_power),
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "options_level": getattr(account, "options_approved_level", "3"),
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
        subplot_titles=("SPY 15-Minute Price Action & EMAs", "Relative Strength Index (RSI 14)", "MACD (12, 26, 9)"),
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
        ),
        row=1,
        col=1,
    )

    # 9 and 21 EMA overlays
    df_ema9 = df_bars["close"].ewm(span=9, adjust=False).mean()
    df_ema21 = df_bars["close"].ewm(span=21, adjust=False).mean()

    fig.add_trace(
        go.Scatter(x=x_vals, y=df_ema9, line=dict(color="#F39C12", width=1.5), name="9 EMA"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=x_vals, y=df_ema21, line=dict(color="#3498DB", width=1.5), name="21 EMA"),
        row=1,
        col=1,
    )

    # RSI Subplot
    df_rsi = df_bars["close"].diff()
    gain = df_rsi.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss = (-df_rsi.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    rs = gain / (loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))

    fig.add_trace(
        go.Scatter(x=x_vals, y=rsi_series, line=dict(color="#9B59B6", width=2), name="RSI (14)"),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#E74C3C", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#2ECC71", row=2, col=1)

    # MACD Subplot
    ema12 = df_bars["close"].ewm(span=12, adjust=False).mean()
    ema26 = df_bars["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    colors = ["#2ECC71" if val >= 0 else "#E74C3C" for val in macd_hist]
    fig.add_trace(
        go.Bar(x=x_vals, y=macd_hist, marker_color=colors, name="MACD Hist"),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=x_vals, y=macd_line, line=dict(color="#3498DB", width=1.5), name="MACD"),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=x_vals, y=signal_line, line=dict(color="#E67E22", width=1.5), name="Signal"),
        row=3,
        col=1,
    )

    fig.update_layout(
        height=580,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        paper_bgcolor="#11141C",
        plot_bgcolor="#11141C",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def main():
    agent = get_agent()
    account_data = fetch_account_data(agent)

    # Header section
    st.markdown('<div class="main-header">🛡️ AlphaShield AI — Autonomous Options Agent</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header"><b>Lablab.ai × Alpaca AI Hackathon</b> &nbsp;|&nbsp; '
        f'Paper Account: <code>{account_data["account_number"]}</code> &nbsp;|&nbsp; '
        f'Inference: <b>Featherless AI (zai-org/GLM-5.2)</b> &nbsp;|&nbsp; '
        f'Architecture: <b>Reason-Before-Execution Dual-Veto</b></div>',
        unsafe_allow_html=True,
    )

    # 3 Top Metric Cards
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
            label="Options Approval",
            value=f"Level {account_data['options_level']}",
            delta="Defined-Risk Only",
        )

    st.markdown("---")

    # Fetch live data for charts & brain
    with st.spinner("Fetching latest SPY momentum and technical indicators..."):
        df_bars = agent.fetch_spy_bars(limit=50)
        indicators = agent.brain.compute_indicators(df_bars)

    # Layout: Chart on Left (65%), Agent Control & Decision Panel on Right (35%)
    left_col, right_col = st.columns([13, 7])

    with left_col:
        st.markdown("### 📊 SPY Real-Time Market Action & Technical Signals")
        chart_fig = render_spy_charts(df_bars, indicators)
        st.plotly_chart(chart_fig, use_container_width=True)

        # Quick indicator chips
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SPY Price", f"${indicators['current_price']:.2f}", f"{indicators['15m_pct_change']:+.2f}%")
        c2.metric("RSI (14)", f"{indicators['rsi_14']:.2f}")
        c3.metric("MACD Hist", f"{indicators['macd_hist']:+.3f}")
        c4.metric("Session Range", f"${indicators['day_low']:.2f} - ${indicators['day_high']:.2f}")

    with right_col:
        st.markdown("### ⚡ Autonomous Dual-Veto Engine")
        
        mode = st.radio(
            "Execution Mode",
            ["Simulated Dry-Run (Safe Preview)", "Live Paper Execution"],
            horizontal=True,
        )
        is_live = (mode == "Live Paper Execution")

        if st.button("🚀 Run AI Agent Analysis", use_container_width=True):
            with st.spinner("1️⃣ Querying Featherless AI (GLM-5.2) ➔ 2️⃣ Evaluating Risk Governor..."):
                result = agent.execute_cycle(dry_run=(not is_live))

            st.session_state["last_analysis"] = result

        # Display Last Analysis Results if available
        if "last_analysis" in st.session_state:
            res = st.session_state["last_analysis"]
            proposal = res.get("proposal", {})
            verdict = res.get("verdict", {})
            contract = res.get("contract", {})
            exit_targets = res.get("exit_targets", {})

            st.markdown("#### 🧠 1. Cognitive Brain (Featherless AI)")
            action = proposal.get("action", "HOLD")
            conf = proposal.get("confidence", 0.0)
            
            action_color = "#2ECC71" if action == "BUY_CALL" else ("#E74C3C" if action == "BUY_PUT" else "#F39C12")
            st.markdown(
                f"<div style='background-color:#1E222D; padding:12px; border-radius:6px; border-left: 5px solid {action_color};'>"
                f"<b>Action Proposal:</b> <span style='font-size:1.2rem; font-weight:bold; color:{action_color};'>{action}</span> "
                f"&nbsp;|&nbsp; <b>Confidence:</b> <code>{conf*100:.1f}%</code><br/>"
                f"<p style='margin-top:8px; font-size:0.9rem;'>{proposal.get('rationale', 'No rationale')}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown("#### 🛡️ 2. Deterministic Risk Governor Veto")
            approved = verdict.get("approved", False)
            if approved:
                st.markdown(
                    f"<div class='badge-approved'>✅ RISK APPROVED</div>"
                    f"<div style='margin-top:8px; font-size:0.9rem;'>"
                    f"• <b>Max Capital Allocation:</b> ${verdict.get('allocated_capital', 0):,.2f} (≤ 5% of portfolio)<br/>"
                    f"• <b>Contract Sizing:</b> {verdict.get('max_contracts', 0)} contracts<br/>"
                    f"• <b>Stop-Loss Limit:</b> -{verdict.get('stop_loss_pct', 0.20)*100:.0f}%<br/>"
                    f"• <b>Take-Profit Target:</b> +{verdict.get('take_profit_pct', 0.40)*100:.0f}%"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                reasons = verdict.get("veto_reasons", ["Trade vetoed by safety constraints."])
                reasons_html = "".join([f"<li>{r}</li>" for r in reasons])
                st.markdown(
                    f"<div class='badge-vetoed'>🛑 VETOED BY GOVERNOR</div>"
                    f"<div style='margin-top:8px; font-size:0.9rem; color:#F5B7B1;'>"
                    f"<ul>{reasons_html}</ul>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("#### 🎯 3. Contract & Execution State")
            if contract:
                st.markdown(
                    f"<div style='background-color:#1E222D; padding:10px; border-radius:6px;'>"
                    f"<b>Contract:</b> <code>{contract.get('symbol')}</code><br/>"
                    f"<b>Strike:</b> ${contract.get('strike_price', 0):.2f} &nbsp;|&nbsp; "
                    f"<b>Expiry:</b> {contract.get('expiration_date')} &nbsp;|&nbsp; "
                    f"<b>Est. Premium:</b> ${contract.get('estimated_premium', 0):.2f}<br/>"
                    f"<b>Execution Status:</b> <code>{res.get('status')}</code>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info(f"Execution Status: {res.get('status')}")

    st.markdown("---")

    # Lower Section: Live Open Positions & Recent Orders
    pos_col, ord_col = st.columns(2)

    with pos_col:
        st.markdown("### 💼 Open Positions (Max 2 Permitted)")
        try:
            positions = agent.trading_client.get_all_positions()
            if positions:
                pos_data = []
                for p in positions:
                    pos_data.append({
                        "Symbol": p.symbol,
                        "Qty": p.qty,
                        "Avg Entry": f"${float(p.avg_entry_price):.2f}",
                        "Current Price": f"${float(p.current_price):.2f}",
                        "Unrealized P&L": f"${float(p.unrealized_pl):+,.2f} ({float(p.unrealized_plpc)*100:+.2f}%)",
                        "Side": p.side,
                    })
                st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
            else:
                st.info("No active open positions. Governor capacity: 2/2 available.")
        except Exception as e:
            st.error(f"Error loading positions: {e}")

    with ord_col:
        st.markdown("### 📜 Recent Order History")
        try:
            orders_req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=8)
            orders = agent.trading_client.get_orders(orders_req)
            if orders:
                ord_data = []
                for o in orders:
                    ord_data.append({
                        "Symbol": o.symbol,
                        "Qty": o.qty,
                        "Side": o.side.name if hasattr(o.side, "name") else str(o.side),
                        "Type": o.type.name if hasattr(o.type, "name") else str(o.type),
                        "Status": o.status.name if hasattr(o.status, "name") else str(o.status),
                        "Submitted At": o.submitted_at.strftime("%Y-%m-%d %H:%M") if o.submitted_at else "N/A",
                    })
                st.dataframe(pd.DataFrame(ord_data), use_container_width=True, hide_index=True)
            else:
                st.info("No recent orders recorded.")
        except Exception as e:
            st.error(f"Error loading order history: {e}")


if __name__ == "__main__":
    main()
