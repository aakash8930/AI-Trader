#execution/multi_runner.py

import time
from collections import defaultdict

from execution.runner import TradingRunner
from execution.universe_manager import UniverseManager
from execution.model_quality import model_quality_ok
from config.live import LiveSettings
from logs.logger import TradeLogger
from execution.strategy import StrategyConfig


class MultiSymbolTradingSystem:
    """
    Fully autonomous multi-symbol trading system.
    """

    def __init__(
        self,
        settings: LiveSettings,
        logger: TradeLogger | None = None,
        strategy_config: StrategyConfig | None = None,
    ):
        self.settings = settings
        self.logger = logger if logger is not None else TradeLogger()
        self.strategy_config = strategy_config
        self.runners: dict[str, TradingRunner] = {}

        self.universe = UniverseManager(
            all_symbols=settings.symbols,
            timeframe=settings.timeframe,
            max_active=settings.max_active_positions,
            refresh_minutes=settings.universe_refresh_minutes,
            selector_top_k_multiplier=settings.selector_top_k_multiplier,
            selector_min_atr_pct=settings.selector_min_atr_pct,
            selector_soft_min_volume_ratio=settings.selector_soft_min_volume_ratio,
            # Keep selector slightly more permissive than execution while avoiding
            # large threshold mismatches that cause skip loops.
            selector_min_adx=max(16.0, settings.strategy_min_adx - 1.5),
            exchange_name=settings.exchange_name,
            exchange_fallbacks=settings.exchange_fallbacks,
            exchange_timeout_ms=settings.exchange_timeout_ms,
        )

        # Per-symbol consecutive rejection counters
        self._model_reject_counts: dict[str, int] = defaultdict(int)
        self._model_reject_max = 5           # blacklist after N rejects
        self._model_reject_cooldown_secs = 3600  # 60 min blackout

        # Timestamps when a symbol was blacklisted
        self._model_blacklist: dict[str, float] = {}

    def _model_quality_ok(self, symbol: str) -> bool:
        ok, metrics = model_quality_ok(
            symbol,
            min_f1=max(self.settings.min_model_val_f1, 0.15),  # Ensure not too strict
            min_precision=max(self.settings.min_model_val_precision, 0.15),
            min_recall=max(self.settings.min_model_val_recall, 0.10),
            allow_high_recall_compensation=True,
        )
        if not ok and metrics:
            print(
                f"[{symbol}] model-quality gate | "
                f"f1={metrics['val_f1']:.3f} prec={metrics['val_precision']:.3f} rec={metrics['val_recall']:.3f} "
                f"(required f1>={max(self.settings.min_model_val_f1, 0.15):.2f} prec>={max(self.settings.min_model_val_precision, 0.15):.2f} rec>={max(self.settings.min_model_val_recall, 0.10):.2f})"
            )
        return ok

    def _filtered_active_symbols(self, symbols: list[str]) -> list[str]:
        now = time.time()
        filtered: list[str] = []

        for symbol in symbols:
            # Check blacklist
            if symbol in self._model_blacklist:
                if now - self._model_blacklist[symbol] < self._model_reject_cooldown_secs:
                    continue
                # Cooldown expired — remove from blacklist but KEEP the counter
                # so the accumulated rejection count is preserved.
                else:
                    del self._model_blacklist[symbol]
                    # Counter is kept at its last value — if it was 4/5 it stays 4

            if self.settings.require_model_quality and not self._model_quality_ok(symbol):
                self._model_reject_counts[symbol] = self._model_reject_counts.get(symbol, 0) + 1
                count = self._model_reject_counts[symbol]

                if count >= self._model_reject_max:
                    self._model_blacklist[symbol] = now
                    print(
                        f"[{symbol}] model-quality BLACKLISTED for {self._model_reject_cooldown_secs // 60}min "
                        f"after {count} consecutive rejections"
                    )
                else:
                    print(f"[{symbol}] rejected by model-quality gate ({count}/{self._model_reject_max})")
                continue

            # Passed — reset counters
            self._model_reject_counts[symbol] = 0
            if symbol in self._model_blacklist:
                del self._model_blacklist[symbol]
            filtered.append(symbol)

        return filtered

    def _ensure_runner(self, symbol: str):
        if symbol in self.runners:
            return

        runner = TradingRunner(
            symbol=symbol,
            timeframe=self.settings.timeframe,
            lookback=self.settings.lookback,
            mode=self.settings.mode,
            starting_balance_usdt=self.settings.starting_balance_usdt,
            cooldown_minutes=self.settings.cooldown_minutes,
            risk_per_trade=self.settings.risk_per_trade,
            config=self.strategy_config,
            exchange_name=self.settings.exchange_name,
            exchange_fallbacks=self.settings.exchange_fallbacks,
            exchange_timeout_ms=self.settings.exchange_timeout_ms,
            logger=self.logger,
        )

        self.runners[symbol] = runner
        print(f"➕ Runner added for {symbol}")

    def _remove_inactive_runners(self, active_symbols: list[str]):
        inactive = [symbol for symbol in self.runners if symbol not in active_symbols]
        for symbol in inactive:
            runner = self.runners[symbol]
            if runner.has_open_position:
                print(
                    f"[SYSTEM] Retaining runner for {symbol} until open position is closed"
                )
                continue
            del self.runners[symbol]
            print(f"➖ Runner removed for {symbol}")

    def run_loop(self):
        print(f"🚀 Autonomous trading system started [MODE={self.settings.mode}]")

        flat_mode_start: float | None = None
        total_refreshes = 0
        flat_refreshes = 0

        while True:
            try:
                active_symbols = self.universe.refresh_if_needed()
                active_symbols = self._filtered_active_symbols(active_symbols)

                if not active_symbols:
                    self._remove_inactive_runners([])
                    total_refreshes += 1
                    flat_refreshes += 1

                    if flat_mode_start is None:
                        flat_mode_start = time.time()

                    flat_duration = time.time() - flat_mode_start
                    flat_hours = flat_duration / 3600

                    # Detailed flat mode status
                    print(
                        f"[SYSTEM] FLAT MODE | "
                        f"duration={flat_hours:.2f}h | "
                        f"consecutive_flat_refreshes={flat_refreshes} | "
                        f"total_refreshes={total_refreshes} | "
                        f"fallback={'ON' if self.universe._fallback_mode else 'OFF'}"
                    )

                    # Show which symbols failed and why (from model quality gate)
                    if self.settings.require_model_quality:
                        rejected_symbols = [
                            s for s in self.universe.all_symbols
                            if not self._model_quality_ok(s)
                        ]
                        if rejected_symbols:
                            print(
                                f"[SYSTEM] Model-quality rejected: {rejected_symbols} | "
                                f"consider lowering thresholds or retraining"
                            )

                    time.sleep(max(self.settings.sleep_seconds, 120))
                    continue
                else:
                    # Exited flat mode
                    if flat_mode_start is not None:
                        flat_duration = time.time() - flat_mode_start
                        flat_hours = flat_duration / 3600
                        print(
                            f"[SYSTEM] EXITED FLAT MODE after {flat_hours:.2f}h | "
                            f"activating {len(active_symbols)} symbols: {active_symbols}"
                        )
                        flat_mode_start = None
                        flat_refreshes = 0
                    total_refreshes += 1

                for symbol in active_symbols:
                    self._ensure_runner(symbol)

                self._remove_inactive_runners(active_symbols)

                for symbol, runner in list(self.runners.items()):
                    if symbol not in active_symbols and not runner.has_open_position:
                        continue
                    runner.run_once()

                    # Track ADX failures per symbol — after N consecutive fails,
                    # the universe manager blacklists the symbol.
                    skip_reason = runner.skip_reason
                    if skip_reason and skip_reason.startswith("adx_low"):
                        self.universe.register_adx_fail(symbol)
                    elif skip_reason is None and symbol in self.universe._adx_fail_count:
                        # Successful entry — reset ADX fail counter
                        self.universe._adx_fail_count.pop(symbol, None)

                    if symbol not in active_symbols and not runner.has_open_position:
                        del self.runners[symbol]
                        print(f"➖ Runner removed for {symbol}")

                time.sleep(self.settings.sleep_seconds)

            except KeyboardInterrupt:
                print("Stopped by user")
                break

            except RuntimeError as e:
                error_msg = str(e)
                if "FETCHER" in error_msg or "exchange" in error_msg.lower():
                    print(f"\n❌ FATAL: {error_msg}")
                    print("\nSystem cannot start due to exchange connectivity issues.")
                    break
                raise

            except Exception as e:
                print(f"System error: {e}")
                time.sleep(30)
