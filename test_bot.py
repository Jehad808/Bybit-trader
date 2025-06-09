#!/usr/bin/env python3
"""
اختبار شامل لبوت التداول Bybit
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# إضافة المجلد الحالي للمسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_signal_parser():
    """اختبار محلل الإشارات"""
    logger.info("🧪 اختبار محلل الإشارات...")
    
    try:
        from signal_parser import TradingSignalParser
        parser = TradingSignalParser()
        
        # إشارة اختبار
        test_signals = [
            """
📢 Trade Signal Detected!

📊 Symbol: LTCUSDT.P
🔁 Direction: LONG
📍 Entry Price: 87.798
🎯 Take Profit 1: 88.503
🎯 Take Profit 2: 90.2514
⛔ Stop Loss: 86.67
""",
            """
📢 Trade Signal Detected!

📊 Symbol: BTCUSDT.P
🔁 Direction: SHORT
📍 Entry Price: 45000.50
🎯 Take Profit 1: 44500.25
⛔ Stop Loss: 45500.75
""",
            """
رسالة عادية بدون إشارة تداول
""",
            """
📊 Symbol: ETHUSDT.P
🔁 Direction: LONG
📍 Entry Price: 2500.00
🎯 Take Profit 1: 2600.00
⛔ Stop Loss: 2400.00
"""
        ]
        
        success_count = 0
        for i, signal in enumerate(test_signals, 1):
            logger.info(f"اختبار الإشارة {i}...")
            result = parser.parse_signal(signal)
            
            if result:
                logger.info(f"✅ تم تحليل الإشارة {i} بنجاح: {result['symbol']} {result['direction']}")
                if parser.validate_signal(result):
                    logger.info(f"✅ الإشارة {i} صالحة")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ الإشارة {i} غير صالحة")
            else:
                logger.info(f"ℹ️ الإشارة {i} ليست إشارة تداول (متوقع)")
        
        logger.info(f"✅ اختبار محلل الإشارات مكتمل - نجح {success_count} من {len(test_signals)} اختبارات")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار محلل الإشارات: {e}")
        return False

def test_bybit_api_connection():
    """اختبار الاتصال مع Bybit API (بدون تنفيذ صفقات)"""
    logger.info("🧪 اختبار الاتصال مع Bybit API...")
    
    try:
        from bybit_api import BybitTradingAPI
        
        # محاولة إنشاء الاتصال
        api = BybitTradingAPI()
        logger.info("✅ تم إنشاء اتصال Bybit API بنجاح")
        
        # اختبار تنسيق الرموز
        test_symbols = ["BTCUSDT.P", "ETHUSDT", "LTCUSDT.P"]
        for symbol in test_symbols:
            formatted = api._format_symbol(symbol)
            logger.info(f"📊 {symbol} -> {formatted}")
        
        logger.info("✅ اختبار Bybit API مكتمل")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار Bybit API: {e}")
        logger.warning("⚠️ تأكد من صحة مفاتيح API في config.ini")
        return False

def test_config_loading():
    """اختبار تحميل الإعدادات"""
    logger.info("🧪 اختبار تحميل الإعدادات...")
    
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read("config.ini")
        
        # التحقق من الأقسام المطلوبة
        required_sections = ["TELEGRAM", "BYBIT"]
        for section in required_sections:
            if not config.has_section(section):
                logger.error(f"❌ قسم مفقود في config.ini: {section}")
                return False
            logger.info(f"✅ تم العثور على قسم: {section}")
        
        # التحقق من المفاتيح المطلوبة
        telegram_keys = ["API_ID", "API_HASH", "STRING_SESSION"]
        bybit_keys = ["API_KEY", "API_SECRET", "LEVERAGE", "CAPITAL_PERCENTAGE"]
        
        for key in telegram_keys:
            if not config.get("TELEGRAM", key, fallback=None):
                logger.warning(f"⚠️ مفتاح Telegram مفقود: {key}")
        
        for key in bybit_keys:
            if not config.get("BYBIT", key, fallback=None):
                logger.warning(f"⚠️ مفتاح Bybit مفقود: {key}")
        
        logger.info("✅ اختبار تحميل الإعدادات مكتمل")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار الإعدادات: {e}")
        return False

def test_dependencies():
    """اختبار المكتبات المطلوبة"""
    logger.info("🧪 اختبار المكتبات المطلوبة...")
    
    required_modules = [
        "telethon",
        "ccxt",
        "configparser",
        "logging",
        "asyncio",
        "re",
        "math",
        "decimal"
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✅ {module}")
        except ImportError:
            logger.error(f"❌ {module}")
            missing_modules.append(module)
    
    if missing_modules:
        logger.error(f"❌ مكتبات مفقودة: {', '.join(missing_modules)}")
        return False
    
    logger.info("✅ جميع المكتبات المطلوبة متوفرة")
    return True

async def test_telegram_client():
    """اختبار عميل Telegram (بدون اتصال فعلي)"""
    logger.info("🧪 اختبار إعداد عميل Telegram...")
    
    try:
        import configparser
        from telethon import TelegramClient
        
        config = configparser.ConfigParser()
        config.read("config.ini")
        
        api_id = int(config["TELEGRAM"]["API_ID"])
        api_hash = config["TELEGRAM"]["API_HASH"]
        string_session = config["TELEGRAM"]["STRING_SESSION"]
        
        # إنشاء العميل (بدون اتصال)
        client = TelegramClient(
            string_session=string_session,
            api_id=api_id,
            api_hash=api_hash
        )
        
        logger.info("✅ تم إنشاء عميل Telegram بنجاح")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار عميل Telegram: {e}")
        return False

def main():
    """تشغيل جميع الاختبارات"""
    logger.info("🚀 بدء الاختبارات الشاملة لبوت التداول")
    logger.info("=" * 60)
    
    tests = [
        ("اختبار المكتبات المطلوبة", test_dependencies),
        ("اختبار تحميل الإعدادات", test_config_loading),
        ("اختبار محلل الإشارات", test_signal_parser),
        ("اختبار Bybit API", test_bybit_api_connection),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"🧪 {test_name}...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = asyncio.run(test_func())
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ خطأ في {test_name}: {e}")
            results.append((test_name, False))
        
        logger.info("-" * 40)
    
    # تقرير النتائج
    logger.info("📊 تقرير الاختبارات:")
    logger.info("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        logger.info(f"{status} - {test_name}")
        if result:
            passed += 1
    
    logger.info("=" * 60)
    logger.info(f"📈 النتيجة النهائية: {passed}/{total} اختبارات نجحت")
    
    if passed == total:
        logger.info("🎉 جميع الاختبارات نجحت! البوت جاهز للتشغيل")
        return True
    else:
        logger.warning("⚠️ بعض الاختبارات فشلت. يرجى مراجعة الأخطاء أعلاه")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

