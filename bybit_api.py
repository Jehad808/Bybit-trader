import os
import ccxt
import math
import logging
import time
from typing import Dict, Any, Optional
import configparser

logger = logging.getLogger(__name__)

class BybitAPI:
    def __init__(self, config_file: str = "config.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.api_key = os.getenv("BYBIT_API_KEY")
        self.api_secret = os.getenv("BYBIT_API_SECRET")
        if not (self.api_key and self.api_secret):
            raise RuntimeError("❌ Bybit API keys missing!")
        self.exchange = ccxt.bybit({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "test": True,
            "options": {"defaultType": "future", "defaultSubType": "linear"},
        })
        try:
            self.exchange.load_markets()
            logger.info("✅ Loaded Bybit market data.")
        except Exception as e:
            logger.error(f"❌ Failed to load Bybit markets: {e}")
            raise
        self.capital_percentage = float(self.config.get("BYBIT", "CAPITAL_PERCENTAGE", fallback=5.0))
        self.balance = self.get_balance()
        logger.info(f"✅ Initialized Bybit API - Balance: {self.balance} USDT")

    def _format_symbol(self, symbol: str) -> str:
        symbol = symbol.replace('.P', '')
        if not symbol.endswith('USDT'):
            symbol += 'USDT'
        return symbol

    def _get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        try:
            formatted_symbol = self._format_symbol(symbol)
            market = self.exchange.market(formatted_symbol)
            return {
                'min_quantity': float(market['limits']['amount']['min']),
                'quantity_step': float(market['precision']['amount']),
                'price_precision': float(market['precision']['price']),
                'max_leverage': float(market['info']['leverageFilter']['maxLeverage'])
            }
        except Exception as e:
            logger.error(f"❌ Error fetching symbol info: {e}")
            raise

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        try:
            symbol_info = self._get_symbol_info(symbol)
            min_quantity = symbol_info['min_quantity']
            step = symbol_info['quantity_step']
            rounded = math.floor(quantity / step) * step
            if rounded < min_quantity:
                rounded = min_quantity
            return rounded
        except Exception as e:
            logger.error(f"❌ Error rounding quantity: {e}")
            return round(quantity, 3)

    def _round_price(self, symbol: str, price: float) -> float:
        try:
            symbol_info = self._get_symbol_info(symbol)
            tick_size = symbol_info['price_precision']
            return round(price / tick_size) * tick_size
        except Exception as e:
            logger.error(f"❌ Error rounding price: {e}")
            return round(price, 8)

    def _validate_sl_tp(self, symbol: str, side: str, entry_price: float, stop_loss: float, take_profit: float) -> tuple:
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_sl = self._round_price(formatted_symbol, stop_loss) if stop_loss else None
            rounded_tp = self._round_price(formatted_symbol, take_profit) if take_profit else None
            ticker = self.exchange.fetch_ticker(formatted_symbol)
            current_price = ticker['last']
            min_distance = entry_price * 0.02
            if side == "buy":
                if rounded_sl and rounded_sl >= entry_price - min_distance:
                    rounded_sl = entry_price - min_distance
                    rounded_sl = self._round_price(formatted_symbol, rounded_sl)
                if rounded_tp and rounded_tp <= entry_price + min_distance:
                    rounded_tp = entry_price + min_distance
                    rounded_tp = self._round_price(formatted_symbol, rounded_tp)
            elif side == "sell":
                if rounded_sl and rounded_sl <= entry_price + min_distance:
                    rounded_sl = entry_price + min_distance
                    rounded_sl = self._round_price(formatted_symbol, rounded_sl)
                if rounded_tp and rounded_tp >= entry_price - min_distance:
                    rounded_tp = entry_price - min_distance
                    rounded_tp = self._round_price(formatted_symbol, rounded_tp)
            if rounded_sl and abs(rounded_sl - current_price) < min_distance:
                logger.warning(f"⚠️ SL too close to current price: {rounded_sl}")
                rounded_sl = None
            if rounded_tp and abs(rounded_tp - current_price) < min_distance:
                logger.warning(f"⚠️ TP too close to current price: {rounded_tp}")
                rounded_tp = None
            return rounded_sl, rounded_tp
        except Exception as e:
            logger.error(f"❌ Error validating SL/TP: {e}")
            return None, None

    def get_balance(self) -> float:
        try:
            balance = self.exchange.fetch_balance(params={'type': 'future', 'category': 'linear'})
            usdt_balance = balance.get('USDT', {}).get('free', 0.0)
            if usdt_balance == 0.0:
                logger.warning("⚠️ No USDT balance found. Fund Futures wallet.")
            logger.info(f"💰 Balance: {usdt_balance} USDT")
            return usdt_balance
        except Exception as e:
            logger.error(f"❌ Error fetching balance: {e}")
            return 0.0

    def calculate_position_size(self, symbol: str, entry_price: float) -> float:
        try:
            balance = self.get_balance()
            if balance <= 0:
                raise RuntimeError("Insufficient balance.")
            position_value = balance * (self.capital_percentage / 100)
            quantity = position_value / entry_price
            formatted_symbol = self._format_symbol(symbol)
            rounded_qty = self._round_quantity(formatted_symbol, quantity)
            required_value = rounded_qty * entry_price
            if required_value > balance:
                max_qty = math.floor((balance / entry_price) / self._get_symbol_info(symbol)['quantity_step']) * self._get_symbol_info(symbol)['quantity_step']
                if max_qty >= self._get_symbol_info(symbol)['min_quantity']:
                    rounded_qty = max_qty
                else:
                    raise RuntimeError("Cannot open position: Insufficient balance.")
            return rounded_qty
        except Exception as e:
            logger.error(f"❌ Error calculating position size: {e}")
            raise

    def get_max_leverage(self, symbol: str) -> float:
        try:
            symbol_info = self._get_symbol_info(symbol)
            return symbol_info['max_leverage']
        except Exception as e:
            logger.error(f"❌ Error fetching max leverage: {e}")
            return 5.0

    def set_leverage(self, symbol: str) -> bool:
        try:
            formatted_symbol = self._format_symbol(symbol)
            leverage = min(self.get_max_leverage(formatted_symbol), 5.0)
            self.exchange.set_leverage(leverage, formatted_symbol, params={'category': 'linear'})
            logger.info(f"✅ Set leverage to {leverage}x for {formatted_symbol}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to set leverage: {e}")
            return True

    def set_margin_mode(self, symbol: str, mode: str = "cross") -> bool:
        try:
            formatted_symbol = self._format_symbol(symbol)
            self.exchange.set_margin_mode(mode, formatted_symbol, params={'category': 'linear'})
            logger.info(f"✅ Set margin mode to {mode} for {formatted_symbol}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to set margin mode: {e}")
            return True

    def _check_position_exists(self, symbol: str, side: str) -> bool:
        try:
            formatted_symbol = self._format_symbol(symbol)
            positions = self.exchange.fetch_positions([formatted_symbol], params={'category': 'linear'})
            expected_side = 'long' if side == "buy" else 'short'
            for pos in positions:
                if pos['contracts'] > 0 and pos['side'] == expected_side:
                    return True
            return False
        except Exception as e:
            logger.error(f"❌ Error checking position: {e}")
            return False

    def create_market_order(self, symbol: str, side: str, amount: float, stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_amount = self._round_quantity(formatted_symbol, amount)
            entry_price = self.exchange.fetch_ticker(formatted_symbol)['last']
            rounded_sl, rounded_tp = self._validate_sl_tp(formatted_symbol, side, entry_price, stop_loss, take_profit)
            order = self.exchange.create_market_order(formatted_symbol, side, rounded_amount, params={'reduceOnly': False, 'category': 'linear'})
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                if self._check_position_exists(formatted_symbol, side):
                    break
                time.sleep(0.5)
                attempt += 1
            if rounded_sl:
                sl_side = "sell" if side == "buy" else "buy"
                self.exchange.create_order(formatted_symbol, 'market', sl_side, rounded_amount, None, params={'category': 'linear', 'triggerPrice': rounded_sl, 'triggerBy': 'LastPrice', 'reduceOnly': True})
                logger.info(f"✅ Set SL: {rounded_sl}")
            if rounded_tp:
                tp_side = "sell" if side == "buy" else "buy"
                self.exchange.create_order(formatted_symbol, 'market', tp_side, rounded_amount, None, params={'category': 'linear', 'triggerPrice': rounded_tp, 'triggerBy': 'LastPrice', 'reduceOnly': True})
                logger.info(f"✅ Set TP: {rounded_tp}")
            logger.info(f"✅ Created market order: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"❌ Error creating order: {e}")
            raise

    def open_position(self, symbol: str, direction: str, entry_price: float, stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        try:
            self.set_margin_mode(symbol, "cross")
            self.set_leverage(symbol)
            position_size = self.calculate_position_size(symbol, entry_price)
            side = 'buy' if direction.upper() == 'LONG' else 'sell'
            order = self.create_market_order(symbol, side, position_size, stop_loss, take_profit)
            logger.info(f"✅ Position opened: {symbol} {direction} @ {entry_price}")
            return {'status': 'success', 'order': order, 'symbol': symbol, 'direction': direction, 'size': position_size, 'entry_price': entry_price}
        except Exception as e:
            logger.error(f"❌ Error opening position: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_positions(self) -> list:
        try:
            positions = self.exchange.fetch_positions(params={'category': 'linear'})
            open_positions = [pos for pos in positions if pos['contracts'] > 0]
            return open_positions
        except Exception as e:
            logger.error(f"❌ Error fetching positions: {e}")
            return []

    def close_position(self, symbol: str) -> Dict[str, Any]:
        try:
            formatted_symbol = self._format_symbol(symbol)
            positions = self.get_positions()
            position = next((pos for pos in positions if pos['symbol'] == formatted_symbol), None)
            if not position:
                return {'status': 'error', 'message': 'No open position'}
            side = 'sell' if position['side'] == 'long' else 'buy'
            amount = abs(position['contracts'])
            order = self.exchange.create_market_order(formatted_symbol, side, amount, params={'reduceOnly': True, 'category': 'linear'})
            logger.info(f"✅ Closed position: {symbol}")
            return {'status': 'success', 'order': order}
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
            return {'status': 'error', 'message': str(e)}
