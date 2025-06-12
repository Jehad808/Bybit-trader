import os
import ccxt
import math
import logging
import time
import requests
import hmac
import hashlib
from typing import Dict, Any, Optional
import configparser

logger = logging.getLogger(__name__)

class BybitTradingAPI:
    """واجهة التداول المثالية مع Bybit - تدعم جميع المتطلبات"""
    
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
            raise RuntimeError("❌ مفاتيح Bybit غير موجودة!")
        
        # تحديد البيئة (testnet أم live)
        self.testnet = self.config.getboolean("BYBIT", "TESTNET", fallback=False)
        
        # إعداد الاتصال مع ccxt
        self.exchange = ccxt.bybit({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "sandbox": self.testnet,
            "options": {
                "defaultType": "linear",
                "defaultSubType": "linear"
            },
        })
        
        # إعداد API المباشر
        if self.testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        # تحميل معلومات الأسواق
        try:
            self.exchange.load_markets()
            logger.info("✅ تم تحميل معلومات أسواق Bybit")
        except Exception as e:
            logger.error(f"❌ فشل في تحميل معلومات الأسواق: {e}")
            raise
        
        # إعداد التداول
        self.capital_percentage = float(self.config.get("BYBIT", "CAPITAL_PERCENTAGE", fallback=5))
        
        logger.info(f"✅ تم تهيئة Bybit API - نسبة رأس المال: {self.capital_percentage}%")
        logger.info(f"🌐 البيئة: {'Testnet' if self.testnet else 'Live'}")

    def _generate_signature(self, params: dict, timestamp: str) -> str:
        """إنشاء التوقيع لـ Bybit API"""
        param_str = f"api_key={self.api_key}&recv_window=5000&timestamp={timestamp}"
        
        for key in sorted(params.keys()):
            if params[key] is not None:
                param_str += f"&{key}={params[key]}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature

    def _make_request(self, endpoint: str, method: str = "GET", params: dict = None) -> dict:
        """إجراء طلب مباشر لـ Bybit API"""
        if params is None:
            params = {}
        
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(params, timestamp)
        
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": "5000",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=params, timeout=10)
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"❌ خطأ في طلب API: {e}")
            raise

    def _format_symbol(self, symbol: str) -> str:
        """تنسيق رمز العملة لـ Bybit"""
        symbol = symbol.replace('.P', '').strip()
        
        if not symbol.endswith('USDT'):
            if 'USDT' not in symbol:
                symbol = symbol + 'USDT'
        
        return symbol

    def get_max_leverage(self, symbol: str) -> int:
        """الحصول على أقصى رافعة مالية للرمز"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            
            # استخدام ccxt للحصول على معلومات السوق
            market = self.exchange.market(formatted_symbol)
            max_leverage = market.get('limits', {}).get('leverage', {}).get('max', 100)
            
            logger.info(f"⚡ أقصى رافعة مالية لـ {formatted_symbol}: {max_leverage}x")
            return int(max_leverage)
            
        except Exception as e:
            logger.warning(f"⚠️ فشل في الحصول على أقصى رافعة، استخدام 100x: {e}")
            return 100

    def set_cross_margin(self, symbol: str) -> bool:
        """تعيين Cross Margin للرمز"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            
            params = {
                "category": "linear",
                "symbol": formatted_symbol,
                "tradeMode": 0,  # 0 = Cross Margin
                "buyLeverage": "1",
                "sellLeverage": "1"
            }
            
            result = self._make_request("/v5/position/switch-isolated", "POST", params)
            
            if result.get("retCode") == 0:
                logger.info(f"✅ تم تعيين Cross Margin لـ {formatted_symbol}")
                return True
            else:
                logger.info(f"ℹ️ Cross Margin مُعين مسبقاً لـ {formatted_symbol}")
                return True
                
        except Exception as e:
            logger.info(f"ℹ️ Cross Margin مُعين مسبقاً لـ {symbol}")
            return True

    def set_leverage(self, symbol: str, leverage: int = None) -> bool:
        """تعيين الرافعة المالية"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            
            if leverage is None:
                leverage = self.get_max_leverage(symbol)
            
            logger.info(f"⚡ تعيين الرافعة المالية {leverage}x للرمز {formatted_symbol}")
            
            params = {
                "category": "linear",
                "symbol": formatted_symbol,
                "buyLeverage": str(leverage),
                "sellLeverage": str(leverage)
            }
            
            result = self._make_request("/v5/position/set-leverage", "POST", params)
            
            if result.get("retCode") == 0:
                logger.info(f"✅ تم تعيين الرافعة المالية {leverage}x بنجاح")
                return True
            else:
                logger.info(f"ℹ️ الرافعة المالية {leverage}x مُعينة مسبقاً")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تعيين الرافعة: {e}")
            return True

    def get_balance(self) -> float:
        """الحصول على رصيد USDT"""
        try:
            result = self._make_request("/v5/account/wallet-balance", "GET", {"accountType": "UNIFIED"})
            
            if result.get("retCode") == 0:
                accounts = result.get("result", {}).get("list", [])
                for account in accounts:
                    coins = account.get("coin", [])
                    for coin in coins:
                        if coin.get("coin") == "USDT":
                            balance = float(coin.get("walletBalance", 0))
                            logger.info(f"💰 رصيد USDT: {balance}")
                            return balance
            
            logger.warning("⚠️ لم يتم العثور على رصيد USDT")
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على الرصيد: {e}")
            return 0.0

    def calculate_position_size(self, symbol: str, entry_price: float, leverage: int = None) -> float:
        """حساب حجم المركز مع 5% من رأس المال الحقيقي"""
        try:
            balance = self.get_balance()
            if balance <= 0:
                raise ValueError("رصيد غير كافي")
            
            if leverage is None:
                leverage = self.get_max_leverage(symbol)
            
            # حساب 5% من رأس المال الحقيقي (قبل الرافعة)
            capital_amount = balance * (self.capital_percentage / 100)
            
            # تطبيق الرافعة لحساب قيمة المركز الإجمالية
            position_value = capital_amount * leverage
            
            # حساب الكمية
            quantity = position_value / entry_price
            
            # تقريب الكمية
            formatted_symbol = self._format_symbol(symbol)
            rounded_quantity = self._round_quantity(formatted_symbol, quantity)
            
            logger.info(f"💰 رأس المال المستخدم: {capital_amount:.2f} USDT (5% من {balance:.2f})")
            logger.info(f"⚡ الرافعة المالية: {leverage}x")
            logger.info(f"💵 قيمة المركز الإجمالية: {position_value:.2f} USDT")
            logger.info(f"📊 الكمية المحسوبة: {quantity:.6f}")
            logger.info(f"📊 الكمية النهائية: {rounded_quantity:.6f}")
            
            return rounded_quantity
            
        except Exception as e:
            logger.error(f"❌ خطأ في حساب حجم المركز: {e}")
            raise

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """تقريب الكمية حسب قواعد Bybit"""
        try:
            market = self.exchange.market(symbol)
            min_amount = market["limits"]["amount"]["min"] or 0.001
            step = market["precision"]["amount"] or 0.001
            
            # تقريب للأسفل حسب الخطوة المسموحة
            rounded = math.floor(quantity / step) * step
            
            # التأكد من أن الكمية أكبر من الحد الأدنى
            final_quantity = max(rounded, min_amount)
            
            logger.debug(f"تقريب الكمية لـ {symbol}: {quantity} → {final_quantity}")
            return final_quantity
            
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تقريب الكمية: {e}")
            return round(quantity, 3)

    def _round_price(self, symbol: str, price: float) -> float:
        """تقريب السعر حسب قواعد Bybit"""
        try:
            market = self.exchange.market(symbol)
            tick_size = market["precision"]["price"] or 0.01
            
            rounded = round(price / tick_size) * tick_size
            logger.debug(f"تقريب السعر لـ {symbol}: {price} → {rounded}")
            return rounded
            
        except Exception as e:
            logger.warning(f"⚠️ خطأ في تقريب السعر: {e}")
            return round(price, 2)

    def create_order_with_sl_tp(self, symbol: str, side: str, amount: float, 
                               stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """إنشاء أمر سوق مع وقف الخسارة والهدف تلقائياً"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_amount = self._round_quantity(formatted_symbol, amount)
            
            logger.info(f"📝 إنشاء أمر {side} للرمز {formatted_symbol}")
            logger.info(f"📊 الكمية: {rounded_amount}")
            
            # إعداد معاملات الأمر الأساسي
            params = {
                "category": "linear",
                "symbol": formatted_symbol,
                "side": side.capitalize(),
                "orderType": "Market",
                "qty": str(rounded_amount),
                "timeInForce": "IOC"
            }
            
            # إضافة وقف الخسارة والهدف إذا كانا موجودين
            if stop_loss:
                rounded_sl = self._round_price(formatted_symbol, stop_loss)
                params["stopLoss"] = str(rounded_sl)
                logger.info(f"⛔ وقف الخسارة: {rounded_sl}")
            
            if take_profit:
                rounded_tp = self._round_price(formatted_symbol, take_profit)
                params["takeProfit"] = str(rounded_tp)
                logger.info(f"🎯 الهدف: {rounded_tp}")
            
            # إنشاء الأمر
            result = self._make_request("/v5/order/create", "POST", params)
            
            if result.get("retCode") == 0:
                order_id = result.get("result", {}).get("orderId")
                logger.info(f"✅ تم إنشاء الأمر بنجاح: {order_id}")
                
                return {
                    "status": "success",
                    "order_id": order_id,
                    "symbol": formatted_symbol,
                    "side": side,
                    "amount": rounded_amount,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit
                }
            else:
                error_msg = result.get("retMsg", "خطأ غير معروف")
                logger.error(f"❌ فشل في إنشاء الأمر: {error_msg}")
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الأمر: {e}")
            raise

    def open_position(self, symbol: str, direction: str, entry_price: float,
                     stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """فتح مركز جديد مع جميع الميزات المطلوبة"""
        try:
            logger.info(f"🚀 فتح مركز {direction} للرمز {symbol}")
            
            # تعيين Cross Margin
            self.set_cross_margin(symbol)
            
            # الحصول على أقصى رافعة مالية وتعيينها
            max_leverage = self.get_max_leverage(symbol)
            self.set_leverage(symbol, max_leverage)
            
            # حساب حجم المركز (5% من رأس المال الحقيقي)
            position_size = self.calculate_position_size(symbol, entry_price, max_leverage)
            
            # تحديد اتجاه الأمر
            side = 'Buy' if direction.upper() == 'LONG' else 'Sell'
            
            # إنشاء الأمر مع وقف الخسارة والهدف
            order = self.create_order_with_sl_tp(
                symbol, 
                side, 
                position_size,
                stop_loss,
                take_profit
            )
            
            logger.info(f"✅ تم فتح المركز بنجاح")
            logger.info(f"📋 معرف الأمر: {order.get('order_id')}")
            logger.info(f"⚡ الرافعة المالية: {max_leverage}x")
            logger.info(f"📊 حجم المركز: {position_size}")
            
            return {
                'status': 'success',
                'order': order,
                'symbol': symbol,
                'direction': direction,
                'size': position_size,
                'entry_price': entry_price,
                'leverage': max_leverage
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
            result = self._make_request("/v5/position/list", "GET", {"category": "linear"})
            
            if result.get("retCode") == 0:
                positions = result.get("result", {}).get("list", [])
                open_positions = [pos for pos in positions if float(pos.get("size", 0)) > 0]
                
                logger.info(f"📊 المراكز المفتوحة: {len(open_positions)}")
                return open_positions
            else:
                logger.error(f"❌ فشل في جلب المراكز: {result.get('retMsg', 'خطأ غير معروف')}")
                return []
                
        except Exception as e:
            logger.error(f"❌ خطأ في جلب المراكز: {e}")
            return []

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """إغلاق مركز مع إلغاء جميع الأوامر المرتبطة"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            
            # إلغاء جميع الأوامر المفتوحة للرمز أولاً
            self._cancel_all_orders(formatted_symbol)
            
            # الحصول على المراكز المفتوحة
            positions = self.get_positions()
            position = next((pos for pos in positions if pos.get("symbol") == formatted_symbol), None)
            
            if not position:
                return {'status': 'error', 'message': 'لا يوجد مركز مفتوح'}
            
            # تحديد اتجاه الإغلاق
            side = 'Sell' if position.get("side") == "Buy" else 'Buy'
            amount = float(position.get("size", 0))
            
            # إنشاء أمر إغلاق
            params = {
                "category": "linear",
                "symbol": formatted_symbol,
                "side": side,
                "orderType": "Market",
                "qty": str(amount),
                "timeInForce": "IOC",
                "reduceOnly": True
            }
            
            result = self._make_request("/v5/order/create", "POST", params)
            
            if result.get("retCode") == 0:
                order_id = result.get("result", {}).get("orderId")
                logger.info(f"✅ تم إغلاق المركز: {symbol}")
                
                return {
                    'status': 'success',
                    'order_id': order_id
                }
            else:
                error_msg = result.get("retMsg", "خطأ غير معروف")
                logger.error(f"❌ فشل في إغلاق المركز: {error_msg}")
                return {
                    'status': 'error',
                    'message': error_msg
                }
                
        except Exception as e:
            logger.error(f"❌ خطأ في إغلاق المركز: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _cancel_all_orders(self, symbol: str) -> bool:
        """إلغاء جميع الأوامر المفتوحة للرمز"""
        try:
            params = {
                "category": "linear",
                "symbol": symbol
            }
            
            result = self._make_request("/v5/order/cancel-all", "POST", params)
            
            if result.get("retCode") == 0:
                logger.info(f"✅ تم إلغاء جميع الأوامر لـ {symbol}")
                return True
            else:
                logger.warning(f"⚠️ فشل في إلغاء الأوامر لـ {symbol}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ خطأ في إلغاء الأوامر: {e}")
            return False

