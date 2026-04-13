# execution/ai_supervisor.py

from collections import deque
from dataclasses import dataclass


@dataclass
class SupervisorDecision:
    risk_multiplier: float
    trade_allowed: bool
    reason: str


class AISupervisor:
    """
    Autonomous supervisor that adapts system behavior
    based on recent performance.
    """

    def __init__(
        self,
        window: int = 20,
        max_drawdown_pct: float = 0.03,
        min_win_rate: float = 0.40,
    ):
        self.window = window
        self.max_drawdown_pct = max_drawdown_pct
        self.min_win_rate = min_win_rate

        self.recent_pnls = deque(maxlen=window)
        self.peak_equity = None
        self.current_equity = None

    # ----------------------------------
    def update_equity(self, equity: float):
        self.current_equity = equity
        if self.peak_equity is None:
            self.peak_equity = equity
        else:
            self.peak_equity = max(self.peak_equity, equity)

    # ----------------------------------
    def register_trade(self, pnl: float):
        self.recent_pnls.append(pnl)

    # ----------------------------------
    def decide(self) -> SupervisorDecision:
        if not self.recent_pnls:
            return SupervisorDecision(1.0, True, "no-history")

        wins = sum(1 for p in self.recent_pnls if p > 0)
        win_rate = wins / len(self.recent_pnls)

        drawdown = (
            (self.peak_equity - self.current_equity) / self.peak_equity
            if self.peak_equity and self.current_equity
            else 0.0
        )

        # -------- HARD STOP --------
        if drawdown >= self.max_drawdown_pct:
            return SupervisorDecision(
                risk_multiplier=0.0,
                trade_allowed=False,
                reason="supervisor-drawdown",
            )

        # -------- ADAPTIVE RISK --------
        if win_rate < self.min_win_rate:
            return SupervisorDecision(
                risk_multiplier=0.5,
                trade_allowed=True,
                reason="low-win-rate",
            )

        if win_rate > 0.60:
            return SupervisorDecision(
                risk_multiplier=1.25,
                trade_allowed=True,
                reason="strong-performance",
            )

        return SupervisorDecision(1.0, True, "normal")