import os
import ccxt
import math
import logging
import requests
import json
import time
import hmac
import hashlib
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

    def _get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """جلب معلومات الرمز من API Bybit المباشر"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            url = "https://api.bybit.com/v5/market/instruments-info"
            params = {"category": "linear", "symbol": formatted_symbol}
            response = requests.get(url, params=params)
            data = response.json()
            if data['retCode'] == 0 and data['result']['list']:
                info = data['result']['list'][0]
                return {
                    'min_quantity': float(info['lotSizeFilter']['minOrderQty']),
                    'quantity_step': float(info['lotSizeFilter']['qtyStep']),
                    'price_precision': float(info['priceFilter']['tickSize']),
                    'max_leverage': float(info['leverageFilter']['maxLeverage'])
                }
            else:
                logger.error(f"❌ فشل في جلب معلومات الرمز: {data}")
                raise Exception("فشل في جلب معلومات الرمز")
        except Exception as e:
            logger.error(f"❌ خطأ في جلب معلومات الرمز: {e}")
            raise

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """تقريب الكمية حسب قواعد Bybit"""
        try:
            symbol_info = self._get_symbol_info(symbol)
            min_quantity = symbol_info['min_quantity']
            step = symbol_info['quantity_step']
            rounded = math.floor(quantity / step) * step
            if rounded < min_quantity:
                logger.warning(f"⚠️ الكمية {rounded} أقل من الحد الأدنى {min_quantity} لـ {symbol}")
                rounded = min_quantity
            logger.info(f"📏 الكمية بعد التقريب: {rounded} (الحد الأدنى: {min_quantity}, الخطوة: {step})")
            return rounded
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تقريب الكمية: {e}")
            return round(quantity, 3)

    def _round_price(self, symbol: str, price: float) -> float:
        """تقريب السعر حسب قواعد Bybit"""
        try:
            symbol_info = self._get_symbol_info(symbol)
            tick_size = symbol_info['price_precision']
            return round(price / tick_size) * tick_size
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تقريب السعر: {e}")
            return round(price, 8)

    def get_balance(self) -> float:
        """الحصول على رصيد USDT من محفظة الفيوتشر"""
        try:
            balance = self.exchange.fetch_balance(params={'type': 'future', 'category': 'linear'})
            usdt_balance = balance['USDT']['free']
            logger.info(f"💰 رصيد محفظة الفيوتشر USDT: {usdt_balance}")
            return usdt_balance
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على رصيد المحفظة: {e}")
            return 0

    def calculate_position_size(self, symbol: str, entry_price: float) -> float:
        """حساب حجم المركز بناءً على نسبة رأس المال مع التحقق من الرصيد"""
        try:
            balance = self.get_balance()
            if balance <= 0:
                raise RuntimeError("رصيد غير كافي")
            position_value = balance * (self.capital_percentage / 100)
            quantity = position_value / entry_price
            formatted_symbol = self._format_symbol(symbol)
            rounded_qty = self._round_quantity(formatted_symbol, quantity)
            # التحقق من أن القيمة الناتجة لا تتجاوز الرصيد
            required_value = rounded_qty * entry_price
            if required_value > balance:
                # تقليل الكمية لتتناسب مع الرصيد
                max_qty = math.floor((balance / entry_price) / self._get_symbol_info(symbol)['quantity_step']) * self._get_symbol_info(symbol)['quantity_step']
                if max_qty >= self._get_symbol_info(symbol)['min_quantity']:
                    rounded_qty = max_qty
                    logger.warning(f"⚠️ تم تقليل الكمية إلى {rounded_qty} لتتناسب مع الرصيد {balance} USDT")
                else:
                    raise RuntimeError(f"❌ القيمة المطلوبة {required_value} USDT تتجاوز الرصيد {balance} USDT ولا يمكن تقليل الكمية أكثر")
            logger.info(f"💰 قيمة المركز: {position_value} USDT")
            logger.info(f"📊 الكمية: {rounded_qty}")
            return rounded_qty
        except Exception as e:
            logger.error(f"❌ خطأ في حساب حجم المركز: {e}")
            raise

    def get_max_leverage(self, symbol: str) -> float:
        """جلب أقصى رافعة مالية متاحة لرمز معين"""
        try:
            symbol_info = self._get_symbol_info(symbol)
            max_leverage = symbol_info['max_leverage']
            logger.info(f"⚡ أقصى رافعة مالية لـ {symbol}: {max_leverage}x")
            return max_leverage
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
            try:
                result = self.exchange.set_leverage(leverage, formatted_symbol, params={'category': 'linear'})
                logger.info(f"✅ تم تعيين الرافعة المالية بنجاح: {result}")
                return True
            except Exception as ccxt_error:
                logger.warning(f"⚠️ فشل تعيين الرافعة عبر ccxt: {ccxt_error}")
                if "leverage not modified" in str(ccxt_error).lower():
                    logger.info(f"⚠️ الرافعة {leverage}x هي الرافعة الحالية، متابعة...")
                    return True
                # محاولة تعيين الرافعة عبر API Bybit المباشر
                url = "https://api.bybit.com/v5/position/set-leverage"
                timestamp = str(int(time.time() * 1000))
                payload = {
                    "category": "linear",
                    "symbol": formatted_symbol,
                    "buyLeverage": str(int(leverage)),
                    "sellLeverage": str(int(leverage))
                }
                param_str = timestamp + self.api_key + "5000" + json.dumps(payload)
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    param_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers = {
                    "X-BAPI-API-KEY": self.api_key,
                    "X-BAPI-SIGN": signature,
                    "X-BAPI-TIMESTAMP": timestamp,
                    "X-BAPI-RECV-WINDOW": "5000",
                    "Content-Type": "application/json"
                }
                response = requests.post(url, headers=headers, json=payload)
                data = response.json()
                if data['retCode'] == 0:
                    logger.info(f"✅ تم تعيين الرافعة عبر API Bybit: {data}")
                    return True
                else:
                    logger.error(f"❌ فشل تعيين الرافعة عبر API Bybit: {data}")
                    return False
        except Exception as e:
            logger.error(f"❌ خطأ في تعيين الرافعة: {str(e)}")
            logger.warning("⚠️ متابعة باستخدام الرافعة الحالية")
            return True

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
        """إنشاء أمر سوقي مع إضافة وقف الخسارة وجني الأرباح عبر API Bybit"""
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
            logger.info(f"✅ تم إنشاء الأمر السوقي: {order['id']}")
            
            # إضافة وقف الخسارة عبر API Bybit المباشر
            if stop_loss:
                rounded_sl = self._round_price(formatted_symbol, stop_loss)
                sl_side = "Sell" if side == "buy" else "Buy"
                logger.info(f"📋 إنشاء أمر وقف الخسارة: سعر={rounded_sl}, اتجاه={sl_side}")
                url = "https://api.bybit.com/v5/order/create"
                timestamp = str(int(time.time() * 1000))
                payload = {
                    "category": "linear",
                    "symbol": formatted_symbol,
                    "side": sl_side,
                    "orderType": "Market",
                    "qty": str(rounded_amount),
                    "stopLossPrice": str(rounded_sl),
                    "reduceOnly": True
                }
                param_str = timestamp + self.api_key + "5000" + json.dumps(payload)
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    param_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers = {
                    "X-BAPI-API-KEY": self.api_key,
                    "X-BAPI-SIGN": signature,
                    "X-BAPI-TIMESTAMP": timestamp,
                    "X-BAPI-RECV-WINDOW": "5000",
                    "Content-Type": "application/json"
                }
                response = requests.post(url, headers=headers, json=payload)
                data = response.json()
                if data['retCode'] == 0:
                    logger.info(f"✅ تم تعيين وقف الخسارة: {rounded_sl} (Order ID: {data['result']['orderId']})")
                else:
                    logger.error(f"❌ فشل في تعيين وقف الخسارة: {data}")
                    raise Exception(f"فشل في تعيين وقف الخسارة: {data}")

            # إضافة جني الأرباح عبر API Bybit المباشر
            if take_profit:
                rounded_tp = self._round_price(formatted_symbol, take_profit)
                tp_side = "Sell" if side == "buy" else "Buy"
                logger.info(f"📋 إنشاء أمر جني الأرباح: سعر={rounded_tp}, اتجاه={tp_side}")
                url = "https://api.bybit.com/v5/order/create"
                timestamp = str(int(time.time() * 1000))
                payload = {
                    "category": "linear",
                    "symbol": formatted_symbol,
                    "side": tp_side,
                    "orderType": "Market",
                    "qty": str(rounded_amount),
                    "takeProfitPrice": str(rounded_tp),
                    "reduceOnly": True
                }
                param_str = timestamp + self.api_key + "5000" + json.dumps(payload)
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    param_str.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers = {
                    "X-BAPI-API-KEY": self.api_key,
                    "X-BAPI-SIGN": signature,
                    "X-BAPI-TIMESTAMP": timestamp,
                    "X-BAPI-RECV-WINDOW": "5000",
                    "Content-Type": "application/json"
                }
                response = requests.post(url, headers=headers, json=payload)
                data = response.json()
                if data['retCode'] == 0:
                    logger.info(f"✅ تم تعيين جني الأرباح: {rounded_tp} (Order ID: {data['result']['orderId']})")
                else:
                    logger.error(f"❌ فشل في تعيين جني الأرباح: {data}")
                    raise Exception(f"فشل في تعيين جني الأرباح: {data}")

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
            self.set_leverage(symbol)  # لا تتوقف إذا فشل تعيين الرافعة
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

    def _sign_request(self, method: str, url: str, payload: Dict) -> str:
        """إنشاء توقيع للطلبات المباشرة إلى API Bybit"""
        try:
            timestamp = str(int(time.time() * 1000))
            param_str = timestamp + self.api_key + "5000" + json.dumps(payload)
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                param_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return signature
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء التوقيع: {e}")
            raise
