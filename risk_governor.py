"""
risk_governor.py - Deterministic Safety & Risk Enforcement Layer

Enforces non-negotiable risk limits before any trade execution can occur:
1. Maximum 5% portfolio allocation per trade (capped at $5,000 hard ceiling).
2. Maximum 2 concurrent open positions across the portfolio.
3. Defined-Risk ONLY: Whitelist for Long SPY Call / Long SPY Put. Strictly blocks naked option writing/selling.
4. Risk Management: 20% Stop-Loss and 40% Take-Profit calculation and validation.
5. Minimum Confidence Threshold: 0.60.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RiskGovernor")


@dataclass
class TradeProposal:
    action: str               # "BUY_CALL", "BUY_PUT", or "HOLD"
    underlying: str           # "SPY"
    rationale: str
    confidence: float
    contract_symbol: Optional[str] = None
    estimated_contract_price: Optional[float] = None
    target_contracts: int = 1


@dataclass
class RiskVerdict:
    approved: bool
    action: str
    allocated_capital: float
    max_contracts: int
    stop_loss_pct: float = 0.20       # 20% Stop Loss
    take_profit_pct: float = 0.40      # 40% Take Profit
    veto_reasons: Optional[List[str]] = None

    def __str__(self) -> str:
        if self.approved:
            return (
                f"✅ APPROVED: Action={self.action}, Allocated=${self.allocated_capital:.2f}, "
                f"Contracts={self.max_contracts}, SL={self.stop_loss_pct*100:.0f}%, TP={self.take_profit_pct*100:.0f}%"
            )
        return f"❌ VETOED: Action={self.action}, Reasons={', '.join(self.veto_reasons or [])}"


class RiskGovernor:
    # Hard constraints
    MAX_PORTFOLIO_ALLOCATION_PCT: float = 0.05   # 5% max equity per trade
    HARD_CAPITAL_CEILING: float = 5000.0        # $5,000 max per trade
    MAX_CONCURRENT_POSITIONS: int = 2           # Max 2 concurrent positions
    MIN_CONFIDENCE_THRESHOLD: float = 0.60       # Minimum AI confidence required
    STOP_LOSS_PCT: float = 0.20                 # 20% Stop Loss
    TAKE_PROFIT_PCT: float = 0.40               # 40% Take Profit
    ALLOWED_ACTIONS: set = {"BUY_CALL", "BUY_PUT"}
    ALLOWED_UNDERLYING: str = "SPY"

    def __init__(
        self,
        max_allocation_pct: float = MAX_PORTFOLIO_ALLOCATION_PCT,
        hard_capital_ceiling: float = HARD_CAPITAL_CEILING,
        max_concurrent_positions: int = MAX_CONCURRENT_POSITIONS,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
    ):
        self.max_allocation_pct = max_allocation_pct
        self.hard_capital_ceiling = hard_capital_ceiling
        self.max_concurrent_positions = max_concurrent_positions
        self.min_confidence = min_confidence

    def evaluate(
        self,
        proposal: TradeProposal,
        portfolio_equity: float,
        current_positions: List[Any],
        contract_premium: Optional[float] = None,
    ) -> RiskVerdict:
        """
        Deterministically evaluates a trade proposal against strict risk parameters.
        Returns a RiskVerdict with approval status, capital allocation, and sizing.
        """
        veto_reasons: List[str] = []

        logger.info("🛡️ Evaluating Trade Proposal against Risk Governor...")
        logger.info(f"   Proposal Action: {proposal.action} | Confidence: {proposal.confidence:.2f}")
        logger.info(f"   Portfolio Equity: ${portfolio_equity:,.2f} | Open Positions: {len(current_positions)}")

        # 1. Check for HOLD action
        if proposal.action == "HOLD":
            return RiskVerdict(
                approved=False,
                action="HOLD",
                allocated_capital=0.0,
                max_contracts=0,
                veto_reasons=["Action is HOLD. No order needed."]
            )

        # 2. Strict Defined-Risk Whitelist: Only Long SPY Calls or Puts
        if proposal.action not in self.ALLOWED_ACTIONS:
            veto_reasons.append(
                f"Prohibited action '{proposal.action}'. Only defined-risk purchases ({', '.join(self.ALLOWED_ACTIONS)}) are allowed. Naked selling is strictly blocked."
            )

        if proposal.underlying.upper() != self.ALLOWED_UNDERLYING:
            veto_reasons.append(
                f"Unauthorized ticker '{proposal.underlying}'. Only {self.ALLOWED_UNDERLYING} is whitelisted."
            )

        # 3. Minimum Confidence Check
        if proposal.confidence < self.min_confidence:
            veto_reasons.append(
                f"Confidence {proposal.confidence:.2f} is below minimum required threshold {self.min_confidence:.2f}."
            )

        # 4. Max Concurrent Positions Check
        if len(current_positions) >= self.max_concurrent_positions:
            veto_reasons.append(
                f"Maximum concurrent positions ({self.max_concurrent_positions}) reached. Currently holding {len(current_positions)} positions."
            )

        # 5. Position Sizing & Capital Allocation
        # 5% of portfolio equity or $5,000 hard ceiling, whichever is lower
        calculated_allocation = portfolio_equity * self.max_allocation_pct
        max_allowed_capital = min(calculated_allocation, self.hard_capital_ceiling)

        if portfolio_equity <= 0:
            veto_reasons.append(f"Insufficient portfolio equity (${portfolio_equity:,.2f}).")

        # 6. Calculate Max Contract Quantity if premium is known
        max_contracts = 0
        allocated_capital = 0.0

        if contract_premium and contract_premium > 0:
            # 1 standard options contract = 100 shares
            contract_cost = contract_premium * 100.0
            if contract_cost > max_allowed_capital:
                veto_reasons.append(
                    f"Single contract cost (${contract_cost:.2f}) exceeds maximum allowed trade allocation (${max_allowed_capital:.2f})."
                )
            else:
                max_contracts = int(max_allowed_capital // contract_cost)
                if max_contracts < 1:
                    veto_reasons.append("Calculated contract quantity is 0 based on capital allocation limits.")
                else:
                    allocated_capital = max_contracts * contract_cost
        else:
            # Sizing without exact contract premium yet (pre-selection phase)
            allocated_capital = max_allowed_capital
            max_contracts = 1

        # Verdict compilation
        if veto_reasons:
            logger.warning(f"🛡️ [VETO TRIGGERED] Proposal rejected by Risk Governor:")
            for reason in veto_reasons:
                logger.warning(f"   -> {reason}")
            return RiskVerdict(
                approved=False,
                action=proposal.action,
                allocated_capital=0.0,
                max_contracts=0,
                stop_loss_pct=self.STOP_LOSS_PCT,
                take_profit_pct=self.TAKE_PROFIT_PCT,
                veto_reasons=veto_reasons,
            )

        logger.info(f"🛡️ [RISK CLEARED] Proposal approved: {proposal.action} | Max Allocation: ${allocated_capital:.2f} | Contracts: {max_contracts}")
        return RiskVerdict(
            approved=True,
            action=proposal.action,
            allocated_capital=allocated_capital,
            max_contracts=max_contracts,
            stop_loss_pct=self.STOP_LOSS_PCT,
            take_profit_pct=self.TAKE_PROFIT_PCT,
            veto_reasons=None,
        )

    def calculate_exit_targets(self, entry_price: float) -> Dict[str, float]:
        """
        Calculates exact exit price targets for 20% Stop-Loss and 40% Take-Profit.
        """
        return {
            "entry_price": entry_price,
            "stop_loss_price": round(entry_price * (1.0 - self.STOP_LOSS_PCT), 2),
            "take_profit_price": round(entry_price * (1.0 + self.TAKE_PROFIT_PCT), 2),
            "stop_loss_pct": self.STOP_LOSS_PCT,
            "take_profit_pct": self.TAKE_PROFIT_PCT,
        }
