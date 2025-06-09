import os
import logging
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_string_session():
    """إنشاء جلسة سلسلة لتيليجرام"""
    
    # معلومات API (يمكن تغييرها حسب الحاجة)
    api_id = 20535892
    api_hash = "25252574a23609d7bdeefe9378d97af2"
    
    print("🔐 مولد جلسة السلسلة لتيليجرام")
    print("=" * 50)
    print("سيطلب منك إدخال رقم الهاتف ورمز التحقق")
    print("(وكلمة المرور إذا كانت مفعلة)")
    print("=" * 50)
    
    try:
        # إنشاء جلسة سلسلة فارغة
        string_session = StringSession()
        
        # إنشاء عميل تيليجرام
        with TelegramClient(string_session, api_id, api_hash) as client:
            print("\n✅ تم تسجيل الدخول بنجاح!")
            
            # الحصول على جلسة السلسلة
            session_string = client.session.save()
            
            print("\n" + "=" * 60)
            print("🎉 تم إنشاء جلسة السلسلة بنجاح!")
            print("=" * 60)
            print("انسخ السلسلة التالية بالكامل واحتفظ بها في مكان آمن:")
            print("ستحتاجها كمتغير بيئة TELEGRAM_STRING_SESSION")
            print("=" * 60)
            print(f"\n{session_string}\n")
            print("=" * 60)
            print("⚠️ تحذير: لا تشارك هذه السلسلة مع أي شخص!")
            print("=" * 60)
            
            return session_string
            
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء الجلسة: {e}")
        return None

if __name__ == "__main__":
    generate_string_session()

