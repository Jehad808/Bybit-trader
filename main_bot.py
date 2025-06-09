import logging
import asyncio
import signal
import sys
from datetime import datetime
from typing import Dict, Any
import configparser
from telethon import TelegramClient, events
from bybit_api import BybitTradingAPI
from signal_parser import TradingSignalParser

# إعداد نظام التسجيل المحسن
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    """بوت التداول الرئيسي"""
    
    def __init__(self, config_file: str = "config.ini"):
        """تهيئة البوت"""
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # إحصائيات البوت
        self.stats = {
            'start_time': datetime.now(),
            'signals_received': 0,
            'signals_processed': 0,
            'trades_executed': 0,
            'trades_failed': 0,
            'last_signal_time': None
        }
        
        # تهيئة المكونات
        self._init_telegram()
        self._init_trading_api()
        self._init_signal_parser()
        
        # إعداد معالج الإشارات للإغلاق الآمن
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = False
        
    def _init_telegram(self):
        """تهيئة عميل Telegram"""
        try:
            api_id = int(self.config["TELEGRAM"]["API_ID"])
            api_hash = self.config["TELEGRAM"]["API_HASH"]
            string_session = self.config["TELEGRAM"]["STRING_SESSION"]
            self.telegram_client = TelegramClient(
                string_session,
                api_id,
                api_hash
            )      
            logger.info("✅ تم تهيئة عميل Telegram")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة Telegram: {e}")
            raise
    
    def _init_trading_api(self):
        """تهيئة واجهة التداول"""
        try:
            self.trading_api = BybitTradingAPI(self.config_file)
            logger.info("✅ تم تهيئة واجهة التداول")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة واجهة التداول: {e}")
            raise
    
    def _init_signal_parser(self):
        """تهيئة محلل الإشارات"""
        try:
            self.signal_parser = TradingSignalParser()
            logger.info("✅ تم تهيئة محلل الإشارات")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة محلل الإشارات: {e}")
            raise
    
    def _signal_handler(self, signum, frame):
        """معالج إشارات النظام للإغلاق الآمن"""
        logger.info(f"🛑 تم استلام إشارة إيقاف ({signum})")
        self.running = False
    
    async def _handle_message(self, event):
        """معالج الرسائل الواردة"""
        try:
            # تحديث الإحصائيات
            self.stats['signals_received'] += 1
            
            if not event.message.text:
                return
            
            # تحليل الإشارة
            signal_data = self.signal_parser.parse_signal(event.message.text)
            
            if not signal_data:
                return  # ليست إشارة تداول
            
            # التحقق من صحة الإشارة
            if not self.signal_parser.validate_signal(signal_data):
                logger.warning("⚠️ إشارة غير صالحة، تم تجاهلها")
                return
            
            # تحديث الإحصائيات
            self.stats['signals_processed'] += 1
            self.stats['last_signal_time'] = datetime.now()
            
            # معلومات المصدر
            chat_info = await self._get_chat_info(event)
            
            logger.info("=" * 60)
            logger.info(f"📩 إشارة تداول جديدة من: {chat_info}")
            logger.info(f"📊 الرمز: {signal_data['symbol']}")
            logger.info(f"🔄 الاتجاه: {signal_data['direction']}")
            logger.info(f"💰 سعر الدخول: {signal_data['entry_price']}")
            logger.info(f"🎯 الهدف الأول: {signal_data['take_profit_1']}")
            logger.info(f"⛔ وقف الخسارة: {signal_data['stop_loss']}")
            
            # تنفيذ الصفقة
            await self._execute_trade(signal_data)
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرسالة: {e}")
    
    async def _get_chat_info(self, event) -> str:
        """الحصول على معلومات المحادثة"""
        try:
            if event.chat:
                if hasattr(event.chat, 'title') and event.chat.title:
                    return event.chat.title
                elif hasattr(event.chat, 'username') and event.chat.username:
                    return f"@{event.chat.username}"
                else:
                    return f"Chat ID: {event.chat_id}"
            else:
                return "محادثة خاصة"
        except:
            return "مصدر غير معروف"
    
    async def _execute_trade(self, signal_data: Dict[str, Any]):
        """تنفيذ الصفقة"""
        try:
            logger.info("🚀 بدء تنفيذ الصفقة...")
            
            # تنفيذ الصفقة
            order_id = self.trading_api.open_position(
                symbol=signal_data['symbol'],
                direction=signal_data['direction'],
                entry_price=signal_data['entry_price'],
                take_profit=signal_data['take_profit_1'],  # نستخدم الهدف الأول فقط
                stop_loss=signal_data['stop_loss']
            )
            
            if order_id:
                self.stats['trades_executed'] += 1
                logger.info(f"✅ تم تنفيذ الصفقة بنجاح - Order ID: {order_id}")
                logger.info(f"📈 إجمالي الصفقات المنفذة: {self.stats['trades_executed']}")
            else:
                self.stats['trades_failed'] += 1
                logger.error("❌ فشل في تنفيذ الصفقة")
                
        except Exception as e:
            self.stats['trades_failed'] += 1
            logger.error(f"❌ خطأ في تنفيذ الصفقة: {e}")
    
    def _print_stats(self):
        """طباعة إحصائيات البوت"""
        uptime = datetime.now() - self.stats['start_time']
        
        logger.info("=" * 60)
        logger.info("📊 إحصائيات البوت:")
        logger.info(f"⏱️ وقت التشغيل: {uptime}")
        logger.info(f"📨 الرسائل المستلمة: {self.stats['signals_received']}")
        logger.info(f"🔍 الإشارات المعالجة: {self.stats['signals_processed']}")
        logger.info(f"✅ الصفقات المنفذة: {self.stats['trades_executed']}")
        logger.info(f"❌ الصفقات الفاشلة: {self.stats['trades_failed']}")
        if self.stats['last_signal_time']:
            logger.info(f"🕐 آخر إشارة: {self.stats['last_signal_time']}")
        logger.info("=" * 60)
    
    async def start(self):
        """بدء تشغيل البوت"""
        try:
            logger.info("🚀 بدء تشغيل بوت التداول...")
            logger.info(f"⚙️ الرافعة المالية: {self.trading_api.leverage}x")
            logger.info(f"💰 نسبة رأس المال: {self.trading_api.capital_percentage}%")
            logger.info("📡 البوت يستقبل الرسائل من جميع المحادثات...")
            
            # تسجيل معالج الرسائل
            @self.telegram_client.on(events.NewMessage)
            async def message_handler(event):
                await self._handle_message(event)
            
            # بدء عميل Telegram
            await self.telegram_client.start()
            
            self.running = True
            logger.info("✅ البوت يعمل الآن...")
            
            # حلقة التشغيل الرئيسية
            while self.running:
                await asyncio.sleep(1)
            
            logger.info("🛑 إيقاف البوت...")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تشغيل البوت: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def _cleanup(self):
        """تنظيف الموارد"""
        try:
            self._print_stats()
            
            if hasattr(self, 'telegram_client'):
                await self.telegram_client.disconnect()
                logger.info("✅ تم قطع الاتصال مع Telegram")
            
            logger.info("✅ تم إيقاف البوت بأمان")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الموارد: {e}")

async def main():
    """الدالة الرئيسية"""
    try:
        # إنشاء وتشغيل البوت
        bot = TradingBot()
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("🛑 تم إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

