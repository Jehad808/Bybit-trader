async def process_signal(self, message):
    logger.info(f"📨 رسالة جديدة من: {message.sender.username}")
    try:
        # Parse signal (example)
        signal = self.parse_signal(message.text)
        if not signal:
            logger.warning("⚠️ لا توجد إشارة صالحة في الرسالة")
            return
        
        symbol = signal['symbol']
        direction = signal['direction']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']
        
        logger.info(f"✅ تم تحليل إشارة بنجاح: {symbol} {direction} @ {entry_price}")
        logger.info(f"📊 الرمز: {symbol}")
        logger.info(f"🔄 الاتجاه: {direction}")
        logger.info(f"💰 سعر الدخول: {entry_price}")
        logger.info(f"🎯 الهدف: {take_profit}")
        logger.info(f"⛔ وقف الخسارة: {stop_loss}")
        
        # Check for existing position
        positions = self.bybit_api.get_positions()
        for pos in positions:
            if pos['symbol'] == self.bybit_api._format_symbol(symbol):
                logger.warning(f"⚠️ مركز مفتوح بالفعل لـ {symbol}: {pos['side']}")
                return
        
        logger.info("🚀 بدء تنفيذ الصفقة...")
        result = self.bybit_api.open_position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        if result['status'] == 'success':
            logger.info("✅ تم تنفيذ الصفقة بنجاح")
            self.executed_trades += 1
        else:
            logger.error(f"❌ فشل في تنفيذ الصفقة: {result['message']}")
            self.failed_trades += 1
        
        logger.info(f"📈 إجمالي الصفقات المنفذة: {self.executed_trades}")
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الإشارة: {e}")
