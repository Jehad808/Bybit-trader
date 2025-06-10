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
            raise RuntimeError("❌ مفاتيح Bybit غير موجودة! تأكد من Bybit مفاتيح config.ini أو المتغيرات البيئية.")
        
        # إعداد الاتصال
        self.exchange = ccxt.bybit({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "sandbox": False,  # استخدام البيئة الحقيقية
            "options": {
                "defaultType": "future",  # العقود الآجلة
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
        
        # إعداد الجدول
        self.leverage = int(self.config.get("BYBIT", "LEVERAGE", fallback=100))
        self.capital_percentage = float(self.config.get("BYBIT", "CAPITAL_PERCENTAGE", fallback=2))
        
        logger.info(f"✅ تم تهيئة Bybit API - رافعة: {self.leverage}x، نسبة رأس المال: {self.capital_percentage}%")

    def _format_symbol(self, symbol: str) -> str:
        """تنسيق رمز العملة لـ Bybit - الإصلاح الجديد"""
        # إزالة .P إذا كان موجود
        symbol = symbol.replace('.P', '')
        
        # التأكد من وجود USDT
        if not symbol.endswith('USDT'):
            if 'USDT' not in symbol:
                symbol = symbol + 'USDT'
        
        # إرجاع الرمز بدون تنسيق ccxt الإضافي
        # هذا هو الإصلاح الرئيسي - Bybit يقبل "BTCUSDT" وليس "BTCUSDT/USDT:USDT"
        return symbol

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
            logger.warning(f"⚠️ خطأ في تقريب الكمية: {e}")
            return round(quantity, 3)

    def _round_price(self, symbol: str, price: float) -> float:
        """تقريب السعر حسب قواعد Bybit"""
        try:
            market = self.exchange.market(symbol)
            tick_size = market["precision"]["price"] or 0.01
            
            return round(price / tick_size) * tick_size
            
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تقريب السعر: {e}")
            return round(price, 2)

    def get_balance(self) -> float:
        """الحصول على رصيد USDT"""
        try:
            balance = self.exchange.fetch_balance({"type": "future"})
            usdt_balance = balance["total"].get("USDT", 0)
            logger.info(f"💰 رصيد USDT: {usdt_balance}")
            return usdt_balance
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على الرصيد: {e}")
            return 0

    def calculate_position_size(self, symbol: str, entry_price: float) -> float:
        """حساب حجم المركز"""
        try:
            balance = self.get_balance()
            if balance <= 0:
                raise ValueError("رصيد غير كافي")
            
            # حساب قيمة المركز (نسبة من رأس المال)
            position_value = balance * (self.capital_percentage / 100)
            
            # حساب الكمية
            quantity = position_value / entry_price
            
            # تقريب الكمية
            formatted_symbol = self._format_symbol(symbol)
            rounded_quantity = self._round_quantity(formatted_symbol, quantity)
            
            logger.info(f"💰 قيمة المركز: {position_value} USDT")
            logger.info(f"📊 الكمية: {rounded_quantity}")
            
            return rounded_quantity
            
        except Exception as e:
            logger.error(f"❌ خطأ في حساب حجم المركز: {e}")
            raise

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """تعيين الرافعة المالية - مع الإصلاح الجديد"""
        try:
            # استخدام الرمز المُنسق الجديد
            formatted_symbol = self._format_symbol(symbol)
            
            logger.info(f"⚡ تعيين الرافعة المالية {leverage}x للرمز {formatted_symbol}")
            
            # تعيين الرافعة المالية
            result = self.exchange.set_leverage(leverage, formatted_symbol)
            
            logger.info(f"✅ تم تعيين الرافعة المالية بنجاح: {result}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تعيين الرافعة: {e}")
            return False

    def create_market_order(self, symbol: str, side: str, amount: float, 
                          stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """إنشاء أمر سوق مع وقف الخسارة والهدف"""
        try:
            # تنسيق الرمز
            formatted_symbol = self._format_symbol(symbol)
            
            # تقريب الكمية
            rounded_amount = self._round_quantity(formatted_symbol, amount)
            
            logger.info(f"📝 إنشاء أمر {side} للرمز {formatted_symbol}")
            logger.info(f"📊 الكمية: {rounded_amount}")
            
            # إنشاء الأمر الأساسي
            order = self.exchange.create_market_order(
                formatted_symbol, 
                side, 
                rounded_amount
            )
            
            logger.info(f"✅ تم إنشاء الأمر: {order['id']}")
            
            # إضافة وقف الخسارة والهدف إذا كانا موجودين
            if stop_loss:
                try:
                    rounded_sl = self._round_price(formatted_symbol, stop_loss)
                    sl_side = 'sell' if side == 'buy' else 'buy'
                    
                    sl_order = self.exchange.create_order(
                        formatted_symbol,
                        'stop_market',
                        sl_side,
                        rounded_amount,
                        None,
                        None,
                        {'stopPrice': rounded_sl, 'reduceOnly': True}
                    )
                    
                    logger.info(f"✅ تم تعيين وقف الخسارة: {rounded_sl}")
                    order['stop_loss'] = sl_order
                    
                except Exception as e:
                    logger.warning(f"⚠️ فشل في تعيين وقف الخسارة: {e}")
            
            if take_profit:
                try:
                    rounded_tp = self._round_price(formatted_symbol, take_profit)
                    tp_side = 'sell' if side == 'buy' else 'buy'
                    
                    tp_order = self.exchange.create_limit_order(
                        formatted_symbol,
                        tp_side,
                        rounded_amount,
                        rounded_tp,
                        None,
                        {'reduceOnly': True}
                    )
                    
                    logger.info(f"✅ تم تعيين الهدف: {rounded_tp}")
                    order['take_profit'] = tp_order
                    
                except Exception as e:
                    logger.warning(f"⚠️ فشل في تعيين الهدف: {e}")
            
            return order
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الأمر: {e}")
            raise

    def open_position(self, symbol: str, direction: str, entry_price: float,
                     stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """فتح مركز جديد"""
        try:
            logger.info(f"🚀 فتح مركز {direction} للرمز {symbol}")
            
            # تعيين الرافعة المالية
            if not self.set_leverage(symbol, self.leverage):
                raise Exception("فشل في تعيين الرافعة المالية")
            
            # حساب حجم المركز
            position_size = self.calculate_position_size(symbol, entry_price)
            
            # تحديد اتجاه الأمر
            side = 'buy' if direction.upper() == 'LONG' else 'sell'
            
            # إنشاء الأمر
            order = self.create_market_order(
                symbol, 
                side, 
                position_size,
                stop_loss,
                take_profit
            )
            
            logger.info(f"✅ تم فتح المركز بنجاح")
            
            return {
                'status': 'success',
                'order': order,
                'symbol': symbol,
                'direction': direction,
                'size': position_size,
                'entry_price': entry_price
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في فتح المركز: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def get_positions(self) -> list:
        """الحصول على المراكز المفتوحة"""
        try:
            positions = self.exchange.fetch_positions()
            open_positions = [pos for pos in positions if pos['contracts'] > 0]
            
            logger.info(f"📊 المراكز المفتوحة: {len(open_positions)}")
            return open_positions
            
        except Exception as e:
            logger.error(f"❌ خطأ في جلب المراكز: {e}")
            return []

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """إغلاق مركز"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            
            # الحصول على المركز الحالي
            positions = self.exchange.fetch_positions([formatted_symbol])
            position = next((pos for pos in positions if pos['contracts'] > 0), None)
            
            if not position:
                return {'status': 'error', 'message': 'لا يوجد مركز مفتوح'}
            
            # تحديد اتجاه الإغلاق
            side = 'sell' if position['side'] == 'long' else 'buy'
            amount = abs(position['contracts'])
            
            # إنشاء أمر إغلاق
            order = self.exchange.create_market_order(
                formatted_symbol,
                side,
                amount,
                None,
                None,
                {'reduceOnly': True}
            )
            
            logger.info(f"✅ تم إغلاق المركز: {symbol}")
            
            return {
                'status': 'success',
                'order': order
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في إغلاق المركز: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

