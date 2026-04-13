# metrics/self_report.py

from pathlib import Path
from datetime import datetime
import csv


class DailyAIReport:
    """
    Generates a daily self-evaluation report for the AI.
    """

    HEADERS = [
        "date",
        "symbol",
        "trades",
        "wins",
        "losses",
        "win_rate",
        "net_pnl",
        "max_drawdown",
        "notes",
    ]

    def __init__(self, path: str = "data_outputs/ai_daily_report.csv"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            with self.path.open("w", newline="") as f:
                csv.writer(f).writerow(self.HEADERS)

    def write(
        self,
        symbol: str,
        trades: int,
        wins: int,
        losses: int,
        net_pnl: float,
        max_dd: float,
        notes: str = "",
    ):
        win_rate = wins / trades if trades > 0 else 0.0

        with self.path.open("a", newline="") as f:
            csv.writer(f).writerow([
                datetime.utcnow().date().isoformat(),
                symbol,
                trades,
                wins,
                losses,
                round(win_rate, 3),
                round(net_pnl, 4),
                round(max_dd, 4),
                notes,
            ])