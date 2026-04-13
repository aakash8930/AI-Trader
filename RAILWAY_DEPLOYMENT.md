# Railway App Deployment Guide

## Prerequisites

- Railway.app account
- GitHub repository connected to Railway
- Database (Neon PostgreSQL recommended)
- CCXT-compatible exchange API keys (Binance, etc.)

## Environment Variables Required

Before deploying, ensure these environment variables are set in Railway:

### Database
- `DATABASE_URL` - PostgreSQL connection string (e.g., from Neon)

### Trading Configuration
- `TRADING_MODE` - `shadow` (test) or `live` (real trading)
- `TRADING_TIMEFRAME` - Timeframe for analysis (e.g., `15m`, `1h`)
- `LOOKBACK_BARS` - Number of historical bars to analyze (e.g., `300`)
- `LOOP_SLEEP_SECONDS` - Sleep time between iterations (e.g., `20`)

### Trading Symbols & Strategy
- `TRADING_SYMBOLS` - Comma-separated symbols (e.g., `BTC/USDT,ETH/USDT`)
- `EXCLUDED_SYMBOLS` - Symbols to exclude (optional)
- `ENTRY_COOLDOWN_MINUTES` - Cooldown between entries
- `MAX_ACTIVE_POSITIONS` - Maximum concurrent positions
- `PAPER_STARTING_BALANCE_USDT` - Starting balance for shadow mode

### Exchange Configuration
- `EXCHANGE_NAME` - Primary exchange (e.g., `binance`)
- Exchange API credentials (if using credentials-based auth)

### Model Configuration
- `REQUIRE_MODEL_QUALITY` - `true`/`false` to validate model performance
- `MIN_MODEL_VAL_F1` - Minimum F1 score threshold (e.g., `0.10`)
- `MIN_MODEL_VAL_PRECISION` - Minimum precision threshold

## Region Configuration

⚠️ **Asia Server Deployment**: This project is configured to deploy on Railway's Singapore (ap-southeast-1) region for optimal latency with crypto exchanges.

- **Region**: `ap-southeast-1` (Singapore, Asia)
- **Benefits**: Lower latency to Binance/CCXT exchanges, faster order execution
- To change regions: Update `railway.json` → `deploy.region` field

Available Railway regions:
- `us-west-1` (Los Angeles)
- `us-east-1` (Virginia)
- `eu-west-1` (Ireland)
- `ap-southeast-1` (Singapore) ← ✓ Configured

## Deployment Steps

### Option 1: Deploy from GitHub (Recommended)

1. Push your code to GitHub
2. Go to railway.app and create a new project
3. Select "Deploy from GitHub repo"
4. Choose this repository
5. **Select Region**: When creating the project, select **Singapore (ap-southeast-1)** for Asia deployment
6. Add PostgreSQL service:
   - Click "Add Service" → "Add from Marketplace" → "PostgreSQL"
   - **Also set region to Singapore**
7. Configure Environment Variables:
   - Add all required variables above
   - Set `DATABASE_URL` from the PostgreSQL service
8. Railway will automatically deploy and run the app in Asia region

### Option 2: Deploy with Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Link to existing Railway project (or create new)
railway link

# Add environment variables
railway variables set DATABASE_URL=your_database_url
railway variables set TRADING_MODE=shadow
# ... add other variables

# Deploy
railway up
```

### Option 3: Manual Docker Deployment

```bash
# Build the Docker image
docker build -t trading-ai:latest .

# Tag for Railway registry
docker tag trading-ai:latest registry.railway.app/your-project/trading-ai:latest

# Push to Railway
docker push registry.railway.app/your-project/trading-ai:latest
```

## Post-Deployment

### Monitor Logs
```bash
railway logs --tail -f
```

### Check Status
```bash
railway status
```

### Update Environment Variables
```bash
railway variables set KEY=value
```

## Important Notes

### Database Initialization
- Railway will automatically initialize the PostgreSQL schema on first run
- Ensure `psycopg2-binary` is in requirements.txt ✓

### Storage Persistence
- Railway containers are ephemeral. Consider:
  - Storing logs in the database instead of local files
  - Using a persistent volume for model files if needed

### Worker Process
- This app is configured as a **worker** (long-running background process)
- It will start automatically and keep running
- Monitor CPU/memory usage in Railway dashboard

### Scaling
- For multiple symbol strategies, Railway's single container should handle it
- Use redundancy: deploy to 2 replicas or regions if critical

## Troubleshooting

### App won't start
1. Check logs: `railway logs`
2. Verify all required environment variables are set
3. Test database connectivity: Check DATABASE_URL format

### Connection timeouts
- Check network policies in Railway
- Verify database firewall allows Railway IPs
- Try increasing connection timeout settings

### Out of memory
- Reduce LOOKBACK_BARS or number of TRADING_SYMBOLS
- Check for memory leaks in logs

## Sensitive Data

**DO NOT** commit `.env` file to git. Railway will handle environment variables securely.

All credentials (API keys, database passwords) should only exist in Railway's environment variables, never in code.

## Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [Railway CLI Reference](https://railway.app/docs/reference/cli)
- [Neon PostgreSQL Setup](https://docs.railway.app/guides/databases/neon)
