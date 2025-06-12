import os
import sys
import logging
import asyncio
import signal
from datetime import datetime
from typing import Dict, Any
import configparser
from telethon import TelegramClient, events
import tempfile

# إضافة المجلد الحالي لمسار Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# استيراد الوحدات المثالية
from perfect_bybit_api import BybitTradingAPI
from perfect_signal_parser import TradingSignalParser

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

class PerfectBybitTradingBot:
    """بوت التداول المثالي مع جميع الميزات المطلوبة"""
    
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
        
        logger.info("🚀 بدء تشغيل بوت التداول Bybit المثالي")
        logger.info("=" * 60)

    def load_config(self) -> bool:
        """تحميل الإعدادات"""
        try:
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
        """تهيئة عميل Telegram مع حل مشكلة قاعدة البيانات"""
        try:
            api_id = int(os.getenv("TELEGRAM_API_ID") or self.config.get("TELEGRAM", "API_ID"))
            api_hash = os.getenv("TELEGRAM_API_HASH") or self.config.get("TELEGRAM", "API_HASH")
            string_session = os.getenv("TELEGRAM_STRING_SESSION") or self.config.get("TELEGRAM", "STRING_SESSION")
            
            # إنشاء مجلد مؤقت لقاعدة البيانات
            temp_dir = tempfile.mkdtemp()
            session_file = os.path.join(temp_dir, "session")
            
            # إنشاء عميل Telegram مع StringSession
            self.telegram_client = TelegramClient(
                session=string_session,
                api_id=api_id,
                api_hash=api_hash,
                system_version="4.16.30-vxCUSTOM"
            )
            
            # تعيين مجلد العمل المؤقت
            self.telegram_client.session.save_path = session_file
            
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
            logger.info(f"⚙️ نسبة رأس المال: {capital_percentage}% من الرصيد الحقيقي")
            logger.info("⚡ الرافعة المالية: أقصى رافعة لكل عملة")
            logger.info("🔄 نوع الهامش: Cross Margin")
            logger.info("🎯 أوامر SL/TP: تلقائية مع كل صفقة")
            
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
            
            # التحقق من وجود مركز مفتوح للرمز
            if self._check_existing_position(signal['symbol']):
                logger.warning(f"⚠️ يوجد مركز مفتوح بالفعل لـ {signal['symbol']}")
                return
            
            # تنفيذ الصفقة
            logger.info("🚀 بدء تنفيذ الصفقة...")
            await self.execute_trade(signal)
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرسالة: {e}")

    def _check_existing_position(self, symbol: str) -> bool:
        """التحقق من وجود مركز مفتوح للرمز"""
        try:
            positions = self.bybit_api.get_positions()
            formatted_symbol = self.bybit_api._format_symbol(symbol)
            
            for position in positions:
                if position.get('symbol') == formatted_symbol:
                    logger.info(f"📊 مركز موجود لـ {symbol}: {position.get('side')} - الحجم: {position.get('size')}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ خطأ في فحص المراكز: {e}")
            return False

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
                logger.info(f"📋 معرف الأمر: {result.get('order', {}).get('order_id', 'N/A')}")
                logger.info(f"⚡ الرافعة المالية: {result.get('leverage', 'N/A')}x")
                logger.info(f"📊 حجم المركز: {result.get('size', 'N/A')}")
                
                # إضافة الهدف الثاني إذا كان موجود
                if signal.get('take_profit_2'):
                    await self._add_second_target(signal, result)
                    
            else:
                self.stats['trades_failed'] += 1
                logger.error(f"❌ فشل في تنفيذ الصفقة: {result.get('message', 'خطأ غير معروف')}")
            
            logger.info(f"📈 إجمالي الصفقات المنفذة: {self.stats['trades_executed']}")
            logger.info(f"❌ إجمالي الصفقات الفاشلة: {self.stats['trades_failed']}")
            
        except Exception as e:
            self.stats['trades_failed'] += 1
            logger.error(f"❌ خطأ في تنفيذ الصفقة: {e}")

    async def _add_second_target(self, signal: Dict[str, Any], trade_result: Dict[str, Any]):
        """إضافة الهدف الثاني للصفقة"""
        try:
            # هذه الوظيفة يمكن تطويرها لاحقاً لإضافة أهداف متعددة
            logger.info(f"🎯 الهدف الثاني متاح: {signal['take_profit_2']}")
            logger.info("ℹ️ يمكن إضافة الهدف الثاني يدوياً أو تطوير الوظيفة لاحقاً")
            
        except Exception as e:
            logger.warning(f"⚠️ خطأ في إضافة الهدف الثاني: {e}")

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
        
        # حساب معدل النجاح
        total_trades = self.stats['trades_executed'] + self.stats['trades_failed']
        if total_trades > 0:
            success_rate = (self.stats['trades_executed'] / total_trades) * 100
            logger.info(f"📈 معدل النجاح: {success_rate:.1f}%")
        
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
            logger.info("💰 يستخدم 5% من رأس المال الحقيقي لكل صفقة")
            logger.info("⚡ يطبق أقصى رافعة مالية لكل عملة")
            logger.info("🔄 يستخدم Cross Margin")
            logger.info("🎯 يضع أوامر SL/TP تلقائياً")
            
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
    bot = PerfectBybitTradingBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 تم إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.error(f"❌ خطأ عام في البوت: {e}")

