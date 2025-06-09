import logging
import configparser
from telethon import TelegramClient, events
from bybit_api import open_position
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

# إعدادات Bybit
leverage = int(config["BYBIT"]["LEVERAGE"])
capital_pct = float(config["BYBIT"]["CAPITAL_PERCENTAGE"])

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
            order_id = open_position(
                symbol=signal_data['symbol'],
                direction=signal_data['direction'],
                entry_price=signal_data['entry_price'],
                take_profit=signal_data['take_profit_1'],  # نستخدم الهدف الأول فقط
                stop_loss=signal_data['stop_loss'],
                pct=capital_pct,
                leverage=leverage
            )
            
            logger.info(f"✅ تم فتح الصفقة بنجاح - Order ID: {order_id}")
            logger.info(f"💰 نسبة رأس المال: {capital_pct}% | 🔢 الرافعة: {leverage}x")
            
        except Exception as trade_error:
            logger.error(f"❌ خطأ في تنفيذ الصفقة: {trade_error}")
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الرسالة: {e}")

async def main():
    """تشغيل البوت الرئيسي"""
    try:
        logger.info("🚀 بدء تشغيل بوت Bybit Trading...")
        logger.info(f"⚙️ الإعدادات: رافعة {leverage}x، نسبة رأس المال {capital_pct}%")
        logger.info("📡 البوت يستقبل الرسائل من جميع المحادثات...")
        
        await client.start()
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())