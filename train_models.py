#!/usr/bin/env python3
"""
Train or retrain direction models for all configured trading symbols.

Usage:
    # Train all default symbols
    python train_models.py

    # Train specific symbols
    python train_models.py --symbols BTC/USDT,ETH/USDT,SOL/USDT

    # Retrain (will overwrite existing models)
    python train_models.py --retrain

    # Exclude specific symbols
    python train_models.py --exclude BNB/USDT,MATIC/USDT

    # Set custom candle count
    python train_models.py --candles 75000

Examples:
    # Retrain BNB model that was failing (F1=0)
    python train_models.py --symbols BNB/USDT --retrain --candles 100000

    # Train new symbols after deployment
    python train_models.py --symbols XLM/USDT,ATOM/USDT --candles 50000

    # Full retrain with extended history
    python train_models.py --retrain --candles 100000
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

import torch
import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data.fetcher import MarketDataFetcher
from features.technicals import compute_core_features
from models.model_identity import MODEL_NAME, MODEL_VERSION


# =========================================================================
# TRAINING CONFIGURATION
# =========================================================================
class TrainingConfig:
    """Flexible training configuration with CLI override support."""

    def __init__(self, timeframe="15m", candles=50000, horizon=12,
                 stop_atr_mult=2.0, take_atr_mult=3.0,
                 epochs=10, batch_size=256, lr=1e-3, train_split=0.8,
                 early_stopping_patience=3, purge_bars=10):
        self.timeframe = timeframe
        self.candles = candles
        self.horizon = horizon
        self.stop_atr_mult = stop_atr_mult
        self.take_atr_mult = take_atr_mult
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.train_split = train_split
        self.early_stopping_patience = early_stopping_patience
        self.purge_bars = purge_bars

    def __repr__(self):
        return (f"TrainingConfig(timeframe={self.timeframe}, candles={self.candles}, "
                f"epochs={self.epochs}, lr={self.lr}, batch_size={self.batch_size})")


DEFAULT_CONFIG = TrainingConfig()

FEATURE_COLUMNS = [
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "dist_ema200",
    "ema_fast_slope",
    "rsi",
    "rsi_delta",
    "ret",
    "vol",
    "volume_zscore",
    "atr_pct",
    "adx",
    "breakout_strength",
]

DEFAULT_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "DOGE/USDT",
]


# =========================================================================
# MODEL ARCHITECTURE
# =========================================================================
class DirectionNet(torch.nn.Module):
    """Neural network for binary direction prediction (long/short)."""

    def __init__(self, input_dim: int):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_dim, 32),
            torch.nn.ReLU(),
            torch.nn.Linear(32, 16),
            torch.nn.ReLU(),
            torch.nn.Linear(16, 1),
            torch.nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x)


# =========================================================================
# DATA PREPARATION
# =========================================================================
def prepare_data(symbol: str, config: TrainingConfig, fetcher: MarketDataFetcher):
    """Fetch and prepare training data for a symbol."""
    print(f"  [DATA] Fetching {config.candles} {config.timeframe} candles for {symbol}...")

    raw_fetch_limit = max(config.candles + 300, 500)
    df = fetcher.fetch_ohlcv(symbol, config.timeframe, limit=raw_fetch_limit)

    if df is None or df.empty or len(df) < config.candles:
        print(f"    ❌ Insufficient data: got {len(df) if df is not None else 0}, need {config.candles}")
        return None

    print(f"  [FEATURES] Computing technical indicators...")
    df = compute_core_features(df)
    df = df.dropna().copy()

    if len(df) < config.candles:
        print(f"    ❌ After feature computation: {len(df)} rows (need {config.candles})")
        return None

    # Use only the required candles
    df = df.iloc[-config.candles:].copy()

    # Target: ATR-based labeling
    print(f"  [LABELING] Creating ATR-based target labels...")
    high_col = "high" if "high" in df.columns else df.columns[2]
    low_col = "low" if "low" in df.columns else df.columns[3]
    close_col = "close" if "close" in df.columns else df.columns[4]

    df["future_high"] = df[high_col].shift(-config.horizon)
    df["future_low"] = df[low_col].shift(-config.horizon)

    atr_pct = df["atr_pct"].iloc[:-config.horizon].values
    stop_dist = atr_pct * config.stop_atr_mult
    take_dist = atr_pct * config.take_atr_mult

    close_prices = df[close_col].iloc[:-config.horizon].values
    future_highs = df["future_high"].iloc[:-config.horizon].values
    future_lows = df["future_low"].iloc[:-config.horizon].values

    # Long signal: future high crosses take profit level
    df["target"] = (future_highs >= close_prices * (1 + take_dist)).astype(int)

    # Leakage protection: remove last N candles (incomplete forward-looking window)
    df = df.iloc[:-config.purge_bars].copy()

    # Prepare feature matrix
    X = df[FEATURE_COLUMNS].values
    y = df["target"].values

    print(f"  [DATA READY] {len(X)} samples, {X.shape[1]} features, "
          f"class balance: {(y == 1).sum()}/{len(y)}")

    return {"X": X, "y": y, "symbol": symbol, "n_features": X.shape[1]}


# =========================================================================
# MODEL TRAINING
# =========================================================================
class EarlyStopping:
    """Early stopping with patience."""

    def __init__(self, patience=3, min_delta=1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float('inf')
        self.counter = 0
        self.best_state = None

    def __call__(self, val_loss):
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
            return False  # continue training
        else:
            self.counter += 1
            return self.counter >= self.patience  # stop if patience exceeded


def train_model(data: dict, config: TrainingConfig, device: str = "cpu"):
    """Train a direction model on prepared data."""
    X, y = data["X"], data["y"]
    symbol = data["symbol"]
    n_features = data["n_features"]

    print(f"  [TRAIN] Initializing model ({n_features} input features)...")
    model = DirectionNet(n_features).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)
    criterion = torch.nn.BCELoss()

    # Class weighting for imbalanced data
    class_counts = np.bincount(y)
    class_weights = torch.tensor(
        1.0 / (class_counts / len(y)),
        dtype=torch.float32,
        device=device
    )

    # Data split
    split_idx = int(len(X) * config.train_split)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    print(f"  [SPLIT] Train={len(X_train)}, Val={len(X_val)}")

    # DataLoader with weighted sampling
    X_train_t = torch.tensor(X_train, dtype=torch.float32, device=device)
    y_train_t = torch.tensor(y_train, dtype=torch.float32, device=device).unsqueeze(1)

    weights = class_weights[y_train]
    sampler = WeightedRandomSampler(weights, len(weights), replacement=True)
    train_loader = DataLoader(
        TensorDataset(X_train_t, y_train_t),
        batch_size=config.batch_size,
        sampler=sampler,
        drop_last=True
    )

    X_val_t = torch.tensor(X_val, dtype=torch.float32, device=device)
    y_val_t = torch.tensor(y_val, dtype=torch.float32, device=device).unsqueeze(1)

    early_stop = EarlyStopping(patience=config.early_stopping_patience)

    print(f"  [EPOCHS] Training for up to {config.epochs} epochs...")
    for epoch in range(config.epochs):
        # Train
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validate
        model.eval()
        with torch.no_grad():
            val_logits = model(X_val_t)
            val_loss = criterion(val_logits, y_val_t).item()

        print(f"    Epoch {epoch+1:2d}/{config.epochs} | "
              f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

        if early_stop(val_loss):
            print(f"    → Early stopping at epoch {epoch+1}")
            break

    return model, X_train, y_train, X_val, y_val


def evaluate_model(model, X_train, y_train, X_val, y_val, device: str = "cpu"):
    """Evaluate model performance."""
    model.eval()

    def predict_proba(X):
        X_t = torch.tensor(X, dtype=torch.float32, device=device)
        with torch.no_grad():
            return model(X_t).cpu().numpy().flatten()

    y_train_pred = (predict_proba(X_train) >= 0.5).astype(int)
    y_val_pred = (predict_proba(X_val) >= 0.5).astype(int)

    train_acc = accuracy_score(y_train, y_train_pred)
    train_prec = precision_score(y_train, y_train_pred, zero_division=0)
    train_rec = recall_score(y_train, y_train_pred, zero_division=0)
    train_f1 = f1_score(y_train, y_train_pred, zero_division=0)

    val_acc = accuracy_score(y_val, y_val_pred)
    val_prec = precision_score(y_val, y_val_pred, zero_division=0)
    val_rec = recall_score(y_val, y_val_pred, zero_division=0)
    val_f1 = f1_score(y_val, y_val_pred, zero_division=0)

    return {
        "train": {"acc": train_acc, "prec": train_prec, "rec": train_rec, "f1": train_f1},
        "val": {"acc": val_acc, "prec": val_prec, "rec": val_rec, "f1": val_f1}
    }


def compute_long_threshold(y_train, model, X_train, device: str = "cpu"):
    """Compute optimal long threshold from training data."""
    model.eval()
    X_train_t = torch.tensor(X_train, dtype=torch.float32, device=device)

    with torch.no_grad():
        probs = model(X_train_t).cpu().numpy().flatten()

    positives = probs[y_train == 1]
    if len(positives) > 0:
        threshold = float(np.percentile(positives, 50))
    else:
        threshold = 0.50

    return max(0.40, min(0.60, threshold))


# =========================================================================
# MODEL PERSISTENCE
# =========================================================================
def save_model(model, symbol: str, scaler: StandardScaler, threshold: float, config: TrainingConfig):
    """Save trained model and metadata."""
    model_dir = Path("models") / symbol.replace("/", "_")
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    torch.save(model.state_dict(), model_dir / "model.pt")
    print(f"    ✓ Model saved: {model_dir}/model.pt")

    # Save scaler
    joblib.dump(scaler, model_dir / "scaler.save")
    print(f"    ✓ Scaler saved: {model_dir}/scaler.save")

    # Save metadata
    metadata = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "symbol": symbol,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_config": {
            "timeframe": config.timeframe,
            "candles": config.candles,
            "horizon": config.horizon,
            "epochs": config.epochs,
            "batch_size": config.batch_size,
        },
        "long_threshold": threshold,
        "feature_columns": FEATURE_COLUMNS,
    }

    with open(model_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"    ✓ Metadata saved: {model_dir}/metadata.json")


def load_or_create_scaler(X_train, symbol: str):
    """Load existing scaler or create new one."""
    model_dir = Path("models") / symbol.replace("/", "_")
    scaler_path = model_dir / "scaler.save"

    if scaler_path.exists():
        scaler = joblib.load(scaler_path)
        print(f"    ✓ Loaded existing scaler")
        return scaler

    scaler = StandardScaler()
    scaler.fit(X_train)
    return scaler


# =========================================================================
# MAIN TRAINING LOOP
# =========================================================================
def train_symbols(symbols: list, config: TrainingConfig, retrain: bool = False):
    """Train models for multiple symbols."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n🤖 Training Models (device={device})\n")
    print(f"Config: {config}")
    print(f"Symbols: {symbols}")
    print(f"Retrain: {retrain}\n")

    fetcher = MarketDataFetcher(exchange_name="binance")
    results = {}

    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"Training: {symbol}")
        print(f"{'='*70}")

        try:
            # Data preparation
            data = prepare_data(symbol, config, fetcher)
            if data is None:
                print(f"❌ Failed to prepare data for {symbol}\n")
                results[symbol] = {"status": "failed", "reason": "data_preparation"}
                continue

            # Feature scaling
            scaler = load_or_create_scaler(data["X"], symbol)
            X_scaled = scaler.transform(data["X"])

            # Model training
            model, X_train, y_train, X_val, y_val = train_model(
                {**data, "X": X_scaled},
                config,
                device=device
            )

            # Evaluation
            metrics = evaluate_model(model, X_train, y_train, X_val, y_val, device=device)
            print(f"\n  [METRICS]")
            print(f"    Train: F1={metrics['train']['f1']:.4f}, "
                  f"Prec={metrics['train']['prec']:.4f}, "
                  f"Rec={metrics['train']['rec']:.4f}")
            print(f"    Val:   F1={metrics['val']['f1']:.4f}, "
                  f"Prec={metrics['val']['prec']:.4f}, "
                  f"Rec={metrics['val']['rec']:.4f}")

            # Threshold computation
            threshold = compute_long_threshold(y_train, model, X_train, device=device)
            print(f"  [THRESHOLD] Long threshold computed: {threshold:.4f}")

            # Save model
            print(f"  [SAVE]")
            save_model(model, symbol, scaler, threshold, config)

            results[symbol] = {
                "status": "success",
                "metrics": metrics,
                "threshold": threshold
            }

            print(f"✅ {symbol} trained successfully\n")

        except Exception as e:
            print(f"❌ Error training {symbol}: {e}\n")
            results[symbol] = {"status": "failed", "reason": str(e)}

    return results


# =========================================================================
# CLI
# =========================================================================
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated list of symbols (default: all defaults)"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default=None,
        help="Comma-separated list of symbols to exclude"
    )
    parser.add_argument(
        "--candles",
        type=int,
        default=50000,
        help="Number of candles to train on (default: 50000)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Number of training epochs (default: 10)"
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Retrain existing models (overwrite)"
    )

    args = parser.parse_args()

    # Determine symbols to train
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        symbols = DEFAULT_SYMBOLS.copy()

    # Apply exclusions
    if args.exclude:
        excluded = {s.strip().upper() for s in args.exclude.split(",") if s.strip()}
        symbols = [s for s in symbols if s not in excluded]

    # Create config
    config = TrainingConfig(candles=args.candles, epochs=args.epochs)

    # Train
    results = train_symbols(symbols, config, retrain=args.retrain)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    successful = sum(1 for r in results.values() if r["status"] == "success")
    failed = sum(1 for r in results.values() if r["status"] == "failed")
    print(f"Total: {len(results)} | Success: {successful} | Failed: {failed}")
    for symbol, result in results.items():
        status_icon = "✅" if result["status"] == "success" else "❌"
        if result["status"] == "success":
            f1 = result["metrics"]["val"]["f1"]
            print(f"{status_icon} {symbol:15} | Val F1={f1:.4f} | Threshold={result['threshold']:.4f}")
        else:
            print(f"{status_icon} {symbol:15} | {result['reason']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
