import os
import ccxt
import math
import logging
import requests
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
        self.capital_percentage = float(self.config.get("BYBIT", "CAPITAL_PERCENTAGE", fallback=5))
        
        logger.info(f"✅ تم تهيئة Bybit API - نسبة رأس المال: {self.capital_percentage}%")

    def _format_symbol(self, symbol: str) -> str:
        """تنسيق رمز العملة لـ Bybit"""
        symbol = symbol.replace('.P', '')
        if not symbol.endswith('USDT'):
            if 'USDT' not in symbol:
                symbol = symbol + 'USDT'
        return symbol

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """تقريب الكمية حسب قواعد Bybit"""
        try:
            market = self.exchange.market(symbol)
            min_amount = market["limits"]["amount"]["min"] or 0.001
            step = market["precision"]["amount"] or 0.001
            rounded = math.floor(quantity / step) * step
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
        """الحصول على رصيد USDT من محفظة الفيوتشر"""
        try:
            balance = self.exchange.fetch_balance(params={'type': 'future'})
            usdt_balance = balance['USDT']['free']
            logger.info(f"💰 رصيد محفظة الفيوتشر USDT: {usdt_balance}")
            return usdt_balance
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على رصيد المحفظة: {e}")
            return 0

    def calculate_position_size(self, symbol: str, entry_price: float) -> float:
        """حساب حجم المركز بناءً على 5% من رصيد محفظة الفيوتشر"""
        try:
            balance = self.get_balance()
            if balance <= 0:
                raise ValueError("رصيد غير كافي")
            position_value = balance * (self.capital_percentage / 100)
            quantity = position_value / entry_price
            formatted_symbol = self._format_symbol(symbol)
            rounded_quantity = self._round_quantity(formatted_symbol, quantity)
            logger.info(f"💰 قيمة المركز: {position_value} USDT")
            logger.info(f"📊 الكمية: {rounded_quantity}")
            return rounded_quantity
        except Exception as e:
            logger.error(f"❌ خطأ في حساب حجم المركز: {e}")
            raise

    def get_max_leverage(self, symbol: str) -> float:
        """جلب أقصى رافعة مالية متاحة لرمز معين عبر API مباشر"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            url = "https://api.bybit.com/v5/market/instruments-info"
            params = {"category": "linear", "symbol": formatted_symbol}
            response = requests.get(url, params=params)
            data = response.json()
            if data['retCode'] == 0 and data['result']['list']:
                max_leverage = float(data['result']['list'][0]['leverageFilter']['maxLeverage'])
                logger.info(f"⚡ أقصى رافعة مالية لـ {formatted_symbol}: {max_leverage}x")
                return max_leverage
            else:
                logger.error(f"❌ فشل في جلب معلومات الأداة: {data}")
                raise Exception("فشل في جلب معلومات الأداة")
        except Exception as e:
            logger.error(f"❌ خطأ في جلب أقصى رافعة مالية: {e}")
            logger.warning("⚠️ استخدام رافعة افتراضية 20x")
            return 20.0

    def set_leverage(self, symbol: str) -> bool:
        """تعيين أقصى رافعة مالية متاحة للرمز"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            leverage = self.get_max_leverage(formatted_symbol)
            logger.info(f"⚡ تعيين الرافعة المالية {leverage}x للرمز {formatted_symbol}")
            params = {'category': 'linear'}  # تحديد السوق الخطي صراحة
            result = self.exchange.set_leverage(leverage, formatted_symbol, params)
            logger.info(f"✅ تم تعيين الرافعة المالية بنجاح: {result}")
            return True
        except Exception as set_error:
            logger.warning(f"⚠️ فشل تعيين الرافعة {leverage}x: {set_error}")
            fallback_leverage = 10.0
            logger.info(f"⚡ محاولة تعيين رافعة أقل {fallback_leverage}x")
            try:
                params = {'category': 'linear'}
                result = self.exchange.set_leverage(fallback_leverage, formatted_symbol, params)
                logger.info(f"✅ تم تعيين الرافعة الاحتياطية بنجاح: {result}")
                return True
            except Exception as fallback_error:
                logger.error(f"❌ خطأ في تعيين الرافعة الاحتياطية: {fallback_error}")
                return False

    def set_margin_mode(self, symbol: str, mode: str = "cross") -> bool:
        """ضبط وضع الرافعة المالية إلى 'cross' أو 'isolated'"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            self.exchange.set_margin_mode(mode, formatted_symbol, params={'category': 'linear'})
            logger.info(f"✅ تم ضبط وضع الرافعة المالية لـ {formatted_symbol} إلى {mode}")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في ضبط وضع الرافعة المالية: {e}")
            return False

    def create_market_order(self, symbol: str, side: str, amount: float, 
                          stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """إنشاء أمر سوق مع إضافة وقف الخسارة والهدف كأوامر منفصلة"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_amount = self._round_quantity(formatted_symbol, amount)
            logger.info(f"📝 إنشاء أمر {side} للرمز {formatted_symbol}")
            logger.info(f"📊 الكمية: {rounded_amount}")
            
            # إنشاء الأمر السوقي الأساسي
            order = self.exchange.create_market_order(
                formatted_symbol, 
                side, 
                rounded_amount,
                params={'reduceOnly': False, 'category': 'linear'}
            )
            logger.info(f"✅ تم إنشاء الأمر: {order['id']}")
            
            # إضافة وقف الخسارة
            if stop_loss:
                rounded_sl = self._round_price(formatted_symbol, stop_loss)
                sl_side = 'sell' if side == 'buy' else 'buy'
                trigger_direction = 'below' if side == 'buy' else 'above'  # SL لـ LONG: below, SHORT: above
                sl_params = {
                    'stopPrice': rounded_sl,
                    'triggerDirection': trigger_direction,
                    'reduceOnly': True,
                    'category': 'linear'
                }
                sl_order = self.exchange.create_order(
                    formatted_symbol,
                    'stop',
                    sl_side,
                    rounded_amount,
                    None,
                    sl_params
                )
                logger.info(f"✅ تم تعيين وقف الخسارة: {rounded_sl} (Order ID: {sl_order['id']})")
            
            # إضافة جني الأرباح
            if take_profit:
                rounded_tp = self._round_price(formatted_symbol, take_profit)
                tp_side = 'sell' if side == 'buy' else 'buy'
                trigger_direction = 'above' if side == 'buy' else 'below'  # TP لـ LONG: above, SHORT: below
                tp_params = {
                    'stopPrice': rounded_tp,
                    'triggerDirection': trigger_direction,
                    'reduceOnly': True,
                    'category': 'linear'
                }
                tp_order = self.exchange.create_order(
                    formatted_symbol,
                    'takeProfit',
                    tp_side,
                    rounded_amount,
                    None,
                    tp_params
                )
                logger.info(f"✅ تم تعيين الهدف: {rounded_tp} (Order ID: {tp_order['id']})")
            
            return order
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الأمر: {e}")
            raise

    def open_position(self, symbol: str, direction: str, entry_price: float,
                     stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """فتح مركز جديد"""
        try:
            logger.info(f"🚀 فتح مركز {direction} للرمز {symbol}")
            if not self.set_margin_mode(symbol, "cross"):
                raise Exception("فشل في ضبط وضع الرافعة المالية إلى 'cross'")
            if not self.set_leverage(symbol):
                logger.warning("⚠️ فشل تعيين الرافعة المالية، متابعة باستخدام الرافعة الحالية")
            position_size = self.calculate_position_size(symbol, entry_price)
            side = 'buy' if direction.upper() == 'LONG' else 'sell'
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
            positions = self.exchange.fetch_positions(params={'category': 'linear'})
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
            positions = self.exchange.fetch_positions([formatted_symbol], params={'category': 'linear'})
            position = next((pos for pos in positions if pos['contracts'] > 0), None)
            if not position:
                return {'status': 'error', 'message': 'لا يوجد مركز مفتوح'}
            side = 'sell' if position['side'] == 'long' else 'buy'
            amount = abs(position['contracts'])
            order = self.exchange.create_market_order(
                formatted_symbol,
                side,
                amount,
                params={'reduceOnly': True, 'category': 'linear'}
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
