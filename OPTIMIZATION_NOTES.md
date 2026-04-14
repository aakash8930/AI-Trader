# Profit Optimization (2026-04-13 → 2026-04-14)

**Made by:** Claude Code (AI assistant)

## Log Analysis Findings (2026-04-14)

### Critical Problems Identified
- SOL/LINK trapped in model-quality gate purgatory — rejected every 20s for 7.5+ hours, zero trades executed
- DOGE added to universe at ADX=19, failed every cycle for 40 min — ADX not enforced at universe-selection level
- AVAX stopped out twice — stop_atr_mult=1.0 too tight for normal intraday noise
- BTC repeatedly blocked by RSI cap of 68.0 in strong trends (RSI 68-82 range, ADX 29-50)
- base_long_threshold=0.51 systematically filtering BTC prob=0.488-0.503 entries
- CoinSelector used adaptive threshold of 0.48 while execution required 0.51 — layer mismatch

---

## Strategy Parameter Changes (2026-04-14 — Live Deployment)
| Parameter | Before | After |
|-----------|--------|-------|
| base_long_threshold | 0.51 | **0.49** |
| min_adx | 25.0 | **26.0** |
| rsi_long_max (TREND_WEAK) | 68.0 | **68.0** |
| rsi_strong_trend_max (TREND_STRONG) | n/a | **75.0** |
| stop_atr_mult | 1.00 | **1.50** |
| take_atr_mult | 3.00 | **2.50** |
| trail_activate_atr_mult | 1.0 | **0.5** |
| trail_atr_mult | 1.0 | **0.5** |
| min_model_val_f1 | 0.10 | **0.25** |
| min_model_val_precision | 0.10 | **0.25** |
| min_model_val_recall | 0.10 | **0.25** |
| CoinSelector MIN_F1/PREC/RECALL | 0.10 | **0.25** |

---

## Architecture Fixes (2026-04-14)

### 1. Model-quality gate moved upstream (Priority 1)
- **Problem:** Gate was applied in `_filtered_active_symbols()` AFTER universe was built. SOL/LINK passed CoinSelector, got added to universe, then rejected every cycle for hours.
- **Fix:** New `execution/model_quality.py` — shared `model_quality_ok()` used by both CoinSelector and MultiRunner. CoinSelector now filters model-quality BEFORE ranking. SOL/LINK never enter the universe.
- **Files:** `execution/model_quality.py` (new), `execution/coin_selector.py`, `execution/multi_runner.py`

### 2. Per-symbol model-quality blacklist (Priority 1 continued)
- **Problem:** Even after 150+ rejections, SOL/LINK were never removed from consideration.
- **Fix:** `_model_reject_counts`, `_model_blacklist`, `_model_reject_max=5`, `_model_reject_cooldown_secs=3600` in `MultiSymbolTradingSystem`. After 5 consecutive model-quality rejections, symbol is blacklisted for 60 min.
- **Files:** `execution/multi_runner.py`

### 3. Per-symbol ADX blacklist (Priority 2)
- **Problem:** DOGE added with ADX=19, failed every cycle for 40 min, universe kept it because score improved from -997 to +1.144.
- **Fix:** `UniverseManager` now tracks `_adx_fail_count` per symbol. After 3 consecutive `adx_low` failures, symbol is 30-min blacklisted. `refresh_if_needed()` checks blacklist cooldown before accepting candidates.
- **Files:** `execution/universe_manager.py`, `execution/multi_runner.py`, `execution/runner.py`

### 4. Runner skip reason cache (Priority 2 continued)
- **Problem:** ADX fail tracking required reading runner internals to detect `adx_low` skips.
- **Fix:** Runner now stores `_last_skip_reason` on every SKIP path (exposed via `@property skip_reason`). MultiRunner reads this after each `run_once()` and calls `universe.register_adx_fail()` when appropriate.
- **Files:** `execution/runner.py`, `execution/multi_runner.py`

### 5. Regime-aware RSI ceiling (Priority 5)
- **Problem:** BTC RSI 68-73 in strong trends (ADX 29-50) was blocked by hard cap of 68.0.
- **Fix:** `rsi_strong_trend_max=75.0` new field. When `regime=TREND_STRONG` AND `ADX >= 30`, RSI ceiling rises to 75.0. `TREND_WEAK` keeps 68.0 ceiling.
- **File:** `execution/strategy.py`

### 6. CoinSelector–execution threshold alignment (Priority 3)
- **Problem:** CoinSelector adaptive threshold floor=0.48, execution floor=0.51. Symbols with prob=0.488 passed selector but failed runner.
- **Fix:** `base_long_threshold` lowered from 0.51 to 0.49. CoinSelector already used 0.48. Gap narrowed. `long_th` floor in `generate_signal()` also dropped from 0.49 to 0.47 to allow borderline cases.
- **File:** `execution/strategy.py`

---

## Previous Changes (2026-04-13 — Preserved)
| Parameter | Before | After |
|-----------|--------|-------|
| Stop loss | 1.30 ATR | **1.00 ATR** |
| Take profit | 3.80 ATR | **3.00 ATR** |
| Min ADX | 20.0 | **25.0** |
| RSI range | 40–75 | **48–68** |
| Min expected edge | 0.00005 | **0.00005** (unchanged) |
| Min ATR% | 0.0010 | **0.0012** |

## Training Improvements (2026-04-13 — Preserved)
- Threshold grid: 0.01 → **0.005** step (2x finer search)
- Minimum trades for threshold validity: 25 → **50**
- Scoring: 75% precision, 15% F1, 5% recall (precision-focused)
- Trade rate penalty increased to discourage overtrading

## Code Fixes (2026-04-13 — Preserved)
- `features/technicals.py` — added MIN_CANDLES=220 guard
- `models/ensemble.py` — fixed regime detection conflict; aligned to RegimeController
- `data/fetcher.py` — added flush=True to all print statements for Railway log visibility

## Files Modified (2026-04-14)
- `execution/model_quality.py` — NEW: shared model-quality check
- `execution/coin_selector.py` — model-quality pre-filter, thresholds raised to 0.25
- `execution/multi_runner.py` — blacklist tracking, ADX fail registration, improved logging
- `execution/universe_manager.py` — ADX fail tracking, blacklist with cooldown
- `execution/runner.py` — skip_reason cache, all SKIP paths set reason
- `execution/strategy.py` — thresholds, stop/TP, trailing, RSI regime-awareness
- `config/live.py` — model-quality thresholds raised to 0.25

## Current Deployment (2026-04-14)
- Railway — shadow mode
- Coins: BTC/USDT, ETH/USDT, SOL/USDT, AVAX/USDT, LINK/USDT, DOGE/USDT, BNB/USDT
- Timeframe: 15m
- Loop sleep: 20 seconds
- Model quality gates: **ENABLED** (F1/prec/rec ≥ 0.25)
- Min ADX: 26.0