# Auto-Training Setup for Railway

## Quick Start: Enable Auto-Training on Deployment

Railway deployment now supports automatic model training. Choose your option:

### Option 1: Auto-Train on Every Deployment (Recommended for Development)

Update your Railway **start command** to:

```bash
bash scripts/train_and_start.sh
```

This will:
1. Train all models (50k candles, 10 epochs)
2. Start trading system

### Option 2: Train Only (No Trading)

Run once to train models:

```bash
python train_models.py --symbols BTC/USDT,ETH/USDT,SOL/USDT,AVAX/USDT,LINK/USDT,DOGE/USDT --candles 50000 --epochs 10
```

Then set main command back to: `python main.py`

### Option 3: Full Retrain (Heavy)

For periodic full retraining:

```bash
python train_models.py --retrain --candles 100000 --epochs 15
```

---

## Railway Environment Variables for Training

Add these to Railway **Variables** section:

```
TRAIN_CANDLES=50000          # Number of candles to train on
TRAIN_EPOCHS=10              # Epochs per symbol
TRAIN_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,AVAX/USDT,LINK/USDT,DOGE/USDT
TRAIN_RETRAIN=false          # Set true to retrain existing models
SKIP_TRAINING=false          # Set true to skip training on startup
TRAINING_FAILURE_MODE=fail   # 'fail' = abort on error, 'skip' = continue anyway
```

---

## Process Types (Procfile)

Available processes in Procfile:

```
web                 → python -u main.py
                    (Main trading system)

train               → Default training process
                    (50k candles, 10 epochs)

train-retrain       → Heavy retrain
                    (100k candles, 15 epochs, overwrites models)

train-bnb           → Retrain BNB only
                    (Fix F1=0 issue)

auto-train-start    → Train then start trading
                    (Uses TRAIN_* env vars)
```

---

## How to Use in Railway Dashboard

### Scenario 1: Normal Trading (No Auto-Training)

1. Go to **Settings → Start Command**
2. Set: `python main.py`
3. Deploy

### Scenario 2: Auto-Train on Every Deploy

1. Go to **Settings → Start Command**
2. Set: `bash scripts/train_and_start.sh`
3. Deploy → Training runs, then trading starts

### Scenario 3: Manual Training Run

1. Go to **Deployments → New Deployment**
2. Set override command: `python train_models.py --symbols BTC/USDT,ETH/USDT --retrain --candles 75000`
3. Deploy (one-time, doesn't change main command)

### Scenario 4: Fix BNB Model Only

1. Manual deployment command: `python train_models.py --symbols BNB/USDT --retrain --candles 100000`
2. Monitor logs for completion
3. Redeploy with main command after training succeeds

---

## Environment Variable Configuration

### For Auto-Training Startup

Add to Railway Variables:

```
SKIP_TRAINING=false
TRAIN_CANDLES=50000
TRAIN_EPOCHS=10
TRAIN_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,AVAX/USDT,LINK/USDT,DOGE/USDT
TRAINING_FAILURE_MODE=fail
```

### For Quick/Heavy Training

Quick (20 min):
```
TRAIN_CANDLES=30000
TRAIN_EPOCHS=5
```

Heavy (1+ hour):
```
TRAIN_CANDLES=150000
TRAIN_EPOCHS=20
TRAIN_RETRAIN=true
```

---

## Monitoring Training

Check logs during training:

```
🤖 [STARTUP] Auto-Training + Trading System
  [DATA] Fetching 50000 15m candles for BTC/USDT...
  [FEATURES] Computing technical indicators...
  [LABELING] Creating ATR-based target labels...
  [DATA READY] 49000 samples, 13 features, class balance: 12340/49000
  [TRAIN] Initializing model...
    Epoch  1/10 | Train Loss: 0.6932 | Val Loss: 0.6847
    Epoch  2/10 | Train Loss: 0.5123 | Val Loss: 0.5034
    ...
  [METRICS]
    Train: F1=0.6234, Prec=0.6100, Rec=0.6400
    Val:   F1=0.5821, Prec=0.5700, Rec=0.6050
  [SAVE]
    ✓ Model saved
    ✓ Scaler saved
    ✓ Metadata saved
✅ BTC/USDT trained successfully
```

---

## Troubleshooting

### Training Hangs/Timeout

- Reduce `TRAIN_CANDLES` (default 50000 → try 30000)
- Reduce `TRAIN_EPOCHS` (default 10 → try 5)
- Check Railway timeout settings (default 120s)

### Training Fails, But Want Trading to Continue

```
TRAINING_FAILURE_MODE=skip
```

This allows trading to start even if training fails.

### Skip Training Temporarily

```
SKIP_TRAINING=true
```

Then redeploy with `SKIP_TRAINING=false` to re-enable.

### Check What Models Exist

SSH into Railway and run:
```bash
ls -la models/*/metadata.json
```

---

## Integration with Config Fix

After updating Railway env vars (from `RAILWAY_VARS_UPDATE_REQUIRED.md`):

1. Deploy with `bash scripts/train_and_start.sh`
2. Training will use latest models
3. System starts with synced config parameters
4. Expect 3-5x more trades in shadow mode

---

## Advanced: Scheduled Training (Cron)

To retrain weekly, you'd need:
1. Railway background job (not directly supported)
2. Or external scheduler (Render, AWS Lambda, etc.)
3. Or manual redeploy with override command weekly

Current recommendation: Manual retrain every 7 days using override command.

---

## Quick Reference

| Task | Command | Time |
|------|---------|------|
| Normal trading | `python main.py` | N/A |
| Auto-train + trade | `bash scripts/train_and_start.sh` | 20-30 min |
| Quick train | `python train_models.py` | 15-20 min |
| Heavy retrain | `python train_models.py --retrain --candles 100000` | 60+ min |
| Train BNB only | `python train_models.py --symbols BNB/USDT --retrain` | 10-15 min |

