#!/bin/bash
# scripts/train_and_start.sh
#
# Auto-training startup script for Railway
# Runs model training, then starts the trading system
#
# Usage:
#   - Set in Railway as main command or cron job
#   - To train on every deploy: update Railway start command to use this script

set -e

echo "🤖 [STARTUP] Auto-Training + Trading System"
echo "=============================================="

# Check if we should skip training
if [ "$SKIP_TRAINING" = "true" ]; then
    echo "⏭️  Training skipped (SKIP_TRAINING=true)"
else
    echo "📊 [PHASE 1] Running model training..."

    # Get training config from environment
    TRAIN_CANDLES=${TRAIN_CANDLES:-50000}
    TRAIN_EPOCHS=${TRAIN_EPOCHS:-10}
    TRAIN_SYMBOLS=${TRAIN_SYMBOLS:-"BTC/USDT,ETH/USDT,SOL/USDT,AVAX/USDT,LINK/USDT,DOGE/USDT"}
    TRAIN_RETRAIN=${TRAIN_RETRAIN:-false}

    echo "   Config:"
    echo "     Symbols: $TRAIN_SYMBOLS"
    echo "     Candles: $TRAIN_CANDLES"
    echo "     Epochs: $TRAIN_EPOCHS"
    echo "     Retrain: $TRAIN_RETRAIN"

    # Run training
    if [ "$TRAIN_RETRAIN" = "true" ]; then
        python train_models.py \
            --symbols "$TRAIN_SYMBOLS" \
            --candles "$TRAIN_CANDLES" \
            --epochs "$TRAIN_EPOCHS" \
            --retrain
    else
        python train_models.py \
            --symbols "$TRAIN_SYMBOLS" \
            --candles "$TRAIN_CANDLES" \
            --epochs "$TRAIN_EPOCHS"
    fi

    if [ $? -eq 0 ]; then
        echo "✅ Training completed successfully"
    else
        echo "❌ Training failed!"
        if [ "$TRAINING_FAILURE_MODE" = "skip" ]; then
            echo "⚠️  Continuing to start trading system (TRAINING_FAILURE_MODE=skip)"
        else
            echo "Aborting startup"
            exit 1
        fi
    fi
fi

echo ""
echo "🚀 [PHASE 2] Starting trading system..."
echo "=============================================="

# Start the main trading system
python main.py
