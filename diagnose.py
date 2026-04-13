#!/usr/bin/env python3
"""
Railway deployment diagnostic.
Run this standalone to pinpoint where startup hangs.
"""
import sys
import os
import time
import traceback

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("[DIAG] === Railway Diagnostic ===", flush=True)
print(f"[DIAG] Python: {sys.version}", flush=True)
print(f"[DIAG] CWD: {os.getcwd()}", flush=True)

# ---- 1. Load env ----
print("[DIAG 1/7] Loading .env...", flush=True)
try:
    from config.env_loader import load_env_file
    load_env_file()
    print("[DIAG 1/7] ✓ .env loaded", flush=True)
except Exception as e:
    print(f"[DIAG 1/7] ✗ {e}", flush=True)
    traceback.print_exc()

# ---- 2. Load settings ----
print("[DIAG 2/7] Loading LiveSettings...", flush=True)
try:
    from config.live import LiveSettings
    settings = LiveSettings.from_env()
    print(f"[DIAG 2/7] ✓ mode={settings.mode}, symbols={settings.symbols}", flush=True)
print(f"[DIAG 2/7] full env check: {os.environ.get('TRADING_SYMBOLS', 'not set')}", flush=True)
except Exception as e:
    print(f"[DIAG 2/7] ✗ {e}", flush=True)
    traceback.print_exc()

# ---- 3. Test exchange connection ----
print("[DIAG 3/7] Testing exchange connection (Binance)...", flush=True)
try:
    from data.fetcher import MarketDataFetcher
    print(f"[DIAG 3/7] creating fetcher with timeout={settings.exchange_timeout_ms}ms...", flush=True)
    fetcher = MarketDataFetcher(
        exchange_name=settings.exchange_name,
        fallback_exchanges=settings.exchange_fallbacks,
        timeout_ms=settings.exchange_timeout_ms,
    )
    print(f"[DIAG 3/7] ✓ connected to {fetcher.exchange_name}", flush=True)
except Exception as e:
    print(f"[DIAG 3/7] ✗ {e}", flush=True)
    traceback.print_exc()
    print("[DIAG 3/7] Sleeping 5s then continuing...", flush=True)
    time.sleep(5)

# ---- 4. Test data fetch ----
print("[DIAG 4/7] Fetching BTC/USDT candle...", flush=True)
try:
    df = fetcher.fetch_ohlcv("BTC/USDT", "15m", limit=300)
    print(f"[DIAG 4/7] ✓ fetched {len(df)} rows", flush=True)
except Exception as e:
    print(f"[DIAG 4/7] ✗ {e}", flush=True)
    traceback.print_exc()

# ---- 5. Test model loading ----
print("[DIAG 5/7] Loading models...", flush=True)
try:
    from models.direction import DirectionModel
    for sym in settings.symbols[:3]:
        try:
            model = DirectionModel.for_symbol(sym)
            print(f"[DIAG 5/7] ✓ {sym} loaded (th={model.long_threshold:.2f})", flush=True)
        except FileNotFoundError:
            print(f"[DIAG 5/7] - {sym} no model file, skipping", flush=True)
        except Exception as e:
            print(f"[DIAG 5/7] - {sym} error: {e}", flush=True)
except Exception as e:
    print(f"[DIAG 5/7] ✗ {e}", flush=True)
    traceback.print_exc()

# ---- 6. Test feature computation ----
print("[DIAG 6/7] Testing feature computation...", flush=True)
try:
    from features.technicals import compute_core_features
    if 'df' in dir() and df is not None and len(df) > 5:
        features_df = compute_core_features(df)
        print(f"[DIAG 6/7] ✓ features computed: {list(features_df.columns[:5])}...", flush=True)
    else:
        print("[DIAG 6/7] - no data to compute features on", flush=True)
except Exception as e:
    print(f"[DIAG 6/7] ✗ {e}", flush=True)
    traceback.print_exc()

# ---- 7. Test imports ----
print("[DIAG 7/7] Final sanity check - importing main modules...", flush=True)
try:
    from execution.runner import TradingRunner
    from execution.multi_runner import MultiSymbolTradingSystem
    print("[DIAG 7/7] ✓ all modules imported successfully", flush=True)
except Exception as e:
    print(f"[DIAG 7/7] ✗ {e}", flush=True)
    traceback.print_exc()

print("[DIAG] === Diagnostic Complete ===", flush=True)
