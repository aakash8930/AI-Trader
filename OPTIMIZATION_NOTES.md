# Profit Optimization (2026-04-13)

**Made by:** Claude Code (AI assistant)

## Changes
- Stop loss: 1.30 → 1.00 ATR
- Take profit: 3.80 → 3.00 ATR
- Model quality gates: F1/Prec/Recall 0.10 → 0.35
- Threshold grid: 0.01 → 0.005 step
- Min ADX: 20 → 25
- Regime fix: aligned `models/ensemble.py` to use `RegimeController` instead of conflicting `regime.py`

## Files Modified
- `main.py` — strategy config overrides
- `.env` — production parameter overrides
- `config/live.py` — default values aligned
- `execution/strategy.py` — default values aligned
- `train/train_direction_model.py` — finer threshold grid, precision-focused scoring
- `models/ensemble.py` — regime import fix, weight alignment

## Context
See Claude conversation from this date.