"""
Circuit breaker to prevent runaway losses
"""


class CircuitBreaker:
    """Automatically pause trading on excessive drawdown"""

    def __init__(self, max_drawdown_pct: float = 0.03):
        """
        Args:
            max_drawdown_pct: Maximum drawdown before tripping (default 3%)
        """
        self.max_drawdown_pct = max_drawdown_pct
        self.peak_balance = None
        self.is_tripped = False
        self.trip_count = 0

    def check(self, current_balance: float) -> bool:
        """
        Check if trading should continue

        Returns:
            True if trading should continue, False if paused
        """
        # Initialize or update peak
        if self.peak_balance is None or current_balance > self.peak_balance:
            self.peak_balance = current_balance

            # Reset if we've recovered
            if self.is_tripped:
                self.is_tripped = False
                print("✅ Circuit breaker RESET - balance recovered")

            return True

        # Calculate current drawdown
        drawdown = (self.peak_balance - current_balance) / self.peak_balance

        # Check if threshold exceeded
        if drawdown >= self.max_drawdown_pct:
            if not self.is_tripped:
                self.trip_count += 1
                print(f"{'='*60}")
                print(f"🛑 CIRCUIT BREAKER TRIPPED #{self.trip_count}")
                print(f"{'='*60}")
                print(f"Peak Balance: ${self.peak_balance:.2f}")
                print(f"Current Balance: ${current_balance:.2f}")
                print(f"Drawdown: {drawdown*100:.2f}% (limit: {self.max_drawdown_pct*100:.2f}%)")
                print(f"Trading PAUSED - will retry in 1 hour")
                print(f"{'='*60}")
                self.is_tripped = True

            return False

        return True

    def manual_reset(self):
        """Manually reset the circuit breaker (use with caution)"""
        print("⚠️  Manual circuit breaker reset requested")
        self.is_tripped = False
        self.peak_balance = None
        print("✅ Circuit breaker manually reset - resuming trading")

    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            "is_tripped": self.is_tripped,
            "peak_balance": self.peak_balance,
            "trip_count": self.trip_count,
            "max_drawdown_pct": self.max_drawdown_pct,
        }
