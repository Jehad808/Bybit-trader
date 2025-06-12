import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TradingSignalParser:
    """محلل إشارات التداول المثالي - يدعم جميع أنماط الإشارات"""
    
    def __init__(self):
        # نماذج regex محسنة لاستخراج البيانات
        self.patterns = {
            'symbol': [
                r'Symbol[:\s]*([A-Z0-9]+\.?P?)',
                r'📊\s*Symbol[:\s]*([A-Z0-9]+\.?P?)',
                r'الرمز[:\s]*([A-Z0-9]+\.?P?)',
                r'العملة[:\s]*([A-Z0-9]+\.?P?)',
                r'([A-Z]{2,10}USDT\.?P?)\b',  # نمط محسن للرموز
                r'([A-Z]{2,10})\s*/?USDT'
            ],
            'direction': [
                r'Direction[:\s]*(LONG|SHORT|BUY|SELL)',
                r'🔁\s*Direction[:\s]*(LONG|SHORT|BUY|SELL)',
                r'الاتجاه[:\s]*(LONG|SHORT|BUY|SELL|شراء|بيع)',
                r'نوع الصفقة[:\s]*(LONG|SHORT|BUY|SELL|شراء|بيع)',
                r'\b(LONG|SHORT|BUY|SELL)\b'
            ],
            'entry_price': [
                r'Entry Price[:\s]*([0-9]+\.?[0-9]*)',
                r'📍\s*Entry Price[:\s]*([0-9]+\.?[0-9]*)',
                r'سعر الدخول[:\s]*([0-9]+\.?[0-9]*)',
                r'الدخول[:\s]*([0-9]+\.?[0-9]*)',
                r'@\s*([0-9]+\.?[0-9]*)',
                r'Price[:\s]*([0-9]+\.?[0-9]*)'
            ],
            'take_profit_1': [
                r'Take Profit 1[:\s]*([0-9]+\.?[0-9]*)',
                r'🎯\s*Take Profit 1[:\s]*([0-9]+\.?[0-9]*)',
                r'الهدف الأول[:\s]*([0-9]+\.?[0-9]*)',
                r'TP1[:\s]*([0-9]+\.?[0-9]*)',
                r'Target 1[:\s]*([0-9]+\.?[0-9]*)',
                r'🎯.*?([0-9]+\.?[0-9]*)'
            ],
            'take_profit_2': [
                r'Take Profit 2[:\s]*([0-9]+\.?[0-9]*)',
                r'🎯\s*Take Profit 2[:\s]*([0-9]+\.?[0-9]*)',
                r'الهدف الثاني[:\s]*([0-9]+\.?[0-9]*)',
                r'TP2[:\s]*([0-9]+\.?[0-9]*)',
                r'Target 2[:\s]*([0-9]+\.?[0-9]*)'
            ],
            'stop_loss': [
                r'Stop Loss[:\s]*([0-9]+\.?[0-9]*)',
                r'⛔\s*Stop Loss[:\s]*([0-9]+\.?[0-9]*)',
                r'وقف الخسارة[:\s]*([0-9]+\.?[0-9]*)',
                r'SL[:\s]*([0-9]+\.?[0-9]*)',
                r'Stop[:\s]*([0-9]+\.?[0-9]*)',
                r'⛔.*?([0-9]+\.?[0-9]*)'
            ]
        }

    def extract_field(self, text: str, field: str) -> Optional[str]:
        """استخراج حقل معين من النص"""
        if field not in self.patterns:
            return None
        
        for pattern in self.patterns[field]:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result = match.group(1).strip()
                logger.debug(f"استخراج {field}: {result}")
                return result
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
        
        # إزالة .P إذا كان موجود
        symbol = symbol.replace('.P', '')
        
        # التأكد من وجود USDT
        if not symbol.endswith('USDT'):
            if 'USDT' not in symbol:
                symbol = symbol + 'USDT'
        
        return symbol

    def extract_multiple_targets(self, text: str) -> list:
        """استخراج أهداف متعددة من النص"""
        targets = []
        
        # البحث عن جميع الأهداف
        target_patterns = [
            r'🎯\s*Take Profit \d+[:\s]*([0-9]+\.?[0-9]*)',
            r'Target \d+[:\s]*([0-9]+\.?[0-9]*)',
            r'TP\d+[:\s]*([0-9]+\.?[0-9]*)',
            r'الهدف \d+[:\s]*([0-9]+\.?[0-9]*)'
        ]
        
        for pattern in target_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    targets.append(float(match))
                except ValueError:
                    continue
        
        return sorted(set(targets))  # إزالة المكررات وترتيب

    def parse_signal(self, message_text: str) -> Optional[Dict[str, Any]]:
        """تحليل إشارة التداول من نص الرسالة"""
        try:
            if not message_text:
                return None
            
            # التحقق من وجود كلمات مفتاحية للإشارة
            signal_keywords = [
                'Trade Signal', 'Symbol', 'Direction', 'Entry Price',
                'Take Profit', 'Stop Loss', 'إشارة', 'الرمز',
                'وقف الخسارة', 'الهدف', 'سعر الدخول', 'LONG', 'SHORT',
                'BUY', 'SELL', '🎯', '⛔', '📊', '📍', '🔁'
            ]
            
            if not any(keyword.lower() in message_text.lower() for keyword in signal_keywords):
                logger.debug("لا توجد كلمات مفتاحية للإشارة")
                return None
            
            # استخراج البيانات الأساسية
            symbol = self.extract_field(message_text, 'symbol')
            direction = self.extract_field(message_text, 'direction')
            entry_price = self.extract_field(message_text, 'entry_price')
            
            # استخراج الأهداف
            take_profit_1 = self.extract_field(message_text, 'take_profit_1')
            take_profit_2 = self.extract_field(message_text, 'take_profit_2')
            
            # استخراج أهداف متعددة إذا لم نجد الأهداف الأساسية
            if not take_profit_1:
                targets = self.extract_multiple_targets(message_text)
                if targets:
                    take_profit_1 = str(targets[0])
                    if len(targets) > 1:
                        take_profit_2 = str(targets[1])
            
            # استخراج وقف الخسارة
            stop_loss = self.extract_field(message_text, 'stop_loss')
            
            # تطبيع البيانات
            symbol = self.normalize_symbol(symbol)
            direction = self.normalize_direction(direction)
            
            # التحقق من البيانات الأساسية
            if not all([symbol, direction, entry_price]):
                logger.warning("❌ بيانات الإشارة غير مكتملة")
                logger.debug(f"Symbol: {symbol}, Direction: {direction}, Entry: {entry_price}")
                return None
            
            # تحويل الأسعار إلى أرقام
            try:
                entry_price = float(entry_price)
                take_profit_1 = float(take_profit_1) if take_profit_1 else None
                take_profit_2 = float(take_profit_2) if take_profit_2 else None
                stop_loss = float(stop_loss) if stop_loss else None
            except ValueError as e:
                logger.error(f"❌ خطأ في تحويل الأسعار إلى أرقام: {e}")
                return None
            
            # إنشاء كائن الإشارة
            signal = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'take_profit_1': take_profit_1,
                'take_profit_2': take_profit_2,
                'stop_loss': stop_loss,
                'raw_text': message_text
            }
            
            logger.info(f"✅ تم تحليل إشارة بنجاح: {symbol} {direction} @ {entry_price}")
            return signal
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحليل الإشارة: {e}")
            return None

    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        """التحقق من صحة الإشارة"""
        try:
            # التحقق من البيانات الأساسية
            required_fields = ['symbol', 'direction', 'entry_price']
            for field in required_fields:
                if not signal.get(field):
                    logger.error(f"❌ حقل مطلوب مفقود: {field}")
                    return False
            
            # التحقق من صحة الاتجاه
            if signal['direction'] not in ['LONG', 'SHORT']:
                logger.error(f"❌ اتجاه غير صحيح: {signal['direction']}")
                return False
            
            # التحقق من صحة الأسعار
            if signal['entry_price'] <= 0:
                logger.error("❌ سعر الدخول يجب أن يكون أكبر من صفر")
                return False
            
            # التحقق من منطقية الأسعار (اختياري - لا يمنع التنفيذ)
            entry = signal['entry_price']
            tp1 = signal.get('take_profit_1')
            sl = signal.get('stop_loss')
            
            if tp1:
                if signal['direction'] == 'LONG' and tp1 <= entry:
                    logger.warning("⚠️ الهدف الأول أقل من سعر الدخول في صفقة LONG")
                elif signal['direction'] == 'SHORT' and tp1 >= entry:
                    logger.warning("⚠️ الهدف الأول أعلى من سعر الدخول في صفقة SHORT")
            
            if sl:
                if signal['direction'] == 'LONG' and sl >= entry:
                    logger.warning("⚠️ وقف الخسارة أعلى من سعر الدخول في صفقة LONG")
                elif signal['direction'] == 'SHORT' and sl <= entry:
                    logger.warning("⚠️ وقف الخسارة أقل من سعر الدخول في صفقة SHORT")
            
            logger.info("✅ الإشارة صحيحة ومقبولة")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من الإشارة: {e}")
            return False

