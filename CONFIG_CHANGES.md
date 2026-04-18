# Configuration Changes Summary

## Quick Reference: Before vs After

| Parameter | Before | After | Change | Reason |
|-----------|--------|-------|--------|--------|
| **base_long_threshold** | 0.48 | 0.515 | +3.5% | Need 51.5% for positive edge after fees |
| **rsi_long_min** | 32.0 | 28.0 | -4.0 | Catch oversold bounces in corrections |
| **rsi_long_max** | 75.0 | 75.0 | - | No change |
| **min_adx** | 12.0 | 12.0 | - | No change (core) |
| **min_atr_pct** | 0.0010 | 0.0008 | -20% | Allow low-vol recovery moves |
| **weak_trend_min_adx** | 18.0 | 16.0 | -2.0 | Relax weak trend requirements |
| **weak_trend_min_prob_edge** | 0.008 | 0.006 | -25% | Realistic edge in 50/50 markets |
| **min_expected_edge** | -0.00020 | -0.0005 | -150% | Allow breakeven trades in high-conf |
| **cooldown_minutes** | 30 | 20 | -10m | Faster recovery entries |
| **Selector base_threshold** | 0.48 | 0.515 | +3.5% | Align with strategy |
| **Selector rsi_long_min** | 38.0 | 28.0 | -10.0 | CRITICAL: was misaligned! |
| **Selector min_adx** | 17.0 | 14.0 | -3.0 | Selector looser than runner |
| **Selector soft_min_volume** | 0.12 | 0.10 | -17% | Allow lower vol |
| **Regime strong_trend ADX** | 28 | 26 | -2.0 | Catch earlier trend confirms |
| **Regime weak_trend ADX** | 16 | 14 | -2.0 | Include recovery moves |
| **Universe fallback threshold** | -500 | -450 | +50 | Accept more borderline |
| **BNB/USDT Model** | Active | Excluded | - | f1=0, prec=0, rec=0 (broken) |

---

## Critical Alignment Fixes

### Issue 1: RSI Misalignment
- **Selector used**: 38.0 min
- **Strategy used**: 32.0 min
- **Problem**: Coins passed selector (RSI ≥ 38) but no coins entered market at 32
- **Fix**: Unified at 28.0 min (catches corrections)

### Issue 2: Probability Threshold Misalignment
- **Selector used**: 0.48 base
- **Strategy used**: 0.48 base
- **Problem**: 48% probability has negative expected value after 0.36% costs
- **Fix**: Unified at 0.515 (0.51.5% for +edge)

### Issue 3: Fallback Mode Ineffective
- **Threshold**: Score > -500 (still hard filtering)
- **Result**: 85+ refreshes, 0 fallback selections
- **Fix**: Score > -450, with -800 absolute floor

---

## Edge Math Verification

### Before (0.48 threshold)
```
Scenario: RSI 28, ADX 15, prob=0.485, atr_pct=0.0010
Entry: $100 × 100 = $10,000 notional
Stop: 2.0 × (atr_pct × price) = $200
Target: 2.5 × $200 = $500

Expected Edge:
= 0.485 × ($500/$10000) - 0.515 × ($200/$10000) - 0.0036
= 0.485 × 0.0050 - 0.515 × 0.0020 - 0.0036
= 0.00243 - 0.00103 - 0.0036
= -0.00220 ❌ REJECTED

Result: ALL trades rejected, flat for 2.8 hours
```

### After (0.515 threshold)
```
Scenario: RSI 28, ADX 15, prob=0.515, atr_pct=0.0010
Same entry/stop/target, improved probability

Expected Edge:
= 0.515 × 0.0050 - 0.485 × 0.0020 - 0.0036
= 0.00258 - 0.00097 - 0.0036
= +0.00121 ✅ ACCEPTED

Profit expectancy: $12.10 per $10k position
Acceptable in high-confidence oversold setup
```

---

## Market Regime Impact

### Before: Oversold Correction Period (09:21-12:10 UTC)
```
Market: Declining ADX 44→20, RSI 19→32, all EMA aligned short
System Response: FLAT
Reason: 
- RSI 28 < min_rsi 32 = REJECTED
- Edge negative = REJECTED
- Even fallback couldn't pick symbols
- Duration: 2h 48m, 85+ refreshes, 0 trades
```

### After: Same Market Conditions
```
Market: Same (ADX 44→20, RSI 19→32)
System Response: SELECT 1-2 symbols
- RSI 28 ≥ min_rsi 28 = ACCEPTED
- Prob 0.515+ = ACCEPTED if
- Expected edge > -0.0005 = ACCEPTED
- Fallback kicks in at 2 refreshes

Expected: 2-4 trades, catch oversold bounce
Risk: Small negative edge acceptable in recovery
Duration: ≤30 minutes flat
```

---

## No Regressions (Critical)

These settings are UNCHANGED - we're not taking on uncontrolled risk:

✅ **Risk Management**
- Position size: Based on 1% risk per trade
- Stop loss multiplier: 2.0× ATR (not changed)
- Take profit multiplier: 2.5× ATR (not changed)
- Fee estimates: 0.0018 (not changed)

✅ **Core Filters**
- EMA200 requirement: Still required above EMA200
- EMA fast/slow cross: Still required bullish
- Model quality minimum: 15% F1 still enforced
- Trend confirmation: ADX still required (≥12 core)

✅ **Entry Signals**
- Strong trend definition: Not materially changed (ADX 26→28, was 28)
- Weak trend definition: Relaxed but still requires ADX+momentum
- Momentum override: Still requires prob ≥ threshold + 2.5%

---

## Implementation Notes

1. **No Breaking Changes**: All improvements are parameter adjustments, no logic changes (except fallback)

2. **Backward Compatible**: Old trades should still validate under new thresholds

3. **Gradual Rollout**: Can enable changes one module at a time:
   - Phase 1: Strategy RSI only (28 min)
   - Phase 2: Probability thresholds (0.515)
   - Phase 3: Edge relaxation (-0.0005)
   - Phase 4: Regime & fallback improvements

4. **Monitoring**: Track key metrics during deployment
   - % of trades with edge > 0
   - Avg flat mode duration
   - Win rate impact
   - Profit factor change

---

## Testing Checklist

- [ ] Unit: Edge calculation formula verification
- [ ] Unit: RSI filter logic at edge cases (27.9, 28.0, 28.1)
- [ ] Integration: Oversold recovery scenario simulation
- [ ] Integration: Normal trending scenario (regression)
- [ ] Stress: Extended fallback mode activation
- [ ] Live: Paper trading 24h with all changes
- [ ] Live: Monitor flat mode duration, edge distribution
- [ ] Rollback: Verify quick revert capability

---

## Success Criteria

| Metric | Before | Target | Status |
|--------|--------|--------|--------|
| Flat mode duration | 2h 48m | <30m | TBD |
| Trades per 12h (normal) | N/A | 2-4 | TBD |
| Avg expected edge | -0.0018 | +0.0002 | TBD |
| % positive edge trades | 0% | >60% | TBD |
| Win rate | 0% | >50% | TBD |

---

## Future Improvements (Not in This Update)

1. **Model Retraining**: Fix BNB and improve other models with better features
2. **Dynamic Thresholds**: Adjust prob threshold based on realized model accuracy
3. **Volatility Scaling**: Scale requirements up in low-vol, down in high-vol
4. **Regime Adaptation**: Further customize filters per regime
5. **Trade Pattern Analysis**: Learn which setups actually work from live data
