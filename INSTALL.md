# Bybit Trading Bot - Installation Guide

## Quick Setup Guide

### 1. Install Dependencies
```bash
pip3 install telethon ccxt python-dotenv
```

### 2. Configure the Bot
Create `config.ini` with your credentials:

```ini
[TELEGRAM]
API_ID = YOUR_API_ID
API_HASH = YOUR_API_HASH
STRING_SESSION = YOUR_STRING_SESSION

[BYBIT]
API_KEY = YOUR_BYBIT_API_KEY
API_SECRET = YOUR_BYBIT_API_SECRET
LEVERAGE = 100
CAPITAL_PERCENTAGE = 2
DEFAULT_MARKET_TYPE = linear
```

### 3. Test the Bot
```bash
python3 test_bot.py
```

### 4. Run the Bot
```bash
python3 run_bot.py
```

## Supported Signal Format

```
📢 Trade Signal Detected!

📊 Symbol: LTCUSDT.P
🔁 Direction: LONG
📍 Entry Price: 87.798
🎯 Take Profit 1: 88.503
🎯 Take Profit 2: 90.2514
⛔ Stop Loss: 86.67
```

## Features

- ✅ Futures trading only (USDT Perpetual)
- ✅ 100x leverage
- ✅ 2% capital per trade
- ✅ Auto close at first target
- ✅ Stop loss and take profit
- ✅ Reads from all Telegram chats
- ✅ Arabic and English support
- ✅ Comprehensive logging

## Files Structure

```
├── main_bot.py           # Main bot (recommended)
├── run_bot.py           # Launcher script
├── bybit_api.py         # Bybit API interface
├── signal_parser.py     # Signal parser
├── config.ini           # Configuration file
├── test_bot.py          # Testing script
├── requirements.txt     # Dependencies
└── README.md           # Documentation
```

## Safety Notes

⚠️ **Warning**: Futures trading involves high risk. Use at your own risk.

- Start with small balance for testing
- Monitor the bot regularly
- Keep API keys secure
- Don't share your config.ini file

For detailed documentation, see the Arabic README.md file.

