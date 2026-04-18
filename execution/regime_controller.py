# execution/ regime_controller.py

from enum import Enum
import pandas as pd


class MarketRegime(str, Enum):
    TREND_STRONG = "trend_strong"
    TREND_WEAK = "trend_weak"
    SIDEWAYS = "sideways"


class RegimeController:
    """
    Detect market regime and adjust risk/trading rules.
    """

    def detect(self, df: pd.DataFrame) -> MarketRegime:
        row = df.iloc[-1]

        adx = float(row["adx"])
        atr_pct = float(row["atr_pct"])
        rsi = float(row.get("rsi", 50.0))  # Add RSI for oversold detection
        price = float(row["close"])
        ema200 = float(row["ema200"])
        ema_fast = float(row["ema_fast"])
        ema_slow = float(row["ema_slow"])

        bullish_cross = ema_fast > ema_slow
        near_ema200 = ema200 > 0 and abs(price - ema200) / ema200 <= 0.015

        # Strong trend detection - tightened ADX threshold from 28 to 26
        if adx >= 26 and atr_pct >= 0.0025:
            return MarketRegime.TREND_STRONG

        # Weak trend detection - relaxed from 16 to 14 ADX, add oversold recovery support
        # During deep oversolds (RSI < 30), even modest ADX (12+) can indicate recovery opportunity
        if adx >= 14:
            return MarketRegime.TREND_WEAK

        # Recovery-friendly weak trend classification - enhanced for low-RSI periods
        if adx >= 10 and atr_pct >= 0.003 and bullish_cross and (near_ema200 or rsi < 30):
            return MarketRegime.TREND_WEAK

        return MarketRegime.SIDEWAYS

    def risk_multiplier(self, regime: MarketRegime) -> float:
        if regime == MarketRegime.TREND_STRONG:
            return 1.0

        if regime == MarketRegime.TREND_WEAK:
            return 0.75

        return 0.0

    def trading_allowed(self, regime: MarketRegime) -> bool:
        return regime != MarketRegime.SIDEWAYS

    def skip_reason(self, df: pd.DataFrame) -> str:
        row = df.iloc[-1]

        adx = float(row["adx"])
        atr_pct = float(row["atr_pct"])
        price = float(row["close"])
        ema200 = float(row["ema200"])
        ema_fast = float(row["ema_fast"])
        ema_slow = float(row["ema_slow"])

        bullish_cross = ema_fast > ema_slow
        near_ema200 = ema200 > 0 and abs(price - ema200) / ema200 <= 0.015

        return (
            f"regime_sideways(adx={adx:.1f}, atr_pct={atr_pct:.4f}, "
            f"bullish_cross={bullish_cross}, near_ema200={near_ema200}, "
            f"price={price:.4f}, ema200={ema200:.4f})"
        )