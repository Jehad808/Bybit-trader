import logging
from main_bot import TradingBot  # استيراد فئة TradingBot بدلاً من main
from bybit_api import BybitAPI
import configparser
import os
from telethon import TelegramClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 بدء تشغيل بوت التداول Bybit")
    logger.info("==================================================")
    
    # التحقق من الملفات والإعدادات
    config_file = "config.ini"
    if not os.path.exists(config_file):
        logger.error("❌ ملف config.ini غير موجود!")
        return
    
    logger.info("✅ جميع الملفات المطلوبة موجودة")
    
    config = configparser.ConfigParser()
    config.read(config_file)
    logger.info("✅ تم تحميل الإعدادات من config.ini")
    
    # التحقق من متغيرات البيئة
    required_env_vars = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "BYBIT_API_KEY", "BYBIT_API_SECRET"]
    for var in required_env_vars:
        if not os.getenv(var):
            logger.error(f"❌ متغير البيئة {var} غير موجود!")
            return
    
    logger.info("✅ جميع متغيرات البيئة موجودة")
    logger.info("✅ جميع الفحوصات نجحت - تشغيل البوت...")
    logger.info("==================================================")
    
    # تهيئة عميل Telegram
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    client = TelegramClient('bot_session', api_id, api_hash)
    
    # تهيئة Bybit API
    bybit_api = BybitAPI(config_file="config.ini")
    
    # تهيئة البوت
    bot = TradingBot(client, bybit_api, config)
    
    # تشغيل البوت
    async def run():
        await client.start()
        logger.info("✅ البوت يعمل الآن...")
        await bot.run()  # تشغيل دالة run في TradingBot
        await client.run_until_disconnected()
    
    with client:
        client.loop.run_until_complete(run())

if __name__ == "__main__":
    main()
