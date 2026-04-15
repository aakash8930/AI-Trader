# execution/universe_manager.py

import time
from typing import List

from execution.coin_selector import CoinSelector


class UniverseManager:
    """
    Manages the tradable symbol universe autonomously.

    Key behavior:
    - If selector finds no valid long-ready symbols, the universe goes flat.
    - Fallback mode activates after extended flat periods to find borderline symbols.
    - Switches symbols only when the new candidate set is meaningfully better.
    - Tracks per-symbol ADX failure count to avoid selecting symbols that
      repeatedly fail the execution min_adx gate.
    - Refreshes more frequently when flat to catch improving conditions.
    """

    def __init__(
        self,
        all_symbols: List[str],
        timeframe: str,
        max_active: int,
        refresh_minutes: int = 60,
        selector_top_k_multiplier: int = 2,
        selector_min_atr_pct: float = 0.0008,
        selector_soft_min_volume_ratio: float = 0.12,
        selector_min_adx: float = 17.0,
        selector_rsi_long_min: float = 38.0,
        selector_rsi_long_max: float = 70.0,  # Tighter than strategy (72.0) to avoid over-extended entries
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

        # Flat mode tracking - enables faster refresh and fallback logic
        self._flat_since: float = 0.0
        self._consecutive_flat_refreshes: int = 0
        self._fallback_mode: bool = False
        self._fallback_activates_after_refreshes: int = 2  # Reduced from 3 - activate fallback after 2hrs

        self.active_symbols: List[str] = []
        self.active_scores: dict[str, float] = {}
        self.min_symbol_switch_gap = min_symbol_switch_gap

        # Per-symbol consecutive ADX failure counter — prevents selecting symbols
        # that pass CoinSelector but repeatedly fail the execution min_adx gate.
        # Logs: BTC/SOL/AVAX all got blacklisted after 3 fails, keeping system flat for hours
        self._adx_fail_count: dict[str, int] = {}
        self._adx_fail_max = 4   # Increased from 3 - allow one extra chance in low ADX regimes
        self._adx_fail_cooldown_secs = 1200  # Reduced from 1800 - 20min vs 30min blackout

        # Timestamps when a symbol was ADX-blacklisted
        self._adx_blacklist: dict[str, float] = {}

        self.selector = CoinSelector(
            timeframe=timeframe,
            top_k=max_active * selector_top_k_multiplier,
            min_atr_pct=selector_min_atr_pct,
            soft_min_volume_ratio=selector_soft_min_volume_ratio,
            rsi_long_min=selector_rsi_long_min,
            rsi_long_max=selector_rsi_long_max,
            min_adx=selector_min_adx,
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

    def _get_refresh_interval(self) -> int:
        """
        Return refresh interval in seconds.
        When flat for extended periods, refresh more frequently to catch
        improving market conditions.
        """
        now = time.time()
        if not self.active_symbols:
            # Flat mode - check how long we've been flat
            flat_duration = now - self._flat_since if self._flat_since > 0 else 0
            hours_flat = flat_duration / 3600

            if hours_flat >= 1.5:
                # After 1.5 hours flat, refresh every 10 minutes
                return 600
            elif hours_flat >= 0.75:
                # After 45 min flat, refresh every 15 minutes
                return 900
            else:
                # First 45 min: refresh every 20 minutes
                return 1200
        else:
            # Active trading: use normal refresh interval
            return self.refresh_seconds

    def _try_fallback_selection(self) -> List[str]:
        """
        When in fallback mode, try to find at least one symbol by relaxing filters.
        Returns the best available symbol even if it doesn't pass all filters.
        """
        print("[Universe] FALLBACK MODE: attempting relaxed selection...")

        # Score all symbols with relaxed criteria
        fallback_scores: dict[str, float] = {}
        for symbol in self.all_symbols:
            if symbol in self._adx_blacklist:
                continue

            # Direct scoring without hard filters
            score = self.selector._score_symbol(symbol)
            if score is None:
                continue
            
            ## Only allow borderline candidates, not completely bad ones
            if score > -500: # instead of accepting everything
                fallback_scores[symbol] = score

        if not fallback_scores:
            return []

        # Return top symbol even with low score
        ranked = sorted(fallback_scores, key=fallback_scores.get, reverse=True)
        best = ranked[:1]
        print(f"[Universe] FALLBACK: selected {best} as best available option")
        return best

    def refresh_if_needed(self) -> List[str]:
        now = time.time()

        # Dynamic refresh interval based on flat/active state
        current_refresh_interval = self._get_refresh_interval()
        if now - self.last_refresh < current_refresh_interval:
            return self.active_symbols

        self.last_refresh = now

        # Track flat duration
        if not self.active_symbols:
            if self._flat_since == 0:
                self._flat_since = now
            self._consecutive_flat_refreshes += 1

            # Activate fallback mode after N consecutive flat refreshes
            if self._consecutive_flat_refreshes >= self._fallback_activates_after_refreshes:
                if not self._fallback_mode:
                    self._fallback_mode = True
                    print(
                        f"[Universe] FALLBACK MODE ACTIVATED | "
                        f"flat for {self._consecutive_flat_refreshes} refreshes (~{self._consecutive_flat_refreshes} hours)"
                    )
        else:
            # Reset flat tracking when we have active symbols
            if self._flat_since > 0:
                flat_hours = (now - self._flat_since) / 3600
                print(f"[Universe] Exited flat mode after {flat_hours:.1f} hours")
            self._flat_since = 0.0
            self._consecutive_flat_refreshes = 0
            self._fallback_mode = False

        ranked = self.selector.select(self.all_symbols)
        candidate_symbols = ranked[: self.max_active]

        # If selector finds nothing valid, try fallback mode
        if not candidate_symbols and self._fallback_mode:
            fallback_candidates = self._try_fallback_selection()
            if fallback_candidates:
                print(
                    f"[Universe] FALLBACK: using relaxed selection → {fallback_candidates}"
                )
                candidate_symbols = fallback_candidates

        # If still no candidates, go flat
        if not candidate_symbols:
            print(
                f"[Universe] selector found no valid symbols → flat mode "
                f"(consecutive_flat_refreshes={self._consecutive_flat_refreshes}, fallback={'ON' if self._fallback_mode else 'OFF'})"
            )
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

        Increments the fail counter for a symbol. If the symbol is already
        blacklisted this is a no-op — the symbol stays blacklisted regardless
        of how many more fails accumulate.
        """
        if symbol in self._adx_blacklist:
            return  # already blacklisted — ignore further fails
        if symbol not in self.active_symbols:
            return  # not in universe — ignore

        self._adx_fail_count[symbol] = self._adx_fail_count.get(symbol, 0) + 1
        count = self._adx_fail_count[symbol]
        if count >= self._adx_fail_max:
            self._adx_blacklist[symbol] = time.time()
            print(
                f"[Universe] {symbol} ADX-blacklisted for {self._adx_fail_cooldown_secs // 60}min "
                f"after {count} consecutive adx_low failures"
            )
