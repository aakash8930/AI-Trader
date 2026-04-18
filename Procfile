web: python -u main.py
train: python train_models.py --symbols BTC/USDT,ETH/USDT,SOL/USDT,AVAX/USDT,LINK/USDT,DOGE/USDT --candles 50000 --epochs 10
train-retrain: python train_models.py --symbols BTC/USDT,ETH/USDT,SOL/USDT,AVAX/USDT,LINK/USDT,DOGE/USDT --candles 100000 --epochs 15 --retrain
train-bnb: python train_models.py --symbols BNB/USDT --candles 100000 --epochs 15 --retrain
auto-train-start: bash scripts/train_and_start.sh
