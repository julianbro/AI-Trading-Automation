# Bitunix Exchange Integration Guide

## Overview

This trading system now supports **Bitunix** exchange through a custom API integration. Since Bitunix is not natively supported by the CCXT library, we've implemented a custom client that wraps the Bitunix API.

## ⚠️ Important Notes

**This is a custom integration with the following considerations:**

1. **API Endpoints**: Based on Bitunix API documentation (https://openapidoc.bitunix.com/doc/common/introduction.html)
2. **Testing Required**: Some features may need adjustment based on actual API behavior
3. **Fallback Available**: If Bitunix doesn't work, you can easily switch back to any CCXT-supported exchange (e.g., Binance, Bybit)

## Setup Instructions

### 1. Get Bitunix API Credentials

1. Create an account at [Bitunix](https://www.bitunix.com)
2. Navigate to API Management
3. Create a new API key with the following permissions:
   - Read account information
   - Trade (for executing orders)
4. Save your API Key and Secret securely

### 2. Configure Environment Variables

Update your `.env` file:

```env
# Exchange Configuration
EXCHANGE_NAME=bitunix
EXCHANGE_API_KEY=your_bitunix_api_key
EXCHANGE_API_SECRET=your_bitunix_api_secret

# Paper Trading Mode (IMPORTANT: Start with true)
PAPER_TRADING=true
```

### 3. Test the Connection

Run the paper trading example to verify the connection:

```bash
python examples/paper_trading_example.py
```

## Supported Features

### ✅ Implemented Features

- **Market Data**
  - Fetch ticker prices
  - Fetch OHLCV (candlestick) data for multiple timeframes
  - Real-time price updates

- **Trading Operations** (when in live mode)
  - Market orders
  - Limit orders
  - Order cancellation
  - Order status queries

- **Account Management**
  - Balance queries
  - Position tracking (via paper trading simulation)

### 🔄 Sandbox/Testnet Mode

The Bitunix client automatically uses sandbox mode when `PAPER_TRADING=true`:
- API calls go to: `https://api-testnet.bitunix.com`
- No real money at risk
- Full functionality testing

When `PAPER_TRADING=false`:
- API calls go to: `https://api.bitunix.com`
- **REAL TRADING** - Use with caution!

## Timeframe Support

The following timeframes are supported:

| Standard | Bitunix API |
|----------|-------------|
| 1m       | 1           |
| 3m       | 3           |
| 5m       | 5           |
| 15m      | 15          |
| 30m      | 30          |
| 1h       | 60          |
| 2h       | 120         |
| 4h       | 240         |
| 6h       | 360         |
| 12h      | 720         |
| 1d       | 1D          |
| 1w       | 1W          |
| 1M       | 1M          |

## Symbol Format

Bitunix uses a different symbol format than some exchanges:

- **In Config**: Use standard format like `BTC/USDT`
- **API Translation**: Automatically converted to `BTCUSDT`

Examples:
- `BTC/USDT` → `BTCUSDT`
- `ETH/USDT` → `ETHUSDT`
- `SOL/USDT` → `SOLUSDT`

## Troubleshooting

### Problem: Connection Errors

**Solution**: Verify your API credentials and network connectivity

```python
# Test manually
from src.exchanges import BitunixClient

client = BitunixClient(
    api_key="your_key",
    api_secret="your_secret",
    sandbox=True
)

# Test connection
ticker = client.fetch_ticker("BTC/USDT")
print(f"Current BTC price: ${ticker['last']}")
```

### Problem: API Rate Limits

**Solution**: The client includes rate limiting, but if you encounter issues:
- Reduce the polling frequency in your trading cycle
- Increase `interval_seconds` in `run_continuous()`

### Problem: Invalid Signature Errors

**Solution**: Check that:
1. API key and secret are correct
2. System time is synchronized (signature uses timestamps)
3. No extra spaces in credentials

### Problem: Feature Not Working

**What to do**:
1. Check the logs in `trading_system.log` for detailed error messages
2. The system will log clear warnings when features are unavailable
3. Consider switching to a CCXT-supported exchange temporarily

## Switching Back to CCXT Exchange

If you need to switch to a different exchange (e.g., Binance):

1. Update `.env`:
```env
EXCHANGE_NAME=binance  # or bybit, bitget, etc.
```

2. The system will automatically detect and use CCXT
3. No code changes needed!

## API Endpoints Reference

The Bitunix client uses the following endpoints:

- **Market Data**
  - `GET /api/v1/market/ticker` - Current price
  - `GET /api/v1/market/kline` - Candlestick data

- **Trading** (requires authentication)
  - `POST /api/v1/order/create` - Create order
  - `DELETE /api/v1/order/cancel` - Cancel order
  - `GET /api/v1/order/query` - Query order status
  - `GET /api/v1/account/balance` - Get balance

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use paper trading first** - Always test with `PAPER_TRADING=true`
3. **Limit API permissions** - Only grant necessary permissions
4. **Monitor regularly** - Check logs and account activity
5. **Use IP whitelisting** if Bitunix supports it

## Support and Issues

If you encounter issues with Bitunix integration:

1. Check logs in `trading_system.log`
2. Enable DEBUG logging: Set `LOG_LEVEL=DEBUG` in `.env`
3. Report issues with:
   - Error messages from logs
   - Configuration (without API keys!)
   - Steps to reproduce

## Full Functionality Checklist

Use this checklist to verify Bitunix integration:

- [ ] Can fetch ticker prices
- [ ] Can fetch OHLCV data for all timeframes
- [ ] Can query account balance
- [ ] Can create market orders (paper trading)
- [ ] Can create limit orders (paper trading)
- [ ] Can cancel orders (paper trading)
- [ ] Can query order status
- [ ] All logs show clear error messages if something fails

**If any feature doesn't work**, the system is designed to:
1. Log a clear error message
2. Continue operating with available features
3. Not crash the entire trading system

## Example Usage

```python
from src.trading_system import TradingSystem

# Initialize with Bitunix (via .env configuration)
system = TradingSystem(
    symbol="BTC/USDT",
    timeframes=["1d", "4h", "15m", "5m"],
    account_balance=10000.0
)

# Run a single cycle
system.run_cycle()

# Or run continuously
system.run_continuous(interval_seconds=60)
```

## Comparison: Bitunix vs CCXT Exchanges

| Feature | Bitunix (Custom) | CCXT Exchanges |
|---------|------------------|----------------|
| Setup | Custom implementation | Built-in support |
| Market Data | ✅ Supported | ✅ Supported |
| Trading | ✅ Supported | ✅ Supported |
| Sandbox Mode | ✅ Available | ⚠️ Varies by exchange |
| Maintenance | May need updates | Auto-updated via CCXT |
| Reliability | Depends on API | Well-tested |

## Conclusion

The Bitunix integration is ready to use with paper trading. Test thoroughly before moving to live trading. If any issues arise, switching to a CCXT-supported exchange is straightforward.

**Remember**: Start with `PAPER_TRADING=true` and test all features!
