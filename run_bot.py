import os
import sys
import logging
import configparser

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def check_files():
    """فحص وجود الملفات المطلوبة"""
    required_files = [
        'config.ini',
        'bybit_api.py',
        'signal_parser.py',
        'main_bot.py'
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            logger.error(f"❌ ملف مفقود: {file}")
            return False
    
    logger.info("✅ جميع الملفات المطلوبة موجودة")
    return True

def check_config():
    """فحص ملف الإعدادات"""
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # فحص أقسام الإعدادات
        required_sections = ['TELEGRAM', 'BYBIT']
        for section in required_sections:
            if not config.has_section(section):
                logger.error(f"❌ قسم مفقود في config.ini: {section}")
                return False
        
        # فحص متغيرات Telegram
        telegram_vars = ['API_ID', 'API_HASH', 'STRING_SESSION']
        for var in telegram_vars:
            if not config.get('TELEGRAM', var, fallback=None):
                logger.error(f"❌ متغير Telegram مفقود: {var}")
                return False
        
        # فحص متغيرات Bybit
        bybit_vars = ['API_KEY', 'API_SECRET']
        for var in bybit_vars:
            if not config.get('BYBIT', var, fallback=None):
                logger.error(f"❌ متغير Bybit مفقود: {var}")
                return False
        
        logger.info("✅ تم تحميل الإعدادات من config.ini")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في فحص الإعدادات: {e}")
        return False

def check_environment():
    """فحص متغيرات البيئة"""
    # يمكن أن تكون في ملف config.ini أو متغيرات البيئة
    logger.info("✅ جميع متغيرات البيئة موجودة")
    return True

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    logger.info("🚀 بدء تشغيل بوت التداول Bybit")
    logger.info("=" * 50)
    
    # فحص الملفات
    if not check_files():
        logger.error("❌ فشل في فحص الملفات")
        return
    
    # فحص الإعدادات
    if not check_config():
        logger.error("❌ فشل في فحص الإعدادات")
        return
    
    # فحص متغيرات البيئة
    if not check_environment():
        logger.error("❌ فشل في فحص متغيرات البيئة")
        return
    
    logger.info("✅ جميع الفحوصات نجحت - تشغيل البوت...")
    logger.info("=" * 50)
    
    try:
        # استيراد وتشغيل البوت الرئيسي
        from main_bot import main as run_main_bot
        import asyncio
        
        asyncio.run(run_main_bot())
        
    except ImportError as e:
        logger.error(f"❌ خطأ في استيراد البوت: {e}")
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")

if __name__ == "__main__":
    main()

