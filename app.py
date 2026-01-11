import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="SPY Spread Regime", layout="centered")

st.title("SPY Spread Regime (Yahoo Finance)")
st.caption("Rule: SPY vs 50-DMA + VIX < 25 + Chop filter")

# -----------------------------
# Sidebar settings
# -----------------------------
DIST_BAND = st.sidebar.slider("Chop distance band (%)", 0.1, 2.0, 0.6, 0.1) / 100
CROSS_LOOKBACK = st.sidebar.slider("Crossover lookback (days)", 5, 30, 10, 1)
CROSS_THRESHOLD = st.sidebar.slider("Chop crossover threshold", 1, 10, 3, 1)
VIX_THRESHOLD = st.sidebar.slider("VIX threshold", 10, 40, 25, 1)

# -----------------------------
# Data loading
# -----------------------------
@st.cache_data(ttl=60 * 15)
def load_data():
    spy = yf.download(
        "SPY",
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",  # helps keep columns consistent
    )
    vix = yf.download(
        "^VIX",
        period="5d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
    )

    # Flatten MultiIndex columns if Yahoo returns them
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)

    return spy, vix


spy_df, vix_df = load_data()

if spy_df.empty or vix_df.empty:
    st.error("Failed to load data from Yahoo Finance. Try again later.")
    st.stop()

spy_df = spy_df.dropna()

# Need enough data to compute SMA50 reliably
if len(spy_df) < 60:
    st.error("Not enough SPY data returned to compute SMA50. Try again later.")
    st.stop()

# -----------------------------
# Indicator calculations
# -----------------------------
spy_df["SMA50"] = spy_df["Close"].rolling(50).mean()

close = float(spy_df["Close"].iloc[-1])
sma50 = float(spy_df["SMA50"].iloc[-1])

# Distance band chop filter
distance_pct = abs(close - sma50) / sma50
chop_distance = distance_pct < DIST_BAND

# VIX latest close
vix_df = vix_df.dropna()
vix_value = float(vix_df["Close"].iloc[-1])

# Crossover chop filter
last = spy_df.dropna().tail(CROSS_LOOKBACK + 1).copy()

# If SMA50 has NaNs near the start of the slice, trim again
last = last.dropna(subset=["SMA50", "Close"])
if len(last) < 2:
    st.error("Not enough recent data to evaluate crossovers. Try again later.")
    st.stop()

above = last["Close"] > last["SMA50"]
crosses = int((above != above.shift(1)).sum() - 1)
chop_cross = crosses >= CROSS_THRESHOLD

chop = bool(chop_distance or chop_cross)

# System ON/OFF
system_on = (vix_value < VIX_THRESHOLD) and (not chop)

# -----------------------------
# UI output
# -----------------------------
st.subheader("Current Read")

col1, col2, col3 = st.columns(3)
col1.metric("SPY Close", f"{close:,.2f}")
col2.metric("SPY 50-DMA", f"{sma50:,.2f}")
col3.metric("VIX", f"{vix_value:,.2f}")

st.write("### Filters")
st.write(
    f"- Distance from 50-DMA: **{distance_pct*100:.2f}%** "
    f"(chop if < **{DIST_BAND*100:.2f}%**)"
)
st.write(
    f"- Crossovers (last {CROSS_LOOKBACK} days): **{crosses}** "
    f"(chop if ≥ **{CROSS_THRESHOLD}**)"
)
st.write(f"- VIX gate: **{vix_value:.2f}** (must be < **{VIX_THRESHOLD}**)")
st.write(f"- Chop status: **{'YES' if chop else 'NO'}**")

st.write("---")

if not system_on:
    st.error("SYSTEM: OFF")

    reasons = []
    if vix_value >= VIX_THRESHOLD:
        reasons.append(f"VIX ≥ {VIX_THRESHOLD}")
    if chop:
        if chop_distance:
            reasons.append("Chop: price too close to 50-DMA")
        if chop_cross:
            reasons.append("Chop: too many 50-DMA crossovers")
    if not reasons:
        reasons.append("Unknown / data issue")

    st.write("Reason(s): " + ", ".join(reasons))
else:
    direction = "PUT CREDIT SPREADS" if close > sma50 else "CALL CREDIT SPREADS"
    st.success(f"SYSTEM: ON → {direction}")

st.caption("Educational dashboard only. Not financial advice.")

