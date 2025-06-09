import os
import logging
from pathlib import Path

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_env_from_config():
    """تحميل متغيرات البيئة من config.ini"""
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read("config.ini")
        
        # تعيين متغيرات البيئة من config.ini
        if config.has_section("TELEGRAM"):
            os.environ["TELEGRAM_API_ID"] = config.get("TELEGRAM", "API_ID", fallback="")
            os.environ["TELEGRAM_API_HASH"] = config.get("TELEGRAM", "API_HASH", fallback="")
            os.environ["TELEGRAM_STRING_SESSION"] = config.get("TELEGRAM", "STRING_SESSION", fallback="")
        
        if config.has_section("BYBIT"):
            os.environ["BYBIT_API_KEY"] = config.get("BYBIT", "API_KEY", fallback="")
            os.environ["BYBIT_API_SECRET"] = config.get("BYBIT", "API_SECRET", fallback="")
        
        logger.info("✅ تم تحميل الإعدادات من config.ini")
        
    except Exception as e:
        logger.warning(f"⚠️ تحذير: لم يتم تحميل config.ini: {e}")

def check_environment():
    """التحقق من متغيرات البيئة المطلوبة"""
    # تحميل الإعدادات أولاً
    load_env_from_config()
    
    required_vars = [
        'TELEGRAM_API_ID',
        'TELEGRAM_API_HASH', 
        'TELEGRAM_STRING_SESSION',
        'BYBIT_API_KEY',
        'BYBIT_API_SECRET'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ متغيرات البيئة المفقودة: {', '.join(missing_vars)}")
        return False
    
    logger.info("✅ جميع متغيرات البيئة موجودة")
    return True

def check_files():
    """التحقق من وجود الملفات المطلوبة"""
    required_files = [
        "config.ini",
        "main_bot.py",
        "bybit_api.py",
        "signal_parser.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        logger.error(f"❌ ملفات مفقودة: {', '.join(missing_files)}")
        return False
    
    logger.info("✅ جميع الملفات المطلوبة موجودة")
    return True

def main():
    """تشغيل البوت الرئيسي"""
    try:
        logger.info("🚀 بدء تشغيل بوت التداول Bybit")
        logger.info("=" * 50)
        
        # التحقق من الملفات
        if not check_files():
            logger.error("❌ فشل في التحقق من الملفات")
            return
        
        # التحقق من متغيرات البيئة
        if not check_environment():
            logger.error("❌ فشل في التحقق من متغيرات البيئة")
            return
        
        # تشغيل البوت الرئيسي
        logger.info("✅ جميع الفحوصات نجحت - تشغيل البوت...")
        logger.info("=" * 50)
        
        # استيراد وتشغيل البوت
        from main_bot import main as run_bot
        import asyncio
        
        asyncio.run(run_bot())
        
    except KeyboardInterrupt:
        logger.info("🛑 تم إيقاف البوت بواسطة المستخدم")
    except ImportError as e:
        logger.error(f"❌ خطأ في استيراد البوت: {e}")
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")

if __name__ == "__main__":
    main()

