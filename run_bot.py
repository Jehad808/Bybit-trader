import logging
from main_bot import TradingBot
from bybit_api import BybitAPI
from telethon import TelegramClient
import configparser
import asyncio
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 بدء تشغيل بوت التداول Bybit")
    logger.info("=" * 50)
    
    config = configparser.ConfigParser()
    config.read('config.ini')

    api_id = config.get('TELEGRAM', 'API_ID')
    api_hash = config.get('TELEGRAM', 'API_HASH')
    phone = config.get('TELEGRAM', 'phone_number')  # Changed from PHONE to phone_number
    session_name = config.get('TELEGRAM', 'SESSION_NAME')
    
    client = TelegramClient(session_name, api_id, api_hash)
    
    bybit_api = BybitAPI()
    
    bot = TradingBot(client, bybit_api, config)
    
    try:
        await client.start(phone)
        await bot.run()
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
