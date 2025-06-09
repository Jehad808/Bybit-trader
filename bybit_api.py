import os
import ccxt
import math
import logging
from decimal import Decimal
from typing import Dict, Any, Optional
import configparser

logger = logging.getLogger(__name__)

class BybitTradingAPI:
    """واجهة التداول مع منصة Bybit"""
    
    def __init__(self, config_file: str = "config.ini"):
        """تهيئة الاتصال مع Bybit"""
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # الحصول على مفاتيح API
        self.api_key = (
            os.getenv("BYBIT_API_KEY") or 
            self.config.get("BYBIT", "API_KEY", fallback=None)
        )
        self.api_secret = (
            os.getenv("BYBIT_API_SECRET") or 
            self.config.get("BYBIT", "API_SECRET", fallback=None)
        )
        
        if not (self.api_key and self.api_secret):
            raise RuntimeError("مفاتيح Bybit غير موجودة! تأكد من config.ini أو المتغيرات البيئية.")
        
        # إعداد الاتصال
        self.exchange = ccxt.bybit({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "sandbox": False,  # استخدام البيئة الحقيقية
            "options": {
                "defaultType": "future",   # العقود الآجلة
                "defaultSubType": "linear"  # USDT Perpetual
            },
        })
        
        # تحميل معلومات الأسواق
        try:
            self.exchange.load_markets()
            logger.info("✅ تم تحميل معلومات أسواق Bybit.")
        except Exception as e:
            logger.error(f"❌ فشل في تحميل معلومات أسواق Bybit: {e}")
            raise
        
        # إعدادات التداول
        self.leverage = int(self.config.get("BYBIT", "LEVERAGE", fallback=100))
        self.capital_percentage = float(self.config.get("BYBIT", "CAPITAL_PERCENTAGE", fallback=2))
        
        logger.info(f"✅ تم تهيئة Bybit API - رافعة: {self.leverage}x، نسبة رأس المال: {self.capital_percentage}%")
    
    def _format_symbol(self, symbol: str) -> str:
        """تنسيق رمز العملة لـ Bybit"""
        # إزالة .P إذا كانت موجودة
        symbol = symbol.replace('.P', '')
        
        # التأكد من وجود USDT
        if not symbol.endswith('USDT'):
            if 'USDT' not in symbol:
                symbol = symbol + 'USDT'
        
        # تنسيق ccxt
        return f"{symbol}/USDT:USDT"
    
    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """تقريب الكمية حسب قواعد Bybit"""
        try:
            market = self.exchange.market(symbol)
            min_amount = market["limits"]["amount"]["min"] or 0.001
            step = market["precision"]["amount"] or 0.001
            
            # تقريب للأسفل حسب الخطوة المسموحة
            rounded = math.floor(quantity / step) * step
            
            # التأكد من أن الكمية أكبر من الحد الأدنى
            return max(rounded, min_amount)
            
        except Exception as e:
            logger.warning(f"خطأ في تقريب الكمية: {e}")
            return round(quantity, 3)
    
    def _round_price(self, symbol: str, price: float) -> float:
        """تقريب السعر حسب قواعد Bybit"""
        try:
            market = self.exchange.market(symbol)
            tick_size = market["precision"]["price"] or 0.01
            
            return round(price / tick_size) * tick_size
            
        except Exception as e:
            logger.warning(f"خطأ في تقريب السعر: {e}")
            return round(price, 2)
    
    def get_balance(self) -> float:
        """الحصول على رصيد USDT"""
        try:
            balance = self.exchange.fetch_balance({"type": "future"})
            usdt_balance = balance["total"].get("USDT", 0)
            logger.info(f"💰 رصيد USDT: {usdt_balance}")
            return usdt_balance
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على الرصيد: {e}")
            return 0
    
    def calculate_position_size(self, symbol: str, entry_price: float) -> float:
        """حساب حجم المركز"""
        try:
            balance = self.get_balance()
            if balance <= 0:
                raise ValueError("رصيد غير كافي")
            
            # حساب المبلغ المخصص للصفقة
            trade_amount = balance * (self.capital_percentage / 100)
            
            # حساب الكمية مع الرافعة المالية
            quantity = (trade_amount * self.leverage) / entry_price
            
            # تقريب الكمية
            rounded_quantity = self._round_quantity(symbol, quantity)
            
            logger.info(f"📊 حجم المركز: {rounded_quantity} | مبلغ الصفقة: {trade_amount} USDT")
            return rounded_quantity
            
        except Exception as e:
            logger.error(f"خطأ في حساب حجم المركز: {e}")
            return 0
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """تعيين الرافعة المالية"""
        try:
            market = self.exchange.market(symbol)
            self.exchange.set_leverage(leverage, market["id"])
            logger.info(f"⚙️ تم تعيين الرافعة {leverage}x لـ {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في تعيين الرافعة: {e}")
            return False
    
    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        take_profit: float,
        stop_loss: float,
        pct: Optional[float] = None,
        leverage: Optional[int] = None
    ) -> Optional[str]:
        """
        فتح مركز تداول جديد
        
        Args:
            symbol: رمز العملة
            direction: اتجاه التداول (LONG/SHORT)
            entry_price: سعر الدخول
            take_profit: هدف الربح
            stop_loss: وقف الخسارة
            pct: نسبة رأس المال (اختياري)
            leverage: الرافعة المالية (اختياري)
        
        Returns:
            معرف الأمر أو None في حالة الفشل
        """
        try:
            # تنسيق الرمز
            formatted_symbol = self._format_symbol(symbol)
            
            # استخدام القيم الافتراضية إذا لم تُمرر
            pct = pct or self.capital_percentage
            leverage = leverage or self.leverage
            
            # تحديد اتجاه التداول
            if direction.upper() in ['LONG', 'BUY']:
                side = "buy"
                opposite_side = "sell"
            elif direction.upper() in ['SHORT', 'SELL']:
                side = "sell"
                opposite_side = "buy"
            else:
                raise ValueError(f"اتجاه تداول غير صالح: {direction}")
            
            # تعيين الرافعة المالية
            if not self.set_leverage(formatted_symbol, leverage):
                raise RuntimeError("فشل في تعيين الرافعة المالية")
            
            # حساب حجم المركز
            quantity = self.calculate_position_size(formatted_symbol, entry_price)
            if quantity <= 0:
                raise ValueError("حجم مركز غير صالح")
            
            # تقريب الأسعار
            take_profit = self._round_price(formatted_symbol, take_profit)
            stop_loss = self._round_price(formatted_symbol, stop_loss)
            
            logger.info(f"🚀 فتح مركز {direction} لـ {symbol}")
            logger.info(f"📊 الكمية: {quantity} | الرافعة: {leverage}x")
            logger.info(f"💰 TP: {take_profit} | SL: {stop_loss}")
            
            # 1. فتح المركز (أمر سوق)
            entry_order = self.exchange.create_order(
                symbol=formatted_symbol,
                type="market",
                side=side,
                amount=quantity,
                params={"reduce_only": False}
            )
            
            order_id = entry_order["id"]
            logger.info(f"✅ تم فتح المركز - Order ID: {order_id}")
            
            # 2. أمر جني الربح (Take Profit)
            try:
                tp_order = self.exchange.create_order(
                    symbol=formatted_symbol,
                    type="limit",
                    side=opposite_side,
                    amount=quantity,
                    price=take_profit,
                    params={"reduce_only": True}
                )
                logger.info(f"🎯 تم تعيين أمر جني الربح: {tp_order['id']}")
            except Exception as e:
                logger.warning(f"تحذير: فشل في تعيين أمر جني الربح: {e}")
            
            # 3. أمر وقف الخسارة (Stop Loss)
            try:
                sl_order = self.exchange.create_order(
                    symbol=formatted_symbol,
                    type="stop_market",
                    side=opposite_side,
                    amount=quantity,
                    params={
                        "stop_price": stop_loss,
                        "reduce_only": True
                    }
                )
                logger.info(f"⛔ تم تعيين أمر وقف الخسارة: {sl_order['id']}")
            except Exception as e:
                logger.warning(f"تحذير: فشل في تعيين أمر وقف الخسارة: {e}")
            
            return order_id
            
        except Exception as e:
            logger.error(f"❌ خطأ في فتح المركز: {e}")
            return None
    
    def close_position(self, symbol: str) -> bool:
        """إغلاق جميع المراكز لرمز معين"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            positions = self.exchange.fetch_positions([formatted_symbol])
            
            closed_any = False
            for position in positions:
                if position["contracts"] and float(position["contracts"]) != 0:
                    side = "sell" if position["side"] == "long" else "buy"
                    amount = abs(float(position["contracts"]))
                    
                    close_order = self.exchange.create_order(
                        symbol=formatted_symbol,
                        type="market",
                        side=side,
                        amount=amount,
                        params={"reduce_only": True}
                    )
                    
                    logger.info(f"🔒 تم إغلاق مركز {symbol}: {close_order['id']}")
                    closed_any = True
            
            return closed_any
            
        except Exception as e:
            logger.error(f"خطأ في إغلاق المركز: {e}")
            return False
    
    def get_positions(self, symbol: Optional[str] = None) -> list:
        """الحصول على المراكز المفتوحة"""
        try:
            if symbol:
                formatted_symbol = self._format_symbol(symbol)
                positions = self.exchange.fetch_positions([formatted_symbol])
            else:
                positions = self.exchange.fetch_positions()
            
            # تصفية المراكز المفتوحة فقط
            open_positions = [
                pos for pos in positions 
                if pos["contracts"] and float(pos["contracts"]) != 0
            ]
            
            return open_positions
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على المراكز: {e}")
            return []

# دالة مساعدة للتوافق مع الكود القديم
def open_position(symbol: str, direction: str, entry_price: float, 
                 take_profit: float, stop_loss: float, pct: float, leverage: int) -> str:
    """دالة مساعدة للتوافق مع الكود القديم"""
    api = BybitTradingAPI()
    return api.open_position(symbol, direction, entry_price, take_profit, stop_loss, pct, leverage)

def close_all_positions(symbol: str) -> bool:
    """دالة مساعدة لإغلاق جميع المراكز"""
    api = BybitTradingAPI()
    return api.close_position(symbol)