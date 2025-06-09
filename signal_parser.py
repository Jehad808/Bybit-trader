import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TradingSignalParser:
    """محلل إشارات التداول من Telegram"""
    
    def __init__(self):
        # نماذج regex لاستخراج البيانات
        self.patterns = {
            'symbol': [
                r'Symbol[:\s]*([A-Z0-9]+\.?P?)',
                r'📊\s*Symbol[:\s]*([A-Z0-9]+\.?P?)',
                r'الرمز[:\s]*([A-Z0-9]+\.?P?)',
                r'العملة[:\s]*([A-Z0-9]+\.?P?)'
            ],
            'direction': [
                r'Direction[:\s]*(LONG|SHORT|BUY|SELL)',
                r'🔁\s*Direction[:\s]*(LONG|SHORT|BUY|SELL)',
                r'الاتجاه[:\s]*(LONG|SHORT|BUY|SELL|شراء|بيع)',
                r'نوع الصفقة[:\s]*(LONG|SHORT|BUY|SELL|شراء|بيع)'
            ],
            'entry_price': [
                r'Entry Price[:\s]*([0-9]+\.?[0-9]*)',
                r'📍\s*Entry Price[:\s]*([0-9]+\.?[0-9]*)',
                r'سعر الدخول[:\s]*([0-9]+\.?[0-9]*)',
                r'الدخول[:\s]*([0-9]+\.?[0-9]*)'
            ],
            'take_profit_1': [
                r'Take Profit 1[:\s]*([0-9]+\.?[0-9]*)',
                r'🎯\s*Take Profit 1[:\s]*([0-9]+\.?[0-9]*)',
                r'الهدف الأول[:\s]*([0-9]+\.?[0-9]*)',
                r'TP1[:\s]*([0-9]+\.?[0-9]*)'
            ],
            'take_profit_2': [
                r'Take Profit 2[:\s]*([0-9]+\.?[0-9]*)',
                r'🎯\s*Take Profit 2[:\s]*([0-9]+\.?[0-9]*)',
                r'الهدف الثاني[:\s]*([0-9]+\.?[0-9]*)',
                r'TP2[:\s]*([0-9]+\.?[0-9]*)'
            ],
            'stop_loss': [
                r'Stop Loss[:\s]*([0-9]+\.?[0-9]*)',
                r'⛔\s*Stop Loss[:\s]*([0-9]+\.?[0-9]*)',
                r'وقف الخسارة[:\s]*([0-9]+\.?[0-9]*)',
                r'SL[:\s]*([0-9]+\.?[0-9]*)'
            ]
        }
    
    def extract_field(self, text: str, field: str) -> Optional[str]:
        """استخراج حقل معين من النص"""
        if field not in self.patterns:
            return None
            
        for pattern in self.patterns[field]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def normalize_direction(self, direction: str) -> Optional[str]:
        """تطبيع اتجاه التداول"""
        if not direction:
            return None
            
        direction = direction.upper().strip()
        
        if direction in ['LONG', 'BUY', 'شراء']:
            return 'LONG'
        elif direction in ['SHORT', 'SELL', 'بيع']:
            return 'SHORT'
        else:
            return None
    
    def normalize_symbol(self, symbol: str) -> Optional[str]:
        """تطبيع رمز العملة"""
        if not symbol:
            return None
            
        symbol = symbol.upper().strip()
        
        # إزالة المسافات والرموز غير المرغوبة
        symbol = re.sub(r'[^A-Z0-9.]', '', symbol)
        
        # إضافة .P إذا لم تكن موجودة للعقود الآجلة
        if not symbol.endswith('.P') and 'USDT' in symbol:
            symbol = symbol.replace('USDT', 'USDT.P')
        
        return symbol
    
    def parse_signal(self, message_text: str) -> Optional[Dict[str, Any]]:
        """تحليل إشارة التداول من نص الرسالة"""
        try:
            if not message_text:
                return None
            
            # التحقق من وجود كلمات مفتاحية للإشارة
            signal_keywords = [
                'Trade Signal', 'Symbol', 'Direction', 'Entry Price',
                'Take Profit', 'Stop Loss', 'إشارة', 'الرمز', 'الاتجاه',
                'سعر الدخول', 'الهدف', 'وقف الخسارة'
            ]
            
            if not any(keyword.lower() in message_text.lower() for keyword in signal_keywords):
                return None
            
            # استخراج البيانات
            symbol = self.extract_field(message_text, 'symbol')
            direction = self.extract_field(message_text, 'direction')
            entry_price = self.extract_field(message_text, 'entry_price')
            take_profit_1 = self.extract_field(message_text, 'take_profit_1')
            take_profit_2 = self.extract_field(message_text, 'take_profit_2')
            stop_loss = self.extract_field(message_text, 'stop_loss')
            
            # تطبيع البيانات
            symbol = self.normalize_symbol(symbol)
            direction = self.normalize_direction(direction)
            
            # التحقق من وجود البيانات الأساسية
            if not all([symbol, direction, entry_price, take_profit_1, stop_loss]):
                logger.warning(f"بيانات ناقصة في الإشارة: symbol={symbol}, direction={direction}, entry={entry_price}, tp1={take_profit_1}, sl={stop_loss}")
                return None
            
            # تحويل الأرقام
            try:
                entry_price = float(entry_price)
                take_profit_1 = float(take_profit_1)
                stop_loss = float(stop_loss)
                take_profit_2 = float(take_profit_2) if take_profit_2 else None
            except ValueError as e:
                logger.error(f"خطأ في تحويل الأرقام: {e}")
                return None
            
            # التحقق من منطقية الأسعار
            if direction == 'LONG':
                if take_profit_1 <= entry_price or stop_loss >= entry_price:
                    logger.warning("أسعار غير منطقية للصفقة الطويلة")
                    return None
            elif direction == 'SHORT':
                if take_profit_1 >= entry_price or stop_loss <= entry_price:
                    logger.warning("أسعار غير منطقية للصفقة القصيرة")
                    return None
            
            signal_data = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'take_profit_1': take_profit_1,
                'take_profit_2': take_profit_2,
                'stop_loss': stop_loss,
                'raw_message': message_text
            }
            
            logger.info(f"تم تحليل إشارة بنجاح: {symbol} {direction} @ {entry_price}")
            return signal_data
            
        except Exception as e:
            logger.error(f"خطأ في تحليل الإشارة: {e}")
            return None
    
    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        """التحقق من صحة الإشارة"""
        try:
            required_fields = ['symbol', 'direction', 'entry_price', 'take_profit_1', 'stop_loss']
            
            # التحقق من وجود الحقول المطلوبة
            for field in required_fields:
                if field not in signal or signal[field] is None:
                    logger.error(f"حقل مفقود: {field}")
                    return False
            
            # التحقق من نوع البيانات
            if not isinstance(signal['entry_price'], (int, float)):
                return False
            if not isinstance(signal['take_profit_1'], (int, float)):
                return False
            if not isinstance(signal['stop_loss'], (int, float)):
                return False
            
            # التحقق من الاتجاه
            if signal['direction'] not in ['LONG', 'SHORT']:
                return False
            
            # التحقق من منطقية الأسعار
            entry = signal['entry_price']
            tp1 = signal['take_profit_1']
            sl = signal['stop_loss']
            
            if signal['direction'] == 'LONG':
                if tp1 <= entry or sl >= entry:
                    return False
            else:  # SHORT
                if tp1 >= entry or sl <= entry:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"خطأ في التحقق من الإشارة: {e}")
            return False

# مثال للاستخدام
if __name__ == "__main__":
    parser = TradingSignalParser()
    
    # مثال على إشارة
    test_signal = """
📢 Trade Signal Detected!

📊 Symbol: LTCUSDT.P
🔁 Direction: LONG
📍 Entry Price: 87.798
🎯 Take Profit 1: 88.503
🎯 Take Profit 2: 90.2514
⛔ Stop Loss: 86.67
"""
    
    result = parser.parse_signal(test_signal)
    if result:
        print("تم تحليل الإشارة بنجاح:")
        for key, value in result.items():
            print(f"{key}: {value}")
    else:
        print("فشل في تحليل الإشارة")

