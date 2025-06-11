import logging
from main_bot import TradingBot
from bybit_api import BybitAPI
import configparser
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

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
    session_string = "1BJWap1sBuzv2tw3hiVhZ3e10vz3_cSpG1bKT1BBgRLqrQxhFHuUqh7N9R98azyy1Zmlmc0HhDQ5YwxpBx3eoce4oxVSNbSkp-trmraA6FRFzb4SBRraazuMSr-T0b8IfGMmyxWbmuKc-dFECryr_b58sbtsmbHScnFIr6zYzQIwi-5FHzXDvJxy7tHBVPJjHviohXJQiMhu6rNMHWN0BJAS83koiEQD49yEdW_caziiLevH5HZrwQ2WBGdpZ4s8G_Tjjoxbzf0qSZBW2nJJ4crzrgO3j4h1a5TWdd5wiX4deCIW31X9by_PuLg3GxIcjF7r-VeXu42lY55nRIOAzOKfO99_A5VY="
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
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
