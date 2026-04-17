import os
import numpy as np

from data.fetcher import MarketDataFetcher
from execution.model_quality import model_quality_ok
from features.technicals import compute_core_features


# Module-level thresholds — relaxed to allow more symbols through initial gate.
# Strategy engine applies additional filters (ADX, RSI, edge) for safety.
_COIN_SELECTOR_MIN_F1 = 0.15
_COIN_SELECTOR_MIN_PREC = 0.15
_COIN_SELECTOR_MIN_RECALL = 0.10


def _has_trained_model(symbol: str) -> bool:
    folder = os.path.join("models", symbol.replace("/", "_"))
    return (
        os.path.exists(os.path.join(folder, "model.pt"))
        and os.path.exists(os.path.join(folder, "scaler.save"))
        and os.path.exists(os.path.join(folder, "metadata.json"))
    )


def _model_quality_ok(symbol: str) -> bool:
    """Check model quality using the same thresholds as live execution."""
    ok, _ = model_quality_ok(
        symbol,
        min_f1=_COIN_SELECTOR_MIN_F1,
        min_precision=_COIN_SELECTOR_MIN_PREC,
        min_recall=_COIN_SELECTOR_MIN_RECALL,
    )
    return ok


class CoinSelector:
    """
    Scores symbols for live trading.

    Design goals:
    - use only closed candles
    - avoid selecting symbols the runner will almost certainly reject
    - prefer symbols already aligned with strategy rules
    - allow strong-trend overrides so the system does not become too idle
    """

    DEFAULT_SYMBOLS = [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "AVAX/USDT",
        "LINK/USDT",
        "DOGE/USDT",
        "BNB/USDT",
    ]

    def __init__(
        self,
        timeframe: str = "15m",
        lookback: int = 240,
        top_k: int = 4,
        min_atr_pct: float = 0.0008,
        soft_min_volume_ratio: float = 0.12,  # Reduced from 0.15 - allow lower vol in quiet markets
        rsi_long_min: float = 38.0,  # Reduced from 40.0 - match strategy.py
        rsi_long_max: float = 70.0,  # Reduced from 74.0 - tighter than strategy (72.0) to avoid over-extended entries
        min_adx: float = 17.0,  # Reduced from 20.0 - selector should be looser than runner
        exchange_name: str = "binance",
        exchange_fallbacks: list[str] | None = None,
        exchange_timeout_ms: int = 20000,
    ):
        self.timeframe = timeframe
        self.lookback = lookback
        self.top_k = top_k
        self.min_atr_pct = min_atr_pct
        self.soft_min_volume_ratio = soft_min_volume_ratio
        self.rsi_long_min = rsi_long_min
        self.rsi_long_max = rsi_long_max
        self.min_adx = min_adx

        self.fetcher = MarketDataFetcher(
            exchange_name=exchange_name,
            fallback_exchanges=exchange_fallbacks,
            timeout_ms=exchange_timeout_ms,
        )

        self._model_cache: dict[str, object] = {}
        self._selector_stats = {
            "total_checked": 0,
            "model_gate_rejected": 0,
            "prob_rejected": 0,
            "adx_rejected": 0,
            "rsi_rejected": 0,
            "atr_rejected": 0,
            "volume_rejected": 0,
            "ema_rejected": 0,
            "passed": 0,
        }

    def _get_model(self, symbol: str):
        if symbol in self._model_cache:
            return self._model_cache[symbol]

        from models.direction import DirectionModel

        model = DirectionModel.for_symbol(symbol)
        self._model_cache[symbol] = model
        return model

    def _model_probability_and_threshold(self, symbol: str, df) -> tuple[float, float]:
        try:
            model = self._get_model(symbol)
            prob = float(model.predict_proba(df))
            long_th = float(getattr(model, "long_threshold", 0.50))

            if not (0.0 <= prob <= 1.0):
                prob = 0.5

            return prob, long_th
        except Exception:
            return 0.5, 0.50

    def _score_symbol(self, symbol: str) -> float | None:
        try:
            raw_fetch_limit = max(self.lookback + 220, 420)
            df = self.fetcher.fetch_ohlcv(symbol, self.timeframe, limit=raw_fetch_limit)
            if df is None or df.empty or len(df) < self.lookback:
                print(f"[CoinSelector] {symbol} | insufficient_data")
                return None

            # Use only historical closed candles for selection.
            df = df.iloc[:-1].copy()
            if len(df) < self.lookback:
                print(f"[CoinSelector] {symbol} | insufficient_closed_candles")
                return None

            df = compute_core_features(df)
            df = df.dropna().copy()
            if df.empty:
                print(f"[CoinSelector] {symbol} | no_features_after_dropna")
                return None

            row = df.iloc[-1]

            price = float(row["close"])
            ema200 = float(row["ema200"])
            ema_fast = float(row["ema_fast"])
            ema_slow = float(row["ema_slow"])
            adx = float(row["adx"])
            atr_pct = float(row["atr_pct"])
            rsi = float(row["rsi"])
            dist_ema200 = float(row["dist_ema200"])

            if not np.isfinite(price) or price <= 0:
                print(f"[CoinSelector] {symbol} | invalid_price")
                return None

            if not np.isfinite(ema200) or ema200 <= 0:
                print(f"[CoinSelector] {symbol} | invalid_ema200")
                return None

            if not np.isfinite(adx):
                adx = 0.0
            if not np.isfinite(atr_pct):
                atr_pct = 0.0
            if not np.isfinite(rsi):
                rsi = 50.0
            if not np.isfinite(dist_ema200):
                dist_ema200 = 0.0

            vol_ratio = 1.0
            if "volume" in df.columns:
                vol_ma = float(df["volume"].rolling(20).mean().iloc[-1])
                cur_vol = float(row["volume"])
                if np.isfinite(vol_ma) and vol_ma > 0 and np.isfinite(cur_vol):
                    vol_ratio = cur_vol / vol_ma

            bullish_cross = ema_fast > ema_slow
            above_ema200 = price > ema200

            prob_up, model_long_th = self._model_probability_and_threshold(symbol, df)

            # Use the actual model threshold as the reference, not a fixed value.
            # The hard reject margin is tighter than execution to let borderline
            # candidates through CoinSelector without blocking strong-trend symbols.
            # CRITICAL FIX: Cap adjustment at +2% to prevent over-optimization
            base_threshold = 0.48
            dynamic_adjustment = model_long_th - base_threshold
            max_adjustment = 0.02
            capped_adjustment = min(dynamic_adjustment, max_adjustment)
            adaptive_long_th = base_threshold + capped_adjustment

            strong_trend = (
                above_ema200
                and bullish_cross
                and adx >= 26.0
                and atr_pct >= self.min_atr_pct
            )

            momentum_override = (
                bullish_cross
                and adx >= 30.0
                and atr_pct >= max(self.min_atr_pct, 0.0010)
                and prob_up >= adaptive_long_th + 0.01
                and dist_ema200 > -0.020
            )
            weak_trend = not strong_trend and above_ema200 and bullish_cross
            prob_edge = prob_up - adaptive_long_th

            reasons: list[str] = []
            final_blocker = None  # Track which filter was the deciding factor

            # Hard rejects only for clearly bad cases.
            if atr_pct < self.min_atr_pct * 0.80:
                reasons.append("atr_too_low")
                final_blocker = "atr"

            if vol_ratio < self.soft_min_volume_ratio * 0.60:
                reasons.append("volume_too_low")
                final_blocker = "volume"

            # Relaxed prob filter - let strategy engine make final call
            if prob_up < adaptive_long_th - 0.045:  # Tightened from 0.050 - reject worse candidates
                reasons.append("prob_too_low")
                final_blocker = "prob"

            # ADX hard reject: reduced to 17.0 to allow borderline symbols in low-vol regimes.
            # Strategy engine still applies its own min_adx filter (18.0).
            # Logs showed 3hr compression with ADX 16-19 - system went flat for hours.
            if adx < self.min_adx:
                reasons.append("adx_too_low")
                final_blocker = "adx"

            # EMA200 filter: SOL had prob=0.53-0.56, adx=25-29 but rejected for price<EMA200
            # Allow setups within 4% of EMA200 if momentum is building
            if not above_ema200 and dist_ema200 <= -0.040 and not momentum_override:
                reasons.append("far_below_ema200")
                final_blocker = "ema"

            # RSI handling:
            # - keep lower bound (38.0 to catch early turns)
            # - relax upper bound in strong trends
            rsi_upper = self.rsi_long_max
            if strong_trend:
                rsi_upper = max(rsi_upper, 80.0)  # Reduced from 82.0 - avoid late entries
            elif adx >= 32.0 and above_ema200 and bullish_cross:
                rsi_upper = max(rsi_upper, 78.0)  # Reduced from 80.0

            if rsi < self.rsi_long_min:
                reasons.append("rsi_too_low")
                final_blocker = "rsi"
            elif rsi > rsi_upper:
                reasons.append("rsi_bad")
                final_blocker = "rsi"

            if weak_trend and prob_edge < 0.015:
                reasons.append("weak_prob_edge")
                final_blocker = "prob"

            if weak_trend and adx < max(self.min_adx, 18.0):
                reasons.append("weak_adx_too_low")
                final_blocker = "adx"

            if weak_trend and vol_ratio < 0.75:
                reasons.append("weak_volume_too_low")
                final_blocker = "volume"

            if reasons:
                # Show how close the symbol was to passing
                adx_margin = f"{adx - self.min_adx:+.1f}"
                prob_margin = f"{prob_up - adaptive_long_th:+.3f}"
                rsi_margin = f"{rsi - self.rsi_long_min:+.1f}" if rsi < self.rsi_long_min else f"{rsi_upper - rsi:+.1f}"

                print(
                    f"[CoinSelector] {symbol} | REJECTED | "
                    f"blocker={final_blocker} | "
                    f"prob={prob_up:.3f}/{adaptive_long_th:.3f} (margin={prob_margin}) | "
                    f"adx={adx:.1f} (min={self.min_adx}, margin={adx_margin}) | "
                    f"rsi={rsi:.1f} (margin={rsi_margin}) | "
                    f"atr_pct={atr_pct:.4f} vol_ratio={vol_ratio:.2f} | "
                    f"reasons={reasons}"
                )
                return -999.0

            # Soft score:
            # probability matters most, then regime alignment, then momentum/liquidity.
            score = 0.0
            score += prob_up * 0.95
            score += min(adx, 50.0) / 100.0
            score += min(atr_pct, 0.0100) * 18.0
            score += min(max(vol_ratio, 0.0), 3.0) * 0.04

            if above_ema200:
                score += 0.12
            else:
                score -= 0.06

            if bullish_cross:
                score += 0.08

            if strong_trend:
                score += 0.06

            if momentum_override and not above_ema200:
                score += 0.03

            score += max(min(prob_edge, 0.10), -0.10) * 1.20

            # Mild penalty for late/extreme RSI, but no automatic rejection.
            if rsi > 68.0:  # Lowered from 72.0 - earlier penalty
                score -= min((rsi - 68.0) * 0.008, 0.10)  # Steeper penalty

            score = float(max(score, 0.0))

            reason = "ok"
            if momentum_override and not above_ema200:
                reason = "ok_momentum_override"
            elif strong_trend:
                reason = "ok_strong_trend"

            print(
                f"[CoinSelector] {symbol} | "
                f"score={score:.3f} "
                f"prob={prob_up:.3f}/{adaptive_long_th:.3f} "
                f"adx={adx:.1f} atr_pct={atr_pct:.4f} "
                f"rsi={rsi:.1f} vol_ratio={vol_ratio:.2f} "
                f"above_ema200={above_ema200} bullish_cross={bullish_cross} "
                f"reasons=['{reason}']"
            )
            return score

        except Exception as exc:
            print(
                f"[CoinSelector] {symbol} | "
                f"error on {self.fetcher.exchange_name}: {exc}"
            )
            return None

    def select(self, symbols: list[str]) -> list[str]:
        configured_symbols = symbols[:] if symbols else self.DEFAULT_SYMBOLS[:]

        # Reset stats for this refresh cycle
        self._selector_stats = {
            "total_checked": len(configured_symbols),
            "model_gate_rejected": 0,
            "prob_rejected": 0,
            "adx_rejected": 0,
            "rsi_rejected": 0,
            "atr_rejected": 0,
            "volume_rejected": 0,
            "ema_rejected": 0,
            "passed": 0,
        }

        supported = [s for s in configured_symbols if self.fetcher.is_symbol_supported(s)]
        unsupported = [s for s in configured_symbols if s not in supported]
        if unsupported:
            print(
                f"[CoinSelector] Unsupported on {self.fetcher.exchange_name}: {unsupported}"
            )

        eligible = [s for s in supported if _has_trained_model(s)]
        skipped = [s for s in supported if s not in eligible]
        if skipped:
            print(f"[CoinSelector] Skipped (no model): {skipped}")

        # PRE-FILTER: reject symbols that don't meet model-quality gate BEFORE ranking.
        # This prevents the universe from picking symbols that will immediately fail
        # the model-quality check in multi_runner._filtered_active_symbols().
        # Uses high-recall compensation to avoid discarding useful models.
        quality_rejected = []
        for s in eligible:
            ok, metrics = model_quality_ok(
                s,
                min_f1=_COIN_SELECTOR_MIN_F1,
                min_precision=_COIN_SELECTOR_MIN_PREC,
                min_recall=_COIN_SELECTOR_MIN_RECALL,
                allow_high_recall_compensation=True,
            )
            if not ok:
                quality_rejected.append(s)
                self._selector_stats["model_gate_rejected"] += 1
                if metrics:
                    print(
                        f"[CoinSelector] {s} | model_gate_rejected | "
                        f"f1={metrics.get('val_f1', 0):.3f} prec={metrics.get('val_precision', 0):.3f} rec={metrics.get('val_recall', 0):.3f}"
                    )

        if quality_rejected:
            print(f"[CoinSelector] Skipped (model-quality gate): {quality_rejected}")
        eligible = [s for s in eligible if s not in quality_rejected]

        scores: dict[str, float] = {}
        for symbol in eligible:
            score = self._score_symbol(symbol)
            if score is not None:
                if score == -999.0:
                    # Track rejection reasons from score output
                    pass
                else:
                    self._selector_stats["passed"] += 1
                scores[symbol] = score

        ranked = sorted(scores, key=scores.get, reverse=True)
        filtered_ranked = [s for s in ranked if scores[s] > -100]

        # Selector summary log
        print(
            f"[CoinSelector] SUMMARY | "
            f"checked={self._selector_stats['total_checked']} | "
            f"model_gate_rejected={self._selector_stats['model_gate_rejected']} | "
            f"passed_all_filters={self._selector_stats['passed']} | "
            f"tradable={len(filtered_ranked[:self.top_k])}"
        )

        if not filtered_ranked:
            print("⚠️ CoinSelector found no long-ready symbols")
            return []

        return filtered_ranked[: self.top_k]
