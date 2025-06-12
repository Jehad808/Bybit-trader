import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TradingSignalParser:
    def __init__(self):
        self.patterns = {
            'symbol': [
                r'Symbol[:\s]*([A-Z0-9]+\.?P?)',
                r'📊\s*Symbol[:\s]*([A-Z0-9]+\.?P?)',
                r'الرمز[:\s]*([A-Z0-9]+\.?P?)',
                r'العملة[:\s]*([A-Z0-9]+\.?P?)',
                r'([A-Z0-9]+USDT)\b'
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
        if field not in self.patterns:
            return None
        for pattern in self.patterns[field]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def normalize_direction(self, direction: str) -> Optional[str]:
        if not direction:
            return None
        direction = direction.upper().strip()
        if direction in ['LONG', 'BUY', 'شراء']:
            return 'LONG'
        elif direction in ['SHORT', 'SELL', 'بيع']:
            return 'SHORT'
        return None

    def normalize_symbol(self, symbol: str) -> Optional[str]:
        if not symbol:
            return None
        symbol = symbol.upper().strip()
        symbol = re.sub(r'[^A-Z0-9.]', '', symbol)
        symbol = symbol.replace('.P', '')
        if not symbol.endswith('USDT'):
            if 'USDT' not in symbol:
                symbol = symbol + 'USDT'
        return symbol

    def parse_signal(self, message_text: str) -> Optional[Dict[str, Any]]:
        try:
            if not message_text:
                return None
            signal_keywords = [
                'Trade Signal', 'Symbol', 'Direction', 'Entry Price',
                'Take Profit', 'Stop Loss', 'إشارة', 'الرمز',
                'وقف الخسارة', 'الهدف', 'سعر الدخول'
            ]
            if not any(keyword.lower() in message_text.lower() for keyword in signal_keywords):
                return None
            symbol = self.extract_field(message_text, 'symbol')
            direction = self.extract_field(message_text, 'direction')
            entry_price = self.extract_field(message_text, 'entry_price')
            take_profit_1 = self.extract_field(message_text, 'take_profit_1')
            take_profit_2 = self.extract_field(message_text, 'take_profit_2')
            stop_loss = self.extract_field(message_text, 'stop_loss')
            symbol = self.normalize_symbol(symbol)
            direction = self.normalize_direction(direction)
            if not all([symbol, direction, entry_price]):
                logger.warning("❌ بيانات الإشارة غير مكتملة")
                return None
            try:
                entry_price = float(entry_price)
                take_profit_1 = float(take_profit_1) if take_profit_1 else None
                take_profit_2 = float(take_profit_2) if take_profit_2 else None
                stop_loss = float(stop_loss) if stop_loss else None
            except ValueError:
                logger.error("❌ خطأ في تحويل الأسعار إلى أرقام")
                return None
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
        try:
            required_fields = ['symbol', 'direction', 'entry_price', 'stop_loss', 'take_profit_1']
            for field in required_fields:
                if not signal.get(field):
                    logger.error(f"❌ حقل مطلوب مفقود: {field}")
                    return False
            if signal['direction'] not in ['LONG', 'SHORT']:
                logger.error(f"❌ اتجاه غير صحيح: {signal['direction']}")
                return False
            if signal['entry_price'] <= 0:
                logger.error("❌ سعر الدخول يجب أن يكون أكبر من صفر")
                return False
            entry = signal['entry_price']
            tp1 = signal.get('take_profit_1')
            sl = signal.get('stop_loss')
            if signal['direction'] == 'LONG':
                if tp1 <= entry:
                    logger.warning("⚠️ الهدف الأول أقل من سعر الدخول في صفقة LONG")
                    return False
                if sl >= entry:
                    logger.warning("⚠️ وقف الخسارة أعلى من سعر الدخول في صفقة LONG")
                    return False
            else:  # SHORT
                if tp1 >= entry:
                    logger.warning("⚠️ الهدف الأول أعلى من سعر الدخول في صفقة SHORT")
                    return False
                if sl <= entry:
                    logger.warning("⚠️ وقف الخسارة أقل من سعر الدخول في صفقة SHORT")
                    return False
            logger.info("✅ الإشارة صحيحة ومقبولة")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من الإشارة: {e}")
            return False
