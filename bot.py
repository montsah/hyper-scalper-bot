import ccxt
import pandas as pd
import pytz
import time
import os
from datetime import datetime, timedelta

# ================== CONFIG ==================
COINS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'XRP/USDT:USDT', 'DOGE/USDT:USDT']
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'
RISK_PERCENT = 3.0
ATR_MULTIPLIER_SL = 1.0
RR = 2.0
TRAIL_AFTER = 1.0
TRAIL_ATR = 0.6
MAX_CONCURRENT = 3
MAX_HOLD_MINUTES = 45
# ===========================================
def get_usdt_balance():
    try:
        balance = exchange.fetch_balance()
        usdt = balance['total'].get('USDT', 0)
        print(f"💰 Current USDT balance: ${usdt:.2f}")
        return float(usdt)
    except Exception as e:
        print(f"Could not fetch balance: {e}")
        return 10000.0  # fallback to 10k if error
exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_API_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})
exchange.set_sandbox_mode(True)   # This switches to paper trading
print("🧪 RUNNING IN PAPER TRADING MODE (Testnet)")
ny_tz = pytz.timezone('America/New_York')
print("✅ HyperScalper v1 started - DRY_RUN =", DRY_RUN)

active_trades = {}  # track open positions

while True:
    now = datetime.now(ny_tz)
        # === Print balance every loop so we can see it ===
    if now.minute % 2 == 0:        # prints every 2 minutes
        get_usdt_balance()
    # Clean expired trades
    for symbol in list(active_trades.keys()):
        if (now - active_trades[symbol]['entry_time']).total_seconds() / 60 > MAX_HOLD_MINUTES:
            print(f"Force close {symbol} - max hold reached")
            del active_trades[symbol]
    
    if len(active_trades) >= MAX_CONCURRENT:
        time.sleep(30)
        continue
    
    for symbol in COINS:
        if symbol in active_trades:
            continue
            
        try:
            # 15m bias
            df15 = pd.DataFrame(exchange.fetch_ohlcv(symbol, '15m', limit=100), columns=['ts','o','h','l','c','v'])
            ema8_15 = df15['c'].ewm(span=8, adjust=False).mean().iloc[-1]
            ema21_15 = df15['c'].ewm(span=21, adjust=False).mean().iloc[-1]
            
            long_bias = ema8_15 > ema21_15
            
            # 5m data
            df5 = pd.DataFrame(exchange.fetch_ohlcv(symbol, '5m', limit=150), columns=['ts','o','h','l','c','v'])
            current_price = df5['c'].iloc[-1]
            
            ema8 = df5['c'].ewm(span=8, adjust=False).mean().iloc[-1]
            rsi = pd.Series(df5['c']).rolling(14).apply(lambda x: 100 - 100/(1 + (x.diff().clip(lower=0).mean() / abs(x.diff().clip(upper=0).mean()))), raw=False).iloc[-1]
            adx = 25  # simplified - in full version we calculate properly
            vol_avg = df5['v'].rolling(20).mean().iloc[-1]
            
            atr = (df5['h'] - df5['l']).rolling(14).mean().iloc[-1]
            
                                       # === LONG ENTRY ===
            if long_bias and current_price > ema8 and rsi > 48 and df5['v'].iloc[-1] > vol_avg * 1.25 and adx > 18:
                balance = get_usdt_balance()
                risk_amount = balance * (RISK_PERCENT / 100)          # 3% of current balance
                
                sl_distance = ATR_MULTIPLIER_SL * atr
                position_size = risk_amount / sl_distance             # in coin quantity
                
                sl = current_price - sl_distance
                tp = current_price + (sl_distance * RR)
                
                print(f"🚀 HYPER LONG {symbol} @ {current_price:.4f} | Risk ${risk_amount:.2f} (3%) | Size {position_size:.6f} coins")
                
                if not DRY_RUN:
                    # Real order code goes here later
                    pass
                                    # === SHORT ENTRY ===
            elif not long_bias and current_price < ema8 and rsi < 52 and df5['v'].iloc[-1] > vol_avg * 1.25 and adx > 18:
                balance = get_usdt_balance()
                risk_amount = balance * (RISK_PERCENT / 100)          # 3% of current balance
                
                sl_distance = ATR_MULTIPLIER_SL * atr
                position_size = risk_amount / sl_distance             # in coin quantity
                
                sl = current_price + sl_distance
                tp = current_price - (sl_distance * RR)
                
                print(f"🔻 HYPER SHORT {symbol} @ {current_price:.4f} | Risk ${risk_amount:.2f} (3%) | Size {position_size:.6f} coins")
                
                if not DRY_RUN:
                    # Real order code goes here later
                    pass
                   
        except:
            continue
            
    time.sleep(30)  # check every 30 seconds on 5m
