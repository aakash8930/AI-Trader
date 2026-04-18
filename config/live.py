#config/live.py

import os
from dataclasses import dataclass, field

LIVE_UNLOCK_TOKEN = "YES_I_UNDERSTAND"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None else float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None else int(raw)


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


@dataclass(slots=True)
class LiveSettings:
    mode: str = "paper"
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT"])
    excluded_symbols: list[str] = field(default_factory=list)
    timeframe: str = "15m"

    starting_balance_usdt: float = 500.0
    cooldown_minutes: int = 30
    risk_per_trade: float = 0.01

    max_active_positions: int = 2
    sleep_seconds: int = 900
    universe_refresh_minutes: int = 60

    require_model_quality: bool = True
    min_model_val_f1: float = 0.25
    min_model_val_precision: float = 0.25
    min_model_val_recall: float = 0.25

    lookback: int = 300

    # Strategy configuration - SYNCED WITH strategy.py (2026-04-18)
    strategy_min_prob: float = 0.515  # Increased from 0.48 - need 51.5% for positive edge after fees
    strategy_min_adx: float = 12.0  # Reduced from 18.0 - critical fix to match strategy.py
    strategy_min_atr_pct: float = 0.0008  # Reduced from 0.0010 - allow lower vol in quiet markets
    strategy_rsi_long_min: float = 28.0  # CRITICAL FIX: Reduced from 38.0 - catch oversold bounces during corrections
    strategy_rsi_long_max: float = 75.0  # Increased from 72.0 - allow strong momentum
    strategy_weak_trend_min_adx: float = 16.0  # Reduced from 18.0 - relax weak trend entry requirements
    strategy_weak_trend_min_prob_edge: float = 0.006  # CRITICAL FIX: Reduced from 0.015 - realistic edge in 50/50 markets
    strategy_weak_trend_min_volume_ratio: float = 0.60  # Reduced from 0.75 - allow low liquidity in quiet periods
    strategy_fee_pct_per_side: float = 0.0010
    strategy_slippage_pct_per_side: float = 0.0008
    strategy_min_expected_edge: float = -0.0005  # CRITICAL FIX: Relaxed from 0.00008 - allow breakeven trades in high-confidence setups
    strategy_stop_atr_mult: float = 2.0  # Updated from 1.25 - give trades more room
    strategy_take_atr_mult: float = 2.5  # Updated from 2.75 - realistic targets
    strategy_trail_atr_mult: float = 1.2  # Updated from 0.5 - lock in more profit

    # Adaptive threshold settings - SYNCED WITH strategy.py
    strategy_adaptive_threshold: bool = True
    strategy_threshold_relaxation: float = 0.030  # Increased from 0.02 - reward strong ADX more (ADX>40)
    strategy_threshold_floor: float = 0.48  # Increased from 0.42 - protect against over-relaxation

    # Universe / selector configuration
    selector_top_k_multiplier: int = 2
    selector_min_atr_pct: float = 0.0008  # Match coin_selector default
    selector_soft_min_volume_ratio: float = 0.12  # Reduced from 0.15

    # Risk management
    max_drawdown_pct: float = 0.03  # Circuit breaker threshold (3%)

    # Exchange configuration
    exchange_name: str = "binance"
    exchange_fallbacks: list[str] = field(default_factory=lambda: ["bybit", "kraken", "okx"])
    exchange_timeout_ms: int = 20000

    @classmethod
    def from_env(cls) -> "LiveSettings":
        raw_symbols = os.getenv("TRADING_SYMBOLS", "BTC/USDT")
        symbols = [s.strip().upper() for s in raw_symbols.split(",") if s.strip()]

        raw_excluded = os.getenv("EXCLUDED_SYMBOLS", "")
        excluded = [s.strip().upper() for s in raw_excluded.split(",") if s.strip()]
        if excluded:
            symbols = [s for s in symbols if s not in excluded]

        raw_fallbacks = os.getenv("EXCHANGE_FALLBACKS", "bybit,kraken,okx")
        fallbacks = [s.strip().lower() for s in raw_fallbacks.split(",") if s.strip()]

        return cls(
            mode=os.getenv("TRADING_MODE", "paper").strip().lower(),
            symbols=symbols,
            excluded_symbols=excluded,
            timeframe=os.getenv("TRADING_TIMEFRAME", "15m"),
            starting_balance_usdt=_env_float("PAPER_STARTING_BALANCE_USDT", 500.0),
            cooldown_minutes=_env_int("ENTRY_COOLDOWN_MINUTES", 30),
            risk_per_trade=_env_float("RISK_PER_TRADE", 0.01),
            max_active_positions=_env_int("MAX_ACTIVE_POSITIONS", 2),
            sleep_seconds=_env_int("LOOP_SLEEP_SECONDS", 900),
            universe_refresh_minutes=_env_int("UNIVERSE_REFRESH_MINUTES", 60),
            require_model_quality=_env_bool("REQUIRE_MODEL_QUALITY", True),
            min_model_val_f1=_env_float("MIN_MODEL_VAL_F1", 0.10),
            min_model_val_precision=_env_float("MIN_MODEL_VAL_PRECISION", 0.10),
            min_model_val_recall=_env_float("MIN_MODEL_VAL_RECALL", 0.10),
            lookback=_env_int("LOOKBACK_BARS", 300),
            strategy_min_prob=_env_float("STRATEGY_MIN_PROB", 0.515),
            strategy_min_adx=_env_float("STRATEGY_MIN_ADX", 12.0),
            strategy_min_atr_pct=_env_float("STRATEGY_MIN_ATR_PCT", 0.0008),
            strategy_rsi_long_min=_env_float("STRATEGY_RSI_LONG_MIN", 28.0),
            strategy_rsi_long_max=_env_float("STRATEGY_RSI_LONG_MAX", 75.0),
            strategy_weak_trend_min_adx=_env_float("STRATEGY_WEAK_TREND_MIN_ADX", 16.0),
            strategy_weak_trend_min_prob_edge=_env_float("STRATEGY_WEAK_TREND_MIN_PROB_EDGE", 0.006),
            strategy_weak_trend_min_volume_ratio=_env_float("STRATEGY_WEAK_TREND_MIN_VOLUME_RATIO", 0.60),
            strategy_fee_pct_per_side=_env_float("STRATEGY_FEE_PCT_PER_SIDE", 0.0010),
            strategy_slippage_pct_per_side=_env_float("STRATEGY_SLIPPAGE_PCT_PER_SIDE", 0.0008),
            strategy_min_expected_edge=_env_float("STRATEGY_MIN_EXPECTED_EDGE", -0.0005),
            strategy_stop_atr_mult=_env_float("STRATEGY_STOP_ATR_MULT", 2.0),
            strategy_take_atr_mult=_env_float("STRATEGY_TAKE_ATR_MULT", 2.5),
            strategy_trail_atr_mult=_env_float("STRATEGY_TRAIL_ATR_MULT", 1.2),
            strategy_adaptive_threshold=_env_bool("STRATEGY_ADAPTIVE_THRESHOLD", True),
            strategy_threshold_relaxation=_env_float("STRATEGY_THRESHOLD_RELAXATION", 0.030),
            strategy_threshold_floor=_env_float("STRATEGY_THRESHOLD_FLOOR", 0.48),
            selector_top_k_multiplier=_env_int("SELECTOR_TOP_K_MULTIPLIER", 2),
            selector_min_atr_pct=_env_float("SELECTOR_MIN_ATR_PCT", 0.0008),
            selector_soft_min_volume_ratio=_env_float("SELECTOR_SOFT_MIN_VOLUME_RATIO", 0.12),
            max_drawdown_pct=_env_float("MAX_DRAWDOWN_PCT", 0.03),
            exchange_name=_env_str("EXCHANGE_NAME", "binance"),
            exchange_fallbacks=fallbacks,
            exchange_timeout_ms=_env_int("EXCHANGE_TIMEOUT_MS", 20000),
        )

    def validate(self) -> None:
        if self.mode not in {"paper", "shadow", "live"}:
            raise ValueError("Invalid TRADING_MODE")

        if not self.symbols:
            raise ValueError("No trading symbols configured")

        if self.lookback < 220:
            raise ValueError("LOOKBACK_BARS must be >= 220")

        if self.strategy_rsi_long_min >= self.strategy_rsi_long_max:
            raise ValueError("STRATEGY_RSI_LONG_MIN must be less than STRATEGY_RSI_LONG_MAX")

        if self.max_active_positions < 1:
            raise ValueError("MAX_ACTIVE_POSITIONS must be >= 1")

        if self.selector_top_k_multiplier < 1:
            raise ValueError("SELECTOR_TOP_K_MULTIPLIER must be >= 1")
