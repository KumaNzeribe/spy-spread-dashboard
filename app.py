import streamlit as st
import yfinance as yf
import pandas as pd

# =================================================
# Page Setup
# =================================================
st.set_page_config(page_title="Spread Permission System", layout="centered")
st.title("Credit Spread Permission System")
st.caption("SPY = Market Permission | Stock = Trade Location")

# =================================================
# Sidebar Inputs
# =================================================
ticker = st.sidebar.text_input("Enter Stock Ticker", "AAPL").upper()

VIX_THRESHOLD = st.sidebar.slider("VIX Threshold", 12, 35, 20, 1)

RANGE_LOOKBACK = st.sidebar.slider("Range Lookback (days)", 10, 40, 20, 1)
ATR_LOOKBACK = st.sidebar.slider("ATR Lookback", 7, 21, 14, 1)
ATR_BUFFER = st.sidebar.slider("ATR Edge Buffer (%)", 15, 50, 30, 5) / 100

CHOP_DIST = st.sidebar.slider("SPY Chop Distance (%)", 0.1, 2.0, 0.6, 0.1) / 100
CHOP_LOOKBACK = st.sidebar.slider("SPY Chop Lookback", 5, 30, 10, 1)
CHOP_CROSSES = st.sidebar.slider("SPY Chop Crosses", 1, 10, 3, 1)

# =================================================
# Data Loader
# =================================================
@st.cache_data(ttl=900)
def load_symbol(symbol, period="1y"):
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()

spy_df = load_symbol("SPY")
stock_df = load_symbol(ticker)
vix_df = load_symbol("^VIX", period="10d")

if spy_df.empty or stock_df.empty or vix_df.empty:
    st.error("Failed to load data.")
    st.stop()

# =================================================
# SPY MARKET PERMISSION
# =================================================
spy_df["SMA20"] = spy_df["Close"].rolling(20).mean()
spy_df["SMA50"] = spy_df["Close"].rolling(50).mean()

spy_close = spy_df["Close"].iloc[-1]
spy_sma20 = spy_df["SMA20"].iloc[-1]
spy_sma50 = spy_df["SMA50"].iloc[-1]

# Regime
if spy_sma20 > spy_sma50:
    market_regime = "Bullish"
elif spy_sma20 < spy_sma50:
    market_regime = "Bearish"
else:
    market_regime = "Neutral"

# Chop
dist_pct = abs(spy_close - spy_sma50) / spy_sma50
chop_dist = dist_pct < CHOP_DIST

recent = spy_df.tail(CHOP_LOOKBACK + 1).dropna(subset=["Close", "SMA50"])
above = recent["Close"] > recent["SMA50"]
crosses = int((above != above.shift()).sum() - 1)
chop_cross = crosses >= CHOP_CROSSES

spy_chop = chop_dist or chop_cross

# VIX
vix_value = vix_df["Close"].iloc[-1]
vol_ok = vix_value < VIX_THRESHOLD

market_permission = vol_ok and not spy_chop

# =================================================
# STOCK LOCATION LOGIC
# =================================================
stock_df["SMA20"] = stock_df["Close"].rolling(20).mean()
stock_df["SMA50"] = stock_df["Close"].rolling(50).mean()

high = stock_df["High"]
low = stock_df["Low"]
prev_close = stock_df["Close"].shift()

tr = pd.concat([
    high - low,
    (high - prev_close).abs(),
    (low - prev_close).abs()
], axis=1).max(axis=1)

stock_df["ATR"] = tr.rolling(ATR_LOOKBACK).mean()

support = low.rolling(RANGE_LOOKBACK).min().iloc[-1]
resistance = high.rolling(RANGE_LOOKBACK).max().iloc[-1]
atr = stock_df["ATR"].iloc[-1]
close = stock_df["Close"].iloc[-1]

near_support = close <= support + ATR_BUFFER * atr
near_resistance = close >= resistance - ATR_BUFFER * atr
mid_range = not (near_support or near_resistance)

# Stock bias
stock_sma20 = stock_df["SMA20"].iloc[-1]
stock_sma50 = stock_df["SMA50"].iloc[-1]

if stock_sma20 > stock_sma50:
    stock_bias = "Bullish"
elif stock_sma20 < stock_sma50:
    stock_bias = "Bearish"
else:
    stock_bias = "Neutral"

# =================================================
# FINAL DECISION
# =================================================
trade_action = "NO TRADE"

if not market_permission:
    trade_action = "NO TRADE (Market Risk OFF)"
elif near_support and stock_bias == "Bullish":
    trade_action = "PUT CREDIT SPREAD"
elif near_resistance and stock_bias == "Bearish":
    trade_action = "CALL CREDIT SPREAD"
else:
    trade_action = "SKIP THIS STOCK (Mid-range or bias mismatch)"


# =================================================
# UI OUTPUT
# =================================================
st.subheader("SPY Market Context")

c1, c2, c3 = st.columns(3)
c1.metric("SPY Close", f"{spy_close:,.2f}")
c2.metric("SPY SMA 20 / 50", f"{spy_sma20:,.2f} / {spy_sma50:,.2f}")
c3.metric("VIX", f"{vix_value:.2f}")

st.write(f"- Regime: **{market_regime}**")
st.write(f"- Chop Detected: **{'YES' if spy_chop else 'NO'}**")
st.write(f"- Market Permission: **{'ON' if market_permission else 'OFF'}**")

st.write("---")

st.subheader(f"{ticker} Trade Decision")

st.write(f"- Bias: **{stock_bias}**")
st.write(f"- Support ({RANGE_LOOKBACK}d): **{support:,.2f}**")
st.write(f"- Resistance ({RANGE_LOOKBACK}d): **{resistance:,.2f}**")
st.write(f"- ATR ({ATR_LOOKBACK}): **{atr:.2f}**")

location = (
    "Near Support" if near_support else
    "Near Resistance" if near_resistance else
    "Mid-Range"
)

st.write(f"- Location: **{location}**")

st.write("---")

if "SPREAD" in trade_action:
    st.success(f"ACTION → {trade_action}")
else:
    st.warning(trade_action)

st.caption("Educational tool only. Not financial advice.")

else:
    st.error(f"SYSTEM OFF → {direction}")

st.caption("Educational tool only. Not financial advice.")

