import logging
import configparser
from telethon import TelegramClient, events
from bybit_api import BybitTradingAPI
from signal_parser import TradingSignalParser

# إعدادات اللوج
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تحميل الإعدادات
config = configparser.ConfigParser()
config.read("config.ini")

api_id = int(config["TELEGRAM"]["API_ID"])
api_hash = config["TELEGRAM"]["API_HASH"]
string_session = config["TELEGRAM"]["STRING_SESSION"]

# إنشاء واجهة Bybit
trading_api = BybitTradingAPI()

# إنشاء محلل الإشارات
signal_parser = TradingSignalParser()

# تشغيل البوت
client = TelegramClient(string_session=string_session, api_id=api_id, api_hash=api_hash)

@client.on(events.NewMessage)
async def handler(event):
    try:
        if not event.message.text:
            return
        
        # تحليل الإشارة
        signal_data = signal_parser.parse_signal(event.message.text)
        
        if not signal_data:
            return  # ليست إشارة تداول
        
        # التحقق من صحة الإشارة
        if not signal_parser.validate_signal(signal_data):
            logger.warning("إشارة غير صالحة، تم تجاهلها")
            return
        
        # معلومات المصدر
        chat_title = "خاص"
        if event.chat:
            chat_title = event.chat.title or f"Chat ID: {event.chat_id}"
        
        logger.info(f"📩 إشارة صالحة من: {chat_title}")
        logger.info(f"📊 {signal_data['symbol']} {signal_data['direction']} @ {signal_data['entry_price']}")
        logger.info(f"🎯 TP1: {signal_data['take_profit_1']} | ⛔ SL: {signal_data['stop_loss']}")
        
        # تنفيذ الصفقة
        try:
            result = trading_api.open_position(
                symbol=signal_data['symbol'],
                direction=signal_data['direction'],
                entry_price=signal_data['entry_price'],
                take_profit=signal_data['take_profit_1'],  # نستخدم الهدف الأول فقط
                stop_loss=signal_data['stop_loss']
            )
            
            if result['status'] == 'success':
                logger.info(f"✅ تم فتح الصفقة بنجاح - Order ID: {result['order']['id']}")
            else:
                logger.error(f"❌ فشل في تنفيذ الصفقة: {result['message']}")
            
        except Exception as trade_error:
            logger.error(f"❌ خطأ في تنفيذ الصفقة: {trade_error}")
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الرسالة: {e}")

async def main():
    """تشغيل البوت الرئيسي"""
    try:
        logger.info("🚀 بدء تشغيل بوت Bybit Trading...")
        logger.info("📡 البوت يستقبل الرسائل من جميع المحادثات...")
        
        await client.start()
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())