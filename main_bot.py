import os
import sys
import logging
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Any
import configparser
from telethon import TelegramClient, events

# إضافة المجلد الحالي لمسار Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# استيراد الوحدات المحسنة
from bybit_api import BybitTradingAPI
from signal_parser import TradingSignalParser

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class EnhancedBybitTradingBot:
    """بوت التداول المحسن مع جميع الميزات المطلوبة"""
    
    def __init__(self, config_file: str = "config.ini"):
        """تهيئة البوت"""
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # إحصائيات البوت
        self.stats = {
            'start_time': datetime.now(),
            'messages_received': 0,
            'signals_processed': 0,
            'trades_executed': 0,
            'trades_failed': 0,
            'last_signal_time': None
        }
        
        # تهيئة المكونات
        self.telegram_client = None
        self.bybit_api = None
        self.signal_parser = None
        
        # حالة البوت
        self.is_running = False
        
        logger.info("🚀 بدء تشغيل بوت التداول Bybit المحسن")
        logger.info("=" * 60)

    def load_config(self) -> bool:
        """تحميل الإعدادات"""
        try:
            # التحقق من وجود الملف
            if not os.path.exists(self.config_file):
                logger.error(f"❌ ملف الإعدادات غير موجود: {self.config_file}")
                return False
            
            self.config.read(self.config_file)
            logger.info("✅ تم تحميل الإعدادات من config.ini")
            
            # التحقق من المتغيرات المطلوبة
            required_vars = {
                'TELEGRAM': ['API_ID', 'API_HASH', 'STRING_SESSION'],
                'BYBIT': ['API_KEY', 'API_SECRET']
            }
            
            for section, vars_list in required_vars.items():
                if not self.config.has_section(section):
                    logger.error(f"❌ قسم مفقود في الإعدادات: {section}")
                    return False
                
                for var in vars_list:
                    if not self.config.get(section, var, fallback=None):
                        # التحقق من متغيرات البيئة
                        env_var = f"{section}_{var}"
                        if not os.getenv(env_var):
                            logger.error(f"❌ متغير مفقود: {section}.{var}")
                            return False
            
            logger.info("✅ جميع متغيرات البيئة موجودة")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل الإعدادات: {e}")
            return False

    async def initialize_telegram(self) -> bool:
        """تهيئة عميل Telegram"""
        try:
            api_id = int(os.getenv("TELEGRAM_API_ID") or self.config.get("TELEGRAM", "API_ID"))
            api_hash = os.getenv("TELEGRAM_API_HASH") or self.config.get("TELEGRAM", "API_HASH")
            string_session = os.getenv("TELEGRAM_STRING_SESSION") or self.config.get("TELEGRAM", "STRING_SESSION")
            
            self.telegram_client = TelegramClient(
                session=string_session,
                api_id=api_id,
                api_hash=api_hash
            )
            
            await self.telegram_client.start()
            logger.info("✅ تم تهيئة عميل Telegram")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة Telegram: {e}")
            return False

    def initialize_bybit(self) -> bool:
        """تهيئة واجهة Bybit"""
        try:
            self.bybit_api = BybitTradingAPI(self.config_file)
            
            # اختبار الاتصال
            balance = self.bybit_api.get_balance()
            logger.info(f"✅ تم تهيئة Bybit API - الرصيد: {balance} USDT")
            
            # عرض الإعدادات
            capital_percentage = self.bybit_api.capital_percentage
            logger.info(f"⚙️ نسبة رأس المال: {capital_percentage}%")
            logger.info("⚡ الرافعة المالية: أقصى رافعة لكل عملة")
            logger.info("🔄 نوع الهامش: Cross Margin")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة Bybit: {e}")
            return False

    def initialize_signal_parser(self) -> bool:
        """تهيئة محلل الإشارات"""
        try:
            self.signal_parser = TradingSignalParser()
            logger.info("✅ تم تهيئة محلل الإشارات")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة محلل الإشارات: {e}")
            return False

    async def handle_message(self, event):
        """معالجة الرسائل الواردة"""
        try:
            self.stats['messages_received'] += 1
            
            # الحصول على نص الرسالة
            message_text = event.message.text
            if not message_text:
                return
            
            # الحصول على معلومات المرسل
            sender = await event.get_sender()
            sender_name = getattr(sender, 'username', None) or getattr(sender, 'first_name', 'Unknown')
            
            logger.info(f"📨 رسالة جديدة من: {sender_name}")
            logger.debug(f"📝 محتوى الرسالة: {message_text[:100]}...")
            
            # تحليل الإشارة
            signal = self.signal_parser.parse_signal(message_text)
            if not signal:
                return
            
            # التحقق من صحة الإشارة
            if not self.signal_parser.validate_signal(signal):
                logger.warning("❌ إشارة غير صحيحة، تم تجاهلها")
                return
            
            self.stats['signals_processed'] += 1
            self.stats['last_signal_time'] = datetime.now()
            
            # عرض تفاصيل الإشارة
            logger.info("=" * 60)
            logger.info(f"📩 إشارة تداول جديدة من: {sender_name}")
            logger.info(f"📊 الرمز: {signal['symbol']}")
            logger.info(f"🔄 الاتجاه: {signal['direction']}")
            logger.info(f"💰 سعر الدخول: {signal['entry_price']}")
            if signal.get('take_profit_1'):
                logger.info(f"🎯 الهدف الأول: {signal['take_profit_1']}")
            if signal.get('take_profit_2'):
                logger.info(f"🎯 الهدف الثاني: {signal['take_profit_2']}")
            if signal.get('stop_loss'):
                logger.info(f"⛔ وقف الخسارة: {signal['stop_loss']}")
            
            # تنفيذ الصفقة
            logger.info("🚀 بدء تنفيذ الصفقة...")
            await self.execute_trade(signal)
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرسالة: {e}")

    async def execute_trade(self, signal: Dict[str, Any]):
        """تنفيذ الصفقة"""
        try:
            result = self.bybit_api.open_position(
                symbol=signal['symbol'],
                direction=signal['direction'],
                entry_price=signal['entry_price'],
                stop_loss=signal.get('stop_loss'),
                take_profit=signal.get('take_profit_1')  # استخدام الهدف الأول
            )
            
            if result['status'] == 'success':
                self.stats['trades_executed'] += 1
                logger.info("✅ تم تنفيذ الصفقة بنجاح")
                logger.info(f"📋 تفاصيل الأمر: {result.get('order', {}).get('order_id', 'N/A')}")
                logger.info(f"⚡ الرافعة المالية: {result.get('leverage', 'N/A')}x")
            else:
                self.stats['trades_failed'] += 1
                logger.error(f"❌ فشل في تنفيذ الصفقة: {result.get('message', 'خطأ غير معروف')}")
            
            logger.info(f"📈 إجمالي الصفقات المنفذة: {self.stats['trades_executed']}")
            
        except Exception as e:
            self.stats['trades_failed'] += 1
            logger.error(f"❌ خطأ في تنفيذ الصفقة: {e}")

    def setup_signal_handlers(self):
        """إعداد معالجات الإشارات"""
        def signal_handler(signum, frame):
            logger.info(f"🛑 تم استلام إشارة إيقاف ({signum})")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def print_stats(self):
        """طباعة إحصائيات البوت"""
        runtime = datetime.now() - self.stats['start_time']
        
        logger.info("🛑 إيقاف البوت...")
        logger.info("=" * 60)
        logger.info("📊 إحصائيات البوت:")
        logger.info(f"⏱️ وقت التشغيل: {runtime}")
        logger.info(f"📨 الرسائل المستلمة: {self.stats['messages_received']}")
        logger.info(f"🔍 الإشارات المعالجة: {self.stats['signals_processed']}")
        logger.info(f"✅ الصفقات المنفذة: {self.stats['trades_executed']}")
        logger.info(f"❌ الصفقات الفاشلة: {self.stats['trades_failed']}")
        if self.stats['last_signal_time']:
            logger.info(f"🕐 آخر إشارة: {self.stats['last_signal_time']}")
        logger.info("=" * 60)

    async def run(self):
        """تشغيل البوت"""
        try:
            # تحميل الإعدادات
            if not self.load_config():
                return False
            
            # تهيئة المكونات
            if not await self.initialize_telegram():
                return False
            
            if not self.initialize_bybit():
                return False
            
            if not self.initialize_signal_parser():
                return False
            
            # إعداد معالج الرسائل
            @self.telegram_client.on(events.NewMessage)
            async def message_handler(event):
                await self.handle_message(event)
            
            # إعداد معالجات الإشارات
            self.setup_signal_handlers()
            
            logger.info("🚀 بدء تشغيل البوت...")
            logger.info("📡 البوت يستقبل الرسائل من جميع المحادثات...")
            
            self.is_running = True
            
            # حلقة التشغيل الرئيسية
            while self.is_running:
                await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تشغيل البوت: {e}")
            return False
        
        finally:
            # تنظيف الموارد
            if self.telegram_client:
                await self.telegram_client.disconnect()
                logger.info("✅ تم قطع الاتصال مع Telegram")
            
            self.print_stats()
            logger.info("✅ تم إيقاف البوت بأمان")

async def main():
    """الدالة الرئيسية"""
    bot = EnhancedBybitTradingBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 تم إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.error(f"❌ خطأ عام في البوت: {e}")

