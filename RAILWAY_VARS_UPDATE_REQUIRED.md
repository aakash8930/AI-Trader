# Railway Environment Variables - Update Required (2026-04-18)

## Critical Issue
Railway's environment variables still contain the **OLD strict parameters** from April-14. These will **override** the config fixes made on 2026-04-18. You must update them for the config sync to take effect.

## Variables to Update on Railway

| Variable | Current (OLD) | New (FIXED) | Status |
|----------|---------------|------------|--------|
| `STRATEGY_MIN_PROB` | 0.48 | **0.515** | ⚠️ CRITICAL |
| `STRATEGY_MIN_ADX` | 18 | **12.0** | ⚠️ CRITICAL |
| `STRATEGY_MIN_ATR_PCT` | 0.0010 | **0.0008** | Important |
| `STRATEGY_RSI_LONG_MIN` | **38** | **28.0** | ⚠️ CRITICAL (Main issue) |
| `STRATEGY_RSI_LONG_MAX` | 72 | **75.0** | Important |
| `STRATEGY_WEAK_TREND_MIN_ADX` | (missing) | **16.0** | Add new |
| `STRATEGY_WEAK_TREND_MIN_PROB_EDGE` | (missing) | **0.006** | Add new |
| `STRATEGY_WEAK_TREND_MIN_VOLUME_RATIO` | (missing) | **0.60** | Add new |
| `STRATEGY_MIN_EXPECTED_EDGE` | 0.00008 | **-0.0005** | Important |
| `STRATEGY_STOP_ATR_MULT` | 2.0 | 2.0 | ✅ OK |
| `STRATEGY_TAKE_ATR_MULT` | 3.0 | **2.5** | Important |
| `STRATEGY_THRESHOLD_FLOOR` | 0.42 | **0.48** | Important |
| `STRATEGY_TRAIL_ATR_MULT` | 1.2 | 1.2 | ✅ OK |
| `SELECTOR_SOFT_MIN_VOLUME_RATIO` | 0.10 | **0.12** | Minor |

## Why This Matters

Your `config/live.py` now has the correct values, but Railway pulls configuration from **environment variables using the `from_env()` method**:

```python
# In config/live.py
@classmethod
def from_env(cls) -> "LiveSettings":
    ...
    strategy_min_prob=_env_float("STRATEGY_MIN_PROB", 0.515),
    strategy_min_adx=_env_float("STRATEGY_MIN_ADX", 12.0),
    strategy_rsi_long_min=_env_float("STRATEGY_RSI_LONG_MIN", 28.0),
    ...
```

**The env vars (Railway) take precedence over the defaults (code).**

## Update Steps on Railway Dashboard

1. Go to **Project Settings → Variables**
2. For each critical variable, click the edit icon (three dots)
3. Update the value
4. Press Enter to save
5. Trigger a new deployment (the system will use updated vars)

## Recommended Update Order

### Phase 1: Critical Variables (Required for fix to work)
These are the main culprits blocking trades:
1. `STRATEGY_RSI_LONG_MIN`: 38 → **28.0** ⭐ MAIN FIX
2. `STRATEGY_MIN_ADX`: 18 → **12.0**
3. `STRATEGY_MIN_PROB`: 0.48 → **0.515**

### Phase 2: Supporting Variables (Enable weak trends)
These allow the system to trade in sideways markets:
4. **Add** `STRATEGY_WEAK_TREND_MIN_ADX`: **16.0**
5. **Add** `STRATEGY_WEAK_TREND_MIN_PROB_EDGE`: **0.006**
6. **Add** `STRATEGY_WEAK_TREND_MIN_VOLUME_RATIO`: **0.60**

### Phase 3: Risk/Reward Tuning (Improve P&L)
These fine-tune entry/exit mechanics:
7. `STRATEGY_MIN_ATR_PCT`: 0.0010 → **0.0008**
8. `STRATEGY_MIN_EXPECTED_EDGE`: 0.00008 → **-0.0005**
9. `STRATEGY_TAKE_ATR_MULT`: 3.0 → **2.5**
10. `STRATEGY_THRESHOLD_FLOOR`: 0.42 → **0.48**
11. `SELECTOR_SOFT_MIN_VOLUME_RATIO`: 0.10 → **0.12**

## Testing Procedure After Updates

1. **Update Phase 1** on Railway
2. **Trigger deployment** and run **2 hours shadow mode**
3. Check logs for signal increase (expect 3-5x more opportunities)
4. If successful, update Phase 2 variables
5. Run another 2 hours, confirm weak trend captures
6. Finally update Phase 3 for tuning

## Quick Copy-Paste Commands

If you have Railway CLI access, you can batch-update:

```bash
# This is informational - actual Railway dashboard update required
railway variables set STRATEGY_RSI_LONG_MIN 28.0
railway variables set STRATEGY_MIN_ADX 12.0
railway variables set STRATEGY_MIN_PROB 0.515
railway variables set STRATEGY_WEAK_TREND_MIN_ADX 16.0
railway variables set STRATEGY_WEAK_TREND_MIN_PROB_EDGE 0.006
railway variables set STRATEGY_WEAK_TREND_MIN_VOLUME_RATIO 0.60
```

## Verification

After deployment, check your first log line should show:

```
[SYSTEM] Strategy config | min_adx=12.0 rsi=[28.0,75.0] base_prob=0.515 weak_prob_edge=0.006 ...
```

If it still shows the old values, the env vars weren't updated or deployment didn't pick them up.

## Notes

- Environment variables on Railway persist across deployments
- No code re-push needed after updating env vars — just redeploy
- After all updates, your trading signal rate should return to normal (3-5x increase from zero)
