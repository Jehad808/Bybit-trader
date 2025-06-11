import logging
import re
from telethon import TelegramClient, events
from bybit_api import BybitAPI
import configparser
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingBot:
    """بوت تداول Bybit يعتمد على إشارات Telegram"""
    
    def __init__(self, client: TelegramClient, bybit_api: BybitAPI, config: configparser.ConfigParser):
        self.client = client
        self.bybit_api = bybit_api
        self.config = config
        self.executed_trades = 0
        self.failed_trades = 0
        self.start_time = datetime.now()
        self.last_signal_time = None
        
        logger.info("✅ تم تهيئة محلل الإشارات")
        
        # إعداد معالج الأحداث
        self.client.add_event_handler(self.handle_message, events.NewMessage())
    
    def parse_signal(self, message: str) -> dict:
        """تحليل إشارة التداول من نص الرسالة"""
        try:
            pattern = r"Symbol: (\w+)\s+Direction: (\w+)\s+Entry Price: ([\d.]+)\s+Take Profit(?: 1)?: ([\d.]+)\s*(?:Take Profit 2: ([\d.]+))?\s+Stop Loss: ([\d.]+)"
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                symbol = match.group(1)
                direction = match.group(2)
                entry_price = float(match.group(3))
                take_profit = float(match.group(4))
                take_profit_2 = float(match.group(5)) if match.group(5) else None
                stop_loss = float(match.group(6))
                
                return {
                    'symbol': symbol,
                    'direction': direction.upper(),
                    'entry_price': entry_price,
                    'take_profit': take_profit,
                    'take_profit_2': take_profit_2,
                    'stop_loss': stop_loss
                }
            else:
                logger.warning("⚠️ تنسيق الإشارة غير صحيح")
                return None
        except Exception as e:
            logger.error(f"❌ خطأ في تحليل الإشارة: {e}")
            return None

    async def handle_message(self, event):
        """معالجة الرسائل الواردة من Telegram"""
        message = event.message
        sender = await event.get_sender()
        logger.info(f"📨 رسالة جديدة من: {sender.username if sender.username else 'غير معروف'}")
        
        try:
            signal = self.parse_signal(message.text)
            if not signal:
                return
            
            symbol = signal['symbol']
            direction = signal['direction']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            
            logger.info(f"✅ تم تحليل إشارة بنجاح: {symbol} {direction} @ {entry_price}")
            logger.info(f"📊 الرمز: {symbol}")
            logger.info(f"🔄 الاتجاه: {direction}")
            logger.info(f"💰 سعر الدخول: {entry_price}")
            logger.info(f"🎯 الهدف: {take_profit}")
            logger.info(f"⛔ وقف الخسارة: {stop_loss}")
            
            # التحقق من وجود مركز مفتوح
            positions = self.bybit_api.get_positions()
            formatted_symbol = self.bybit_api._format_symbol(symbol)
            for pos in positions:
                if pos['symbol'] == formatted_symbol:
                    logger.warning(f"⚠️ مركز مفتوح بالفعل لـ {symbol}: {pos['side']}")
                    return
            
            logger.info("🚀 بدء تنفيذ الصفقة...")
            result = self.bybit_api.open_position(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            if result['status'] == 'success':
                logger.info("✅ تم تنفيذ الصفقة بنجاح")
                self.executed_trades += 1
                self.last_signal_time = datetime.now()
            else:
                logger.error(f"❌ فشل في تنفيذ الصفقة: {result['message']}")
                self.failed_trades += 1
            
            logger.info(f"📈 إجمالي الصفقات المنفذة: {self.executed_trades}")
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الإشارة: {e}")
            self.failed_trades += 1

    async def run(self):
        """تشغيل البوت"""
        logger.info("🚀 بدء تشغيل البوت...")
        logger.info("📡 البوت يستقبل الرسائل من جميع المحادثات...")
        await self.client.run_until_disconnected()
