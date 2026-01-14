import streamlit as st
import yfinance as yf
import pandas as pd

# -------------------------------------------------
# Page setup
# -------------------------------------------------
st.set_page_config(page_title="SPY Spread System", layout="centered")
st.title("SPY Credit Spread System")
st.caption("Regime + Volatility + Range Location (Edge-Only Entries)")

# -------------------------------------------------
# Sidebar parameters
# -------------------------------------------------
DIST_BAND = st.sidebar.slider("Chop distance band (%)", 0.1, 2.0, 0.6, 0.1) / 100
CROSS_LOOKBACK = st.sidebar.slider("Crossover lookback (days)", 5, 30, 10, 1)
CROSS_THRESHOLD = st.sidebar.slider("Crossover threshold", 1, 10, 3, 1)
VIX_THRESHOLD = st.sidebar.slider("VIX threshold", 10, 40, 20, 1)

RANGE_LOOKBACK = st.sidebar.slider("Range lookback (days)", 10, 40, 20, 1)
ATR_LOOKBACK = st.sidebar.slider("ATR lookback", 7, 21, 14, 1)
ATR_BUFFER = st.sidebar.slider("ATR edge buffer (%)", 10, 50, 25, 5) / 100

# -------------------------------------------------
# Data loading
# -------------------------------------------------
@st.cache_data(ttl=900)
def load_data():
    spy = yf.download("SPY", period="1y", interval="1d", auto_adjust=True, progress=False)
    vix = yf.download("^VIX", period="10d", interval="1d", auto_adjust=True, progress=False)

    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)

    return spy.dropna(), vix.dropna()

spy_df, vix_df = load_data()

if spy_df.empty or vix_df.empty or len(spy_df) < 60:
    st.error("Insufficient data loaded.")
    st.stop()

# -------------------------------------------------
# Indicators
# -------------------------------------------------
spy_df["SMA20"] = spy_df["Close"].rolling(20).mean()
spy_df["SMA50"] = spy_df["Close"].rolling(50).mean()

close = float(spy_df["Close"].iloc[-1])
sma20 = float(spy_df["SMA20"].iloc[-1])
sma50 = float(spy_df["SMA50"].iloc[-1])

# -------------------------------------------------
# Chop detection
# -------------------------------------------------
distance_pct = abs(close - sma50) / sma50
chop_distance = distance_pct < DIST_BAND

recent = spy_df.tail(CROSS_LOOKBACK + 1).dropna(subset=["Close", "SMA50"])
above = recent["Close"] > recent["SMA50"]
crosses = int((above != above.shift()).sum() - 1)
chop_cross = crosses >= CROSS_THRESHOLD

chop = chop_distance or chop_cross

# -------------------------------------------------
# Volatility filter
# -------------------------------------------------
vix_value = float(vix_df["Close"].iloc[-1])
vol_ok = vix_value < VIX_THRESHOLD

# -------------------------------------------------
# ATR + Range Location
# -------------------------------------------------
high = spy_df["High"]
low = spy_df["Low"]
prev_close = spy_df["Close"].shift()

tr = pd.concat([
    high - low,
    (high - prev_close).abs(),
    (low - prev_close).abs()
], axis=1).max(axis=1)

spy_df["ATR"] = tr.rolling(ATR_LOOKBACK).mean()

support = low.rolling(RANGE_LOOKBACK).min().iloc[-1]
resistance = high.rolling(RANGE_LOOKBACK).max().iloc[-1]
atr = spy_df["ATR"].iloc[-1]

near_support = close <= support + ATR_BUFFER * atr
near_resistance = close >= resistance - ATR_BUFFER * atr
mid_range = not (near_support or near_resistance)

# -------------------------------------------------
# Market regime
# -------------------------------------------------
if sma20 > sma50:
    regime = "Bullish"
elif sma20 < sma50:
    regime = "Bearish"
else:
    regime = "Neutral"

# -------------------------------------------------
# Final decision logic
# -------------------------------------------------
system_on = vol_ok and not chop and not mid_range

direction = "NO TRADE"

if system_on:
    if regime == "Bullish" and near_support:
        direction = "PUT CREDIT SPREADS"
    elif regime == "Bearish" and near_resistance:
        direction = "CALL CREDIT SPREADS"
    else:
        system_on = False
        direction = "NO TRADE (Location/Regime mismatch)"

# -------------------------------------------------
# UI OUTPUT
# -------------------------------------------------
st.subheader("Market Snapshot")

c1, c2, c3 = st.columns(3)
c1.metric("SPY Close", f"{close:,.2f}")
c2.metric("SMA 20 / 50", f"{sma20:,.2f} / {sma50:,.2f}")
c3.metric("VIX", f"{vix_value:,.2f}")

st.write("### Filters")
st.write(f"- Regime: **{regime}**")
st.write(f"- Volatility OK: **{'YES' if vol_ok else 'NO'}**")
st.write(f"- Chop Detected: **{'YES' if chop else 'NO'}**")
st.write(f"- Distance from SMA50: **{distance_pct*100:.2f}%**")
st.write(f"- SMA50 Crosses ({CROSS_LOOKBACK}d): **{crosses}**")

st.write("### Range Location")
st.write(f"- Support ({RANGE_LOOKBACK}d): **{support:,.2f}**")
st.write(f"- Resistance ({RANGE_LOOKBACK}d): **{resistance:,.2f}**")
st.write(f"- ATR ({ATR_LOOKBACK}): **{atr:,.2f}**")

location = (
    "Near Support" if near_support else
    "Near Resistance" if near_resistance else
    "Mid-Range"
)
st.write(f"- Location: **{location}**")

st.write("---")

if system_on:
    st.success(f"SYSTEM ON → {direction}")
else:
    st.error(f"SYSTEM OFF → {direction}")

st.caption("Educational tool only. Not financial advice.")

