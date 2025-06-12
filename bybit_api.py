import os
import ccxt
import math
import logging
import time
from typing import Dict, Any, Optional
import configparser
import pandas as pd
import numpy as np
from pybit.unified_trading import HTTP

logger = logging.getLogger(__name__)

class BybitAPI:
    def __init__(self, config_file: str = "config.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.api_key = os.getenv("BYBIT_API_KEY", self.config.get("BYBIT", "API_KEY"))
        self.api_secret = os.getenv("BYBIT_API_SECRET", self.config.get("BYBIT", "API_SECRET"))
        self.testnet = self.config.getboolean("BYBIT", "TESTNET", fallback=True)
        if not (self.api_key and self.api_secret):
            raise RuntimeError("❌ Bybit API keys missing!")
        self.exchange = ccxt.bybit({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "test": self.testnet,
            "options": {"defaultType": "future", "defaultSubType": "linear"},
        })
        self.pybit_client = HTTP(
            testnet=self.testnet,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
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
        symbol = symbol.replace('.P', '').strip()
        if not symbol.endswith('USDT'):
            symbol += 'USDT'
        return symbol

    def _get_symbol_info(self, symbol: str) -> Dict[str, float]:
        try:
            formatted_symbol = self._format_symbol(symbol)
            market = self.exchange.market(formatted_symbol)
            leverage = float(market['info'].get('leverageFilter', {}).get('maxLeverage', 25.0))
            min_qty = float(market['limits']['amount'].get('min', 0.001))
            qty_step = float(market['precision']['amount'] or 0.001)
            price_step = float(market['precision']['price'] or 0.0001)
            logger.debug(f"Symbol info for {formatted_symbol}: min_qty={min_qty}, qty_step={qty_step}, price_step={price_step}, max_leverage={leverage}")
            return {
                'min_quantity': min_qty if min_qty > 0 else 0.001,
                'quantity_precision': qty_step if qty_step > 0 else 0.001,
                'price_precision': price_step if price_step > 0 else 0.0001,
                'max_leverage': leverage if leverage > 0 else 25.0
            }
        except Exception as e:
            logger.error(f"❌ Error fetching symbol info for {symbol}: {e}")
            return {
                'min_quantity': 0.001,
                'quantity_precision': 0.001,
                'price_precision': 0.0001,
                'max_leverage': 25.0
            }

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        try:
            symbol_info = self._get_symbol_info(symbol)
            min_qty = symbol_info['min_quantity']
            step = symbol_info['quantity_precision']
            if quantity < min_qty:
                logger.warning(f"⚠️ Quantity {quantity} below min_qty {min_qty} for {symbol}, adjusting to min_qty")
                quantity = min_qty
            precision = max(0, -int(math.log10(step)))
            rounded = round(max(quantity, min_qty) / step) * step
            rounded = round(rounded, precision)
            logger.debug(f"Rounding quantity for {symbol}: input={quantity}, min_qty={min_qty}, step={step}, precision={precision}, rounded={rounded}")
            return rounded
        except Exception as e:
            logger.error(f"❌ Error rounding quantity for {symbol}: {e}")
            return round(quantity, 3)

    def _round_price(self, symbol: str, price: float) -> float:
        try:
            symbol_info = self._get_symbol_info(symbol)
            tick_size = symbol_info['price_precision']
            rounded = round(price / tick_size) * tick_size
            logger.debug(f"Rounding price for {symbol}: input={price}, tick_size={tick_size}, rounded={rounded}")
            return rounded
        except Exception as e:
            logger.error(f"❌ Error rounding price for {symbol}: {e}")
            return round(price, 8)

    def _calculate_atr(self, symbol: str, period: int = 14) -> float:
        try:
            formatted_symbol = self._format_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(formatted_symbol, timeframe='1h', limit=period + 1)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            return atr if not np.isnan(atr) else 0.01
        except Exception as e:
            logger.warning(f"⚠️ Error calculating ATR for {symbol}: {e}")
            return 0.01

    def _validate_sl_tp Mediavalidate(self, symbol: str, side: str, entry_price: float, stop_loss: float, take_profit: float, take_profit_2: float = None) -> tuple:
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_sl = self._round_price(formatted_symbol, stop_loss) if stop_loss else None
            rounded_tp = self._round_price(formatted_symbol, take_profit) if take_profit else None
            rounded_tp2 = self._round_price(formatted_symbol, take_profit_2) if take_profit_2 else None
            ticker = self.exchange.fetch_ticker(formatted_symbol)
            current_price = ticker['last']
            atr = self._calculate_atr(formatted_symbol)
            min_distance = atr * 0.5
            if side == "buy":
                if rounded_sl is not None and rounded_sl >= entry_price - min_distance:
                    rounded_sl = entry_price - min_distance
                    rounded_sl = self._round_price(formatted_symbol, rounded_sl)
                if rounded_tp is not None and rounded_tp <= entry_price + min_distance:
                    rounded_tp = entry_price + min_distance
                    rounded_tp = self._round_price(formatted_symbol, rounded_tp)
                if rounded_tp2 is not None and rounded_tp2 <= entry_price + min_distance:
                    rounded_tp2 = entry_price + min_distance
                    rounded_tp2 = self._round_price(formatted_symbol, rounded_tp2)
            else:  # side == "sell"
                if rounded_sl is not None and rounded_sl <= entry_price + min_distance:
                    rounded_sl = entry_price + min_distance
                    rounded_sl = self._round_price(formatted_symbol, rounded_sl)
                if rounded_tp is not None and rounded_tp >= entry_price - min_distance:
                    rounded_tp = entry_price - min_distance
                    rounded_tp = self._round_price(formatted_symbol, rounded_tp)
                if rounded_tp2 is not None and rounded_tp2 >= entry_price - min_distance:
                    rounded_tp2 = entry_price - min_distance
                    rounded_tp2 = self._round_price(formatted_symbol, rounded_tp2)
            logger.debug(f"Validated SL/TP for {symbol}: SL={rounded_sl}, TP1={rounded_tp}, TP2={rounded_tp2}")
            return rounded_sl, rounded_tp, rounded_tp2
        except Exception as e:
            logger.error(f"❌ Error validating SL/TP for {symbol}: {e}")
            return None, None, None

    def get_balance(self) -> float:
        try:
            balance = self.exchange.fetch_balance(params={'type': 'future', 'category': 'linear'})
            usdt_balance = float(balance.get('USDT', {}).get('free', 0.0))
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
            leverage = self.get_max_leverage(symbol)
            position_value = balance * (self.capital_percentage / 100)  # 5% من الرصيد الحقيقي
            quantity = position_value / entry_price  # الكمية بدون الرافعة
            formatted_symbol = self._format_symbol(symbol)
            rounded_qty = self._round_quantity(formatted_symbol, quantity)
            required_value = rounded_qty * entry_price
            if required_value > balance:
                max_qty = math.floor((balance / entry_price) / self._get_symbol_info(symbol)['quantity_precision']) * self._get_symbol_info(symbol)['quantity_precision']
                if max_qty >= self._get_symbol_info(symbol)['min_quantity']:
                    rounded_qty = max_qty
                else:
                    raise RuntimeError("Cannot open position: Insufficient balance.")
            logger.debug(f"Position size for {symbol}: balance={balance}, leverage={leverage}, position_value={position_value}, quantity={quantity}, rounded_qty={rounded_qty}")
            return rounded_qty
        except Exception as e:
            logger.error(f"❌ Error calculating position size for {symbol}: {e}")
            raise

    def get_max_leverage(self, symbol: str) -> float:
        try:
            symbol_info = self._get_symbol_info(symbol)
            return symbol_info['max_leverage']
        except Exception as e:
            logger.error(f"❌ Error fetching max leverage for {symbol}: {e}")
            return 25.0

    def set_leverage(self, symbol: str) -> bool:
        try:
            formatted_symbol = self._format_symbol(symbol)
            leverage = self.get_max_leverage(formatted_symbol)
            response = self.pybit_client.set_leverage(
                category='linear',
                symbol=formatted_symbol,
                buy_leverage=str(leverage),
                sell_leverage=str(leverage)
            )
            if response['retCode'] == 0:
                logger.info(f"✅ Set leverage to {leverage}x for {formatted_symbol}")
                return True
            else:
                logger.warning(f"⚠️ Failed to set leverage {leverage}x for {formatted_symbol}: {response['retMsg']}")
                return False
        except Exception as e:
            logger.error(f"❌ Error setting leverage for {formatted_symbol}: {e}")
            return False

    def set_margin_mode(self, symbol: str, mode: str = "cross") -> bool:
        try:
            formatted_symbol = self._format_symbol(symbol)
            response = self.pybit_client.set_margin_mode(
                setMarginMode=mode.upper(),
                category='linear'
            )
            if response['retCode'] == 0:
                logger.info(f"✅ Set margin mode to {mode} for {formatted_symbol}")
                return True
            else:
                logger.warning(f"⚠️ Failed to set margin mode for {formatted_symbol}: {response['retMsg']}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to set margin mode for {formatted_symbol}: {e}")
            return True

    def _check_position_exists(self, symbol: str, side: str) -> bool:
        try:
            formatted_symbol = self._format_symbol(symbol)
            positions = self.pybit_client.get_positions(
                category='linear',
                symbol=formatted_symbol
            )
            if positions['retCode'] == 0:
                for pos in positions['result']['list']:
                    if float(pos['size']) > 0:
                        expected_side = 'long' if side == "buy" else 'short'
                        if pos['side'].lower() == expected_side:
                            return True
            return False
        except Exception as e:
            logger.error(f"❌ Error checking position for {symbol}: {e}")
            return False

    def _cancel_open_orders(self, symbol: str) -> bool:
        try:
            formatted_symbol = self._format_symbol(symbol)
            response = self.pybit_client.cancel_all_orders(
                category='linear',
                symbol=formatted_symbol
            )
            if response['retCode'] == 0:
                logger.info(f"✅ Canceled all open orders for {formatted_symbol}")
                return True
            else:
                logger.warning(f"⚠️ Failed to cancel orders for {formatted_symbol}: {response['retMsg']}")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Failed to cancel orders for {formatted_symbol}: {e}")
            return False

    def create_market_order(self, symbol: str, side: str, amount: float, stop_loss: float = None, take_profit: float = None, take_profit_2: float = None) -> Dict[str, Any]:
        try:
            formatted_symbol = self._format_symbol(symbol)
            rounded_amount = self._round_quantity(formatted_symbol, amount)
            entry_price = self.exchange.fetch_ticker(formatted_symbol)['last']
            rounded_sl, rounded_tp, rounded_tp2 = self._validate_sl_tp(formatted_symbol, side, entry_price, stop_loss, take_profit, take_profit_2)
            order = self.pybit_client.place_order(
                category='linear',
                symbol=formatted_symbol,
                side=side.capitalize(),
                order_type='Market',
                qty=str(rounded_amount),
                time_in_force='GTC',
                reduce_only=False
            )
            if order['retCode'] != 0:
                raise Exception(f"Failed to place order: {order['retMsg']}")
            order_id = order['result']['orderId']
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                if self._check_position_exists(formatted_symbol, side):
                    break
                time.sleep(0.5)
                attempt += 1
            if rounded_sl:
                sl_side = "Sell" if side == "buy" else "Buy"
                sl_trigger = "below" if side == "buy" else "above"
                self.pybit_client.place_order(
                    category='linear',
                    symbol=formatted_symbol,
                    side=sl_side,
                    order_type='Market',
                    qty=str(rounded_amount),
                    trigger_price=str(rounded_sl),
                    trigger_by='LastPrice',
                    reduce_only=True,
                    time_in_force='GTC'
                )
                logger.info(f"✅ Set SL: {rounded_sl} (trigger: {sl_trigger})")
            if rounded_tp:
                tp_side = "Sell" if side == "buy" else "Buy"
                tp_trigger = "above" if side == "buy" else "below"
                self.pybit_client.place_order(
                    category='linear',
                    symbol=formatted_symbol,
                    side=tp_side,
                    order_type='Market',
                    qty=str(rounded_amount),
                    trigger_price=str(rounded_tp),
                    trigger_by='LastPrice',
                    reduce_only=True,
                    time_in_force='GTC'
                )
                logger.info(f"✅ Set TP1: {rounded_tp} (trigger: {tp_trigger})")
            if rounded_tp2:
                tp_side = "Sell" if side == "buy" else "Buy"
                tp_trigger = "above" if side == "buy" else "below"
                self.pybit_client.place_order(
                    category='linear',
                    symbol=formatted_symbol,
                    side=tp_side,
                    order_type='Market',
                    qty=str(rounded_amount / 2),
                    trigger_price=str(rounded_tp2),
                    trigger_by='LastPrice',
                    reduce_only=True,
                    time_in_force='GTC'
                )
                logger.info(f"✅ Set TP2: {rounded_tp2} (trigger: {tp_trigger})")
            logger.info(f"✅ Created market order: {order_id}")
            return {'id': order_id, 'symbol': formatted_symbol, 'side': side, 'amount': rounded_amount}
        except Exception as e:
            logger.error(f"❌ Error creating order for {symbol}: {e}")
            raise

    def open_position(self, symbol: str, direction: str, entry_price: float, stop_loss: float = None, take_profit: float = None, take_profit_2: float = None) -> Dict[str, Any]:
        try:
            self.set_margin_mode(symbol, "cross")
            if not self.set_leverage(symbol):
                logger.warning(f"⚠️ Using default leverage for {symbol}")
            position_size = self.calculate_position_size(symbol, entry_price)
            side = 'buy' if direction.upper() == 'LONG' else 'sell'
            order = self.create_market_order(symbol, side, position_size, stop_loss, take_profit, take_profit_2)
            logger.info(f"✅ Position opened: {symbol} {direction} @ {entry_price}")
            return {'status': 'success', 'order': order, 'symbol': symbol, 'direction': direction, 'size': position_size, 'entry_price': entry_price}
        except Exception as e:
            logger.error(f"❌ Error opening position for {symbol}: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_positions(self) -> list:
        try:
            positions = self.pybit_client.get_positions(category='linear')
            if positions['retCode'] == 0:
                open_positions = [pos for pos in positions['result']['list'] if float(pos['size']) > 0]
                return open_positions
            return []
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
            side = 'Sell' if position['side'].lower() == 'long' else 'Buy'
            amount = float(position['size'])
            order = self.pybit_client.place_order(
                category='linear',
                symbol=formatted_symbol,
                side=side,
                order_type='Market',
                qty=str(amount),
                reduce_only=True,
                time_in_force='GTC'
            )
            if order['retCode'] != 0:
                raise Exception(f"Failed to close position: {order['retMsg']}")
            self._cancel_open_orders(formatted_symbol)
            logger.info(f"✅ Closed position: {symbol}")
            return {'status': 'success', 'order': {'id': order['result']['orderId']}}
        except Exception as e:
            logger.error(f"❌ Error closing position for {symbol}: {e}")
            return {'status': 'error', 'message': str(e)}
