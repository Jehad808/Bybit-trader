import logging
from main_bot import TradingBot
from bybit_api import BybitAPI
import configparser
import os
from telethon import TelegramClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 بدء تشغيل بوت التداول Bybit")
    logger.info("==================================================")
    config_file = "config.ini"
    if not os.path.exists(config_file):
        logger.error("❌ ملف config.ini غير موجود!")
        return
    config = configparser.ConfigParser()
    config.read(config_file)
    required_env_vars = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "BYBIT_API_KEY", "BYBIT_API_SECRET"]
    for var in required_env_vars:
        if not os.getenv(var):
            logger.error(f"❌ متغير البيئة {var} غير موجود!")
            return
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    client = TelegramClient('bot_session', api_id, api_hash)
    try:
        bybit_api = BybitAPI(config_file="config.ini")
    except Exception as e:
        logger.error(f"❌ فشل تهيئة Bybit API: {e}")
        return
    bot = TradingBot(client, bybit_api, config)
    async def run():
        try:
            await client.start()
            logger.info("✅ البوت يعمل الآن...")
            await bot.run()
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"❌ خطأ أثناء تشغيل البوت: {e}")
    with client:
        client.loop.run_until_complete(run())

if __name__ == "__main__":
    main()
