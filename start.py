import os
import sys
import logging
from pathlib import Path

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """التحقق من متغيرات البيئة المطلوبة"""
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

def check_string_session():
    """التحقق من وجود جلسة السلسلة"""
    string_session = os.getenv('TELEGRAM_STRING_SESSION')
    
    if not string_session:
        logger.error("❌ جلسة السلسلة غير موجودة")
        logger.info("💡 قم بتشغيل generate_string_session.py لإنشاء جلسة جديدة")
        return False
    
    if len(string_session) < 100:
        logger.error("❌ جلسة السلسلة قصيرة جداً - قد تكون غير صالحة")
        return False
    
    logger.info("✅ جلسة السلسلة موجودة وتبدو صالحة")
    return True

def main():
    """تشغيل البوت الرئيسي"""
    try:
        logger.info("🚀 بدء تشغيل بوت التداول Bybit")
        logger.info("=" * 50)
        
        # التحقق من متغيرات البيئة
        if not check_environment():
            logger.error("❌ فشل في التحقق من متغيرات البيئة")
            sys.exit(1)
        
        # التحقق من جلسة السلسلة
        if not check_string_session():
            logger.error("❌ فشل في التحقق من جلسة السلسلة")
            sys.exit(1)
        
        # التحقق من وجود ملف البوت الرئيسي
        bot_file = Path("main_bot.py")
        if not bot_file.exists():
            logger.error("❌ ملف البوت الرئيسي غير موجود: main_bot.py")
            sys.exit(1)
        
        # تشغيل البوت الرئيسي
        logger.info("✅ جميع الفحوصات نجحت - تشغيل البوت...")
        logger.info("=" * 50)
        
        # استيراد وتشغيل البوت
        import main_bot
        
    except ImportError as e:
        logger.error(f"❌ خطأ في استيراد البوت: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

