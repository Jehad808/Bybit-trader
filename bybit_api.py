import os
import ccxt
import math
import logging
import requests
import json
import time
import hmac
import hashlib
from typing import Dict, Any, Optional
from decimal import Decimal
import configparser

logger = logging.getLogger(__name__)

class BybitAPI:
    """واجهة التداول مع منصة Bybit"""
    
    def __init__(self, config_file: str = "config.ini"):
        """Initialize Bybit connection"""
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Get API keys
        self.api_key = (
            os.getenv("BYBIT_API_KEY") or 
            self.config.get("BYBIT", "API_KEY", fallback=None)
        )
        self.api_secret = (
            os.getenv("BYBIT_API_SECRET") or 
            self.config.get("BYBIT", "API_SECRET", fallback=None)
        )
        
        if not (self.api_key and self.api_secret):
            raise RuntimeError("❌ Bybit API keys missing! Check config.ini or environment variables.")
        
        # Setup connection
        self.exchange = ccxt.bybit({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "sandbox": False,  # Use live environment
            "options": {
                "defaultType": "future",
                "defaultSubType": "linear"  # USDT Perpetual
            },
        })
        
        # Load markets
        try:
            self.exchange.load_markets()
            logger.info("✅ Loaded Bybit market data.")
        except Exception as e:
            logger.error(f"❌ Failed to load Bybit markets: {e}")
            raise
        
        # Load config
        self.capital_percentage = float(self.config.get("BYBIT", "CAPITAL_PERCENTAGE", fallback=10))
        
        logger.info(f"✅ Initialized Bybit API - Capital percentage: {self.capital_percentage}%")

    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for Bybit"""
        symbol = symbol.replace('.P', '')
        if not symbol.endswith('USDT'):
            if 'USDT' not in symbol:
                symbol = symbol + 'USDT'
        return symbol

    def _get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch symbol info from Bybit API"""
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
                logger.error(f"❌ Failed to fetch symbol info: {data}")
                raise Exception("Failed to fetch symbol info")
        except Exception as e:
            logger.error(f"❌ Error fetching symbol info: {e}")
            raise

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Round quantity per Bybit rules"""
        try:
            symbol_info = self._get_symbol_info(symbol)
            min_quantity = symbol_info['min_quantity']
            step = symbol_info['quantity_step']
            rounded = math.floor(quantity / step) * step
            if rounded < min_quantity:
                logger.warning(f"⚠️ Quantity {rounded} below minimum {min_quantity} for {symbol}")
                rounded = min_quantity
            logger.info(f"📏 Rounded quantity: {rounded} (min: {min_quantity}, step: {step})")
            return rounded
        except Exception as e:
            logger.warning(f"⚠️ Error rounding quantity: {e}")
            return round(quantity, 3)

    def _round_price(self, symbol: str, price: float) -> float:
        """Round price per Bybit rules"""
        try:
            symbol_info = self._get_symbol_info(symbol)
            tick_size = symbol_info['price_precision']
            return round(price / tick_size) * tick_size
        except Exception as e:
            logger.warning(f"⚠️ Error rounding price: {e}")
            return round(price, 8)

    def _validate_sl_tp(self, symbol: str, side: str, entry_price: float, stop_loss: float, take_profit: float) -> tuple:
        """Validate SL/TP prices to prevent immediate execution"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_sl = self._round_price(formatted_symbol, stop_loss) if stop_loss else None
            rounded_tp = self._round_price(formatted_symbol, take_profit) if take_profit else None
            
            # Fetch current market price
            ticker = self.exchange.fetch_ticker(formatted_symbol)
            current_price = ticker['last']
            
            # Minimum distance (e.g., 0.5% of entry price)
            min_distance = entry_price * 0.005
            
            if side == "buy":  # LONG
                if rounded_sl and rounded_sl >= entry_price:
                    logger.warning(f"⚠️ SL {rounded_sl} too close to entry {entry_price} for LONG, adjusting...")
                    rounded_sl = entry_price - min_distance
                    rounded_sl = self._round_price(formatted_symbol, rounded_sl)
                if rounded_tp and rounded_tp <= entry_price:
                    logger.warning(f"⚠️ TP {rounded_tp} too close to entry {entry_price} for LONG, adjusting...")
                    rounded_tp = entry_price + min_distance
                    rounded_tp = self._round_price(formatted_symbol, rounded_tp)
            elif side == "sell":  # SHORT
                if rounded_sl and rounded_sl <= entry_price:
                    logger.warning(f"⚠️ SL {rounded_sl} too close to entry {entry_price} for SHORT, adjusting...")
                    rounded_sl = entry_price + min_distance
                    rounded_sl = self._round_price(formatted_symbol, rounded_sl)
                if rounded_tp and rounded_tp >= entry_price:
                    logger.warning(f"⚠️ TP {rounded_tp} too close to entry {entry_price} for SHORT, adjusting...")
                    rounded_tp = entry_price - min_distance
                    rounded_tp = self._round_price(formatted_symbol, rounded_tp)
            
            # Check against current price
            if rounded_sl and abs(rounded_sl - current_price) < min_distance:
                logger.error(f"❌ SL {rounded_sl} too close to current price {current_price}")
                raise ValueError("SL too close to current price")
            if rounded_tp and abs(rounded_tp - current_price) < min_distance:
                logger.error(f"❌ TP {rounded_tp} too close to current price {current_price}")
                raise ValueError("TP too close to current price")
            
            return rounded_sl, rounded_tp
        except Exception as e:
            logger.error(f"❌ Error validating SL/TP: {e}")
            raise

    def get_balance(self) -> float:
        """Get USDT balance from futures wallet"""
        try:
            balance = self.exchange.fetch_balance(params={'type': 'future', 'category': 'linear'})
            usdt_balance = balance['USDT']['free']
            logger.info(f"💰 Futures wallet USDT balance: {usdt_balance}")
            return usdt_balance
        except Exception as e:
            logger.error(f"❌ Error fetching balance: {e}")
            return 0

    def calculate_position_size(self, symbol: str, entry_price: float) -> float:
        """Calculate position size based on capital percentage"""
        try:
            balance = self.get_balance()
            if balance <= 0:
                raise RuntimeError("Insufficient balance")
            position_value = balance * (self.capital_percentage / 100)
            quantity = position_value / entry_price
            formatted_symbol = self._format_symbol(symbol)
            rounded_qty = self._round_quantity(formatted_symbol, quantity)
            required_value = rounded_qty * entry_price
            if required_value > balance:
                logger.warning(f"⚠️ Required value {required_value} USDT exceeds balance {balance} USDT")
                max_qty = math.floor((balance / entry_price) / self._get_symbol_info(symbol)['quantity_step']) * self._get_symbol_info(symbol)['quantity_step']
                if max_qty >= self._get_symbol_info(symbol)['min_quantity']:
                    rounded_qty = max_qty
                    logger.info(f"📏 Reduced quantity to {rounded_qty} to fit balance {balance} USDT")
                else:
                    logger.error(f"❌ Cannot open position for {symbol}: Required value {required_value} USDT exceeds balance")
                    raise RuntimeError("Cannot open position: Required value exceeds balance")
            logger.info(f"💰 Position value: {position_value} USDT")
            logger.info(f"📊 Quantity: {rounded_qty}")
            return rounded_qty
        except Exception as e:
            logger.error(f"❌ Error calculating position size: {e}")
            raise

    def get_max_leverage(self, symbol: str) -> float:
        """Fetch maximum leverage for a symbol"""
        try:
            symbol_info = self._get_symbol_info(symbol)
            max_leverage = symbol_info['max_leverage']
            logger.info(f"⚡ Max leverage for {symbol}: {max_leverage}x")
            return max_leverage
        except Exception as e:
            logger.error(f"❌ Error fetching max leverage: {e}")
            logger.warning("⚠️ Using default leverage 20x")
            return 20.0

    def set_leverage(self, symbol: str) -> bool:
        """Set maximum leverage for the symbol"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            leverage = min(self.get_max_leverage(formatted_symbol), 50.0)  # Cap leverage at 50x
            logger.info(f"⚡ Setting leverage {leverage}x for {formatted_symbol}")
            try:
                result = self.exchange.set_leverage(leverage, formatted_symbol, params={'category': 'linear'})
                logger.info(f"✅ Leverage set successfully: {result}")
                return True
            except Exception as ccxt_error:
                logger.warning(f"⚠️ Failed to set leverage via ccxt: {ccxt_error}")
                if "leverage not modified" in str(ccxt_error).lower():
                    logger.info(f"⚠️ Leverage {leverage}x is current, proceeding...")
                    return True
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
                if data['retCode'] == 0 or data['retCode'] == 110043:  # Success or leverage not modified
                    logger.info(f"✅ Leverage set via Bybit API or already set: {data}")
                    return True
                else:
                    logger.error(f"❌ Failed to set leverage via Bybit API: {data}")
                    return False
        except Exception as e:
            logger.error(f"❌ Error setting leverage: {str(e)}")
            logger.warning("⚠️ Proceeding with current leverage")
            return True

    def set_margin_mode(self, symbol: str, mode: str = "cross") -> bool:
        """Set margin mode to 'cross' or 'isolated'"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            self.exchange.set_margin_mode(mode, formatted_symbol, params={'category': 'linear'})
            logger.info(f"✅ Set margin mode for {formatted_symbol} to {mode}")
            return True
        except Exception as e:
            logger.error(f"❌ Error setting margin mode: {e}")
            return False

    def _check_position_exists(self, symbol: str, side: str) -> bool:
        """Check if an open position exists for the symbol"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            positions = self.exchange.fetch_positions([formatted_symbol], params={'category': 'linear'})
            expected_side = 'long' if side == "buy" else 'short'
            for pos in positions:
                if pos['contracts'] > 0 and pos['side'] == expected_side:
                    logger.info(f"✅ Position open for {formatted_symbol} with side {expected_side}")
                    return True
            logger.warning(f"⚠️ No open position for {formatted_symbol} with side {expected_side}")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking position: {e}")
            return False

    def create_market_order(self, symbol: str, side: str, amount: float, 
                            stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """Create a market order with SL/TP"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_amount = self._round_quantity(formatted_symbol, amount)
            logger.info(f"📝 Creating {side} order for {formatted_symbol}")
            logger.info(f"📊 Quantity: {rounded_amount}")
            
            # Validate SL/TP
            entry_price = self.exchange.fetch_ticker(formatted_symbol)['last']
            rounded_sl, rounded_tp = self._validate_sl_tp(formatted_symbol, side, entry_price, stop_loss, take_profit)
            
            # Create market order
            order = self.exchange.create_market_order(
                formatted_symbol, 
                side, 
                rounded_amount,
                params={'reduceOnly': False, 'category': 'linear'}
            )
            logger.info(f"✅ Created market order: {order['id']}")
            
            # Wait for position confirmation
            max_attempts = 10
            attempt = 0
            while attempt < max_attempts:
                if self._check_position_exists(formatted_symbol, side):
                    break
                logger.info(f"⏳ Waiting for position confirmation (attempt {attempt + 1}/{max_attempts})...")
                time.sleep(1)
                attempt += 1
            if attempt == max_attempts:
                logger.warning(f"⚠️ Failed to confirm position for {formatted_symbol}, proceeding with SL/TP")
            
            # Set SL via Bybit API
            if rounded_sl:
                sl_side = "Sell" if side == "buy" else "Buy"
                logger.info(f"📋 Creating SL order: price={rounded_sl}, side={sl_side}")
                url = "https://api.bybit.com/v5/order/create"
                timestamp = str(int(time.time() * 1000))
                payload = {
                    "category": "linear",
                    "symbol": formatted_symbol,
                    "side": sl_side,
                    "orderType": "Market",
                    "qty": str(rounded_amount),
                    "triggerPrice": str(rounded_sl),
                    "triggerBy": "LastPrice",
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
                    logger.info(f"✅ Set SL: {rounded_sl} (Order ID: {data['result']['orderId']})")
                else:
                    logger.error(f"❌ Failed to set SL: {data}")
                    raise Exception(f"Failed to set SL: {data}")

            # Set TP via Bybit API
            if rounded_tp:
                tp_side = "Sell" if side == "buy" else "Buy"
                logger.info(f"📋 Creating TP order: price={rounded_tp}, side={tp_side}")
                url = "https://api.bybit.com/v5/order/create"
                timestamp = str(int(time.time() * 1000))
                payload = {
                    "category": "linear",
                    "symbol": formatted_symbol,
                    "side": tp_side,
                    "orderType": "Market",
                    "qty": str(rounded_amount),
                    "triggerPrice": str(rounded_tp),
                    "triggerBy": "LastPrice",
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
                    logger.info(f"✅ Set TP: {rounded_tp} (Order ID: {data['result']['orderId']})")
                else:
                    logger.error(f"❌ Failed to set TP: {data}")
                    raise Exception(f"Failed to set TP: {data}")

            return order
        except Exception as e:
            logger.error(f"❌ Error creating order: {e}")
            raise

    def open_position(self, symbol: str, direction: str, entry_price: float,
                     stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """Open a new position"""
        try:
            logger.info(f"🚀 Opening {direction} position for {symbol}")
            if not self.set_margin_mode(symbol, "cross"):
                raise RuntimeError("Failed to set margin mode to 'cross'")
            self.set_leverage(symbol)
            position_size = self.calculate_position_size(symbol, entry_price)
            side = 'buy' if direction.upper() == 'LONG' else 'sell'
            order = self.create_market_order(
                symbol, 
                side, 
                position_size,
                stop_loss,
                take_profit
            )
            logger.info(f"✅ Position opened successfully")
            return {
                'status': 'success',
                'order': order,
                'symbol': symbol,
                'direction': direction,
                'size': position_size,
                'entry_price': entry_price
            }
        except Exception as e:
            logger.error(f"❌ Error opening position: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def get_positions(self) -> list:
        """Fetch open positions"""
        try:
            positions = self.exchange.fetch_positions(params={'category': 'linear'})
            open_positions = [pos for pos in positions if pos['contracts'] > 0]
            logger.info(f"📊 Open positions: {len(open_positions)}")
            return open_positions
        except Exception as e:
            logger.error(f"❌ Error fetching positions: {e}")
            return []

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close a position"""
        try:
            formatted_symbol = self._format_symbol(symbol)
            positions = self.get_positions()
            position = next((pos for pos in positions if pos['symbol'] == formatted_symbol), None)
            if not position:
                logger.info(f"ℹ️ No open position for {formatted_symbol}")
                return {'status': 'error', 'message': 'No open position'}
            side = 'sell' if position['side'] == 'long' else 'buy'
            amount = abs(position['contracts'])
            order = self.exchange.create_market_order(
                formatted_symbol,
                side,
                amount,
                params={'reduceOnly': True, 'category': 'linear'}
            )
            logger.info(f"✅ Closed position: {formatted_symbol}")
            return {
                'status': 'success',
                'order': order
            }
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _sign_request(self, method: str, url: str, payload: Dict) -> str:
        """Sign Bybit API requests"""
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
            logger.error(f"❌ Error signing request: {e}")
            raise
