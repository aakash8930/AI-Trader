# execution/universe_manager.py

import time
from typing import List

from execution.coin_selector import CoinSelector


class UniverseManager:
    """
    Manages the tradable symbol universe autonomously.

    Key behavior:
    - If selector finds no valid long-ready symbols, the universe goes flat.
    - No fallback to weak symbols during bad market conditions.
    - Switches symbols only when the new candidate set is meaningfully better.
    - Tracks per-symbol ADX failure count to avoid selecting symbols that
      repeatedly fail the execution min_adx gate.
    """

    def __init__(
        self,
        all_symbols: List[str],
        timeframe: str,
        max_active: int,
        refresh_minutes: int = 60,
        selector_top_k_multiplier: int = 2,
        selector_min_atr_pct: float = 0.001,
        selector_soft_min_volume_ratio: float = 0.15,
        selector_rsi_long_min: float = 40.0,
        selector_rsi_long_max: float = 75.0,
        min_symbol_switch_gap: float = 0.03,
        exchange_name: str = "binance",
        exchange_fallbacks: List[str] | None = None,
        exchange_timeout_ms: int = 20000,
    ):
        self.all_symbols = all_symbols
        self.timeframe = timeframe
        self.max_active = max_active
        self.refresh_seconds = refresh_minutes * 60
        self.last_refresh = 0.0

        self.active_symbols: List[str] = []
        self.active_scores: dict[str, float] = {}
        self.min_symbol_switch_gap = min_symbol_switch_gap

        # Per-symbol consecutive ADX failure counter — prevents selecting symbols
        # that pass CoinSelector but repeatedly fail the execution min_adx gate.
        self._adx_fail_count: dict[str, int] = {}
        self._adx_fail_max = 3   # remove from universe after N consecutive ADX fails
        self._adx_fail_cooldown_secs = 1800  # 30 min blackout after ADX blacklist

        # Timestamps when a symbol was ADX-blacklisted
        self._adx_blacklist: dict[str, float] = {}

        self.selector = CoinSelector(
            timeframe=timeframe,
            top_k=max_active * selector_top_k_multiplier,
            min_atr_pct=selector_min_atr_pct,
            soft_min_volume_ratio=selector_soft_min_volume_ratio,
            rsi_long_min=selector_rsi_long_min,
            rsi_long_max=selector_rsi_long_max,
            exchange_name=exchange_name,
            exchange_fallbacks=exchange_fallbacks,
            exchange_timeout_ms=exchange_timeout_ms,
        )

    def _scores_for_symbols(self, symbols: List[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for symbol in symbols:
            score = self.selector._score_symbol(symbol)
            if score is not None:
                scores[symbol] = score
        return scores

    def refresh_if_needed(self) -> List[str]:
        now = time.time()

        # Do not refresh too often
        if now - self.last_refresh < self.refresh_seconds:
            return self.active_symbols

        self.last_refresh = now

        ranked = self.selector.select(self.all_symbols)
        candidate_symbols = ranked[: self.max_active]

        # If selector finds nothing valid, go flat
        if not candidate_symbols:
            print("[Universe] selector found no valid symbols → going flat")
            self.active_symbols = []
            self.active_scores = {}
            self._adx_fail_count.clear()
            return self.active_symbols

        candidate_scores = self._scores_for_symbols(candidate_symbols)

        # If candidate symbols cannot be scored, also go flat
        if not candidate_scores:
            print("[Universe] candidate symbols could not be scored → going flat")
            self.active_symbols = []
            self.active_scores = {}
            self._adx_fail_count.clear()
            return self.active_symbols

        # Filter out blacklisted ADX symbols (check cooldown)
        cleaned_candidates = []
        for s in candidate_symbols:
            if s in self._adx_blacklist:
                if now - self._adx_blacklist[s] < self._adx_fail_cooldown_secs:
                    # Still in cooldown — skip this symbol this cycle
                    continue
                else:
                    # Cooldown expired — remove from blacklist, reset counter
                    del self._adx_blacklist[s]
                    self._adx_fail_count.pop(s, None)
            cleaned_candidates.append(s)
        candidate_symbols = cleaned_candidates

        # Re-evaluate if we still have candidates after blacklist filter
        if not candidate_symbols:
            print("[Universe] all candidates blocked by ADX blacklist → going flat")
            self.active_symbols = []
            self.active_scores = {}
            return self.active_symbols

        # First-time activation
        if not self.active_symbols:
            self.active_symbols = candidate_symbols
            self.active_scores = candidate_scores
            print(f"🔄 Universe updated → {self.active_symbols}")
            return self.active_symbols

        current_scores = self._scores_for_symbols(self.active_symbols)
        current_total = sum(current_scores.get(s, 0.0) for s in self.active_symbols)
        candidate_total = sum(candidate_scores.get(s, 0.0) for s in candidate_symbols)

        current_bad = (
            not current_scores
            or any(score <= -900 for score in current_scores.values())
        )
        current_weak = current_total <= 0.15

        should_switch = (
            current_bad
            or current_weak
            or candidate_total >= current_total + self.min_symbol_switch_gap
        )

        if should_switch:
            if candidate_symbols != self.active_symbols:
                print(
                    f"🔄 Universe updated → {candidate_symbols} "
                    f"(old_score={current_total:.3f}, new_score={candidate_total:.3f})"
                )
            self.active_symbols = candidate_symbols
            self.active_scores = candidate_scores
        else:
            print(
                f"[Universe] keeping current symbols {self.active_symbols} "
                f"(old_score={current_total:.3f}, new_score={candidate_total:.3f})"
            )
            self.active_scores = current_scores

        return self.active_symbols

    def register_adx_fail(self, symbol: str) -> None:
        """
        Called by the runner/multirunner when a symbol fails the min_adx gate.
        After _adx_fail_max consecutive failures, the symbol is blacklisted
        from the universe for _adx_fail_cooldown_secs seconds.
        """
        if symbol not in self.active_symbols:
            return
        self._adx_fail_count[symbol] = self._adx_fail_count.get(symbol, 0) + 1
        count = self._adx_fail_count[symbol]
        if count >= self._adx_fail_max:
            self._adx_blacklist[symbol] = time.time()
            print(
                f"[Universe] {symbol} ADX-blacklisted for {self._adx_fail_cooldown_secs // 60}min "
                f"after {count} consecutive adx_low failures"
            )