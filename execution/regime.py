
# execution/regime.py

from enum import Enum
import pandas as pd


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    CHOPPY = "choppy"


def detect_regime(df: pd.DataFrame) -> MarketRegime:
    """
    Simple + robust regime detection.
    Requires: ema200, adx columns
    """

    adx = df.iloc[-1]["adx"]
    price = df.iloc[-1]["close"]
    ema200 = df.iloc[-1]["ema200"]

    if adx >= 25 and price > ema200:
        return MarketRegime.TRENDING

    if adx < 15:
        return MarketRegime.RANGING

    return MarketRegime.CHOPPY
