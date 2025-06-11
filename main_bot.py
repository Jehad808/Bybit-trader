import logging
import re
from telethon import TelegramClient, events
from bybit_api import BybitAPI
import configparser
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, client: TelegramClient, bybit_api: BybitAPI, config: configparser.ConfigParser):
        self.client = client
        self.bybit_api = bybit_api
        self.config = config
        self.executed_trades = 0
        self.failed_trades = 0
        self.start_time = datetime.now()
        self.last_signal_time = None
        self.client.add_event_handler(self.handle_message, events.NewMessage())

    def parse_signal(self, message: str) -> dict:
        try:
            pattern = r"Symbol: (\w+)\s+Direction: (\w+)\s+Entry Price: ([\d.]+)\s+Take Profit(?: 1)?: ([\d.]+)\s*(?:Take Profit 2: ([\d.]+))?\s+Stop Loss: ([\d.]+)"
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'symbol': match.group(1),
                    'direction': match.group(2).upper(),
                    'entry_price': float(match.group(3)),
                    'take_profit': float(match.group(4)),
                    'take_profit_2': float(match.group(5)) if match.group(5) else None,
                    'stop_loss': float(match.group(6))
                }
            logger.warning("⚠️ تنسيق الإشارة غير صحيح")
            return None
        except Exception as e:
            logger.error(f"❌ خطأ في تحليل الإشارة: {e}")
            return None

    async def handle_message(self, event):
        message = event.message
        sender = await event.get_sender()
        logger.info(f"📨 رسالة من: {sender.username if sender.username else 'غير معروف'}")
        try:
            signal = self.parse_signal(message.text)
            if not signal:
                return
            symbol = signal['symbol']
            direction = signal['direction']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            positions = self.bybit_api.get_positions()
            formatted_symbol = self.bybit_api._format_symbol(symbol)
            for pos in positions:
                if pos['symbol'] == formatted_symbol:
                    logger.warning(f"⚠️ مركز مفتوح لـ {symbol}: {pos['side']}")
                    return
            result = self.bybit_api.open_position(symbol=symbol, direction=direction, entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit)
            if result['status'] == 'success':
                self.executed_trades += 1
                self.last_signal_time = datetime.now()
            else:
                self.failed_trades += 1
            logger.info(f"📈 الصفقات المنفذة: {self.executed_trades}")
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الإشارة: {e}")
            self.failed_trades += 1

    async def run(self):
        logger.info("🚀 البوت يعمل...")
        await self.client.run_until_disconnected()
