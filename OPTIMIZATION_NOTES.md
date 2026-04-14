# Profit Optimization (2026-04-13)

**Made by:** Claude Code (AI assistant)

## Strategy Parameter Changes (Profit-Focused)
| Parameter | Before | After |
|-----------|--------|-------|
| Stop loss | 1.30 ATR | **1.00 ATR** |
| Take profit | 3.80 ATR | **3.00 ATR** |
| Min ADX | 20.0 | **25.0** |
| RSI range | 40–75 | **48–68** |
| Min expected edge | 0.00005 | **0.00005** (unchanged) |
| Base threshold | 0.49 | **0.49** (unchanged) |
| Min ATR% | 0.0010 | **0.0012** |

## Training Improvements
- Threshold grid: 0.01 → **0.005** step (2x finer search)
- Minimum trades for threshold validity: 25 → **50**
- Scoring: 75% precision, 15% F1, 5% recall (precision-focused)
- Trade rate penalty increased to discourage overtrading

## Code Fixes
- `features/technicals.py` — added MIN_CANDLES=220 guard (prevents crash on insufficient data)
- `models/ensemble.py` — fixed regime detection conflict; aligned to RegimeController
- `data/fetcher.py` — added flush=True to all print statements for Railway log visibility

## Model Quality Gates (Disabled)
- `REQUIRE_MODEL_QUALITY=false` — all coins trade regardless of model quality
- Default thresholds remain: F1≥0.10, Precision≥0.10, Recall≥0.10
- Model quality gates are bypassed to maximize coin coverage

## Files Modified
- `main.py` — strategy config overrides (SL/TP/ADX/RSI)
- `.env` — REQUIRE_MODEL_QUALITY=false, strategy parameters
- `config/live.py` — default values aligned
- `execution/strategy.py` — default values aligned
- `train/train_direction_model.py` — finer threshold grid, precision-focused scoring
- `models/ensemble.py` — regime import fix, weight alignment
- `features/technicals.py` — added MIN_CANDLES=220 guard

## Current Deployment
- Railway — shadow mode
- Coins: BTC/USDT, ETH/USDT, SOL/USDT, AVAX/USDT, LINK/USDT, DOGE/USDT, BNB/USDT
- Timeframe: 15m
- Loop sleep: 20 seconds

## Context
See Claude conversation from this date.