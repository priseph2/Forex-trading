"""
Forex & Crypto Signal Generator — Streamlit dashboard
Run: streamlit run app.py
"""
import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

# On Streamlit Cloud secrets are not env vars — inject them before the fetcher loads.
if "POLYGON_API_KEY" not in os.environ:
    try:
        os.environ["POLYGON_API_KEY"] = st.secrets["POLYGON_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass

from src.data.fetcher import (
    CRYPTO_PAIRS,
    FOREX_PAIRS,
    DataFetchError,
    fetch_ohlcv,
    get_pairs_for_market,
)
from src.signals.aggregator import aggregate_signals
from src.signals.models import Direction, PairResult
from src.strategies.bollinger_strategy import BollingerStrategy
from src.strategies.ema_crossover import EMACrossoverStrategy
from src.strategies.macd_strategy import MACDStrategy
from src.strategies.rsi_strategy import RSIStrategy

STRATEGIES = [
    EMACrossoverStrategy(),
    RSIStrategy(),
    MACDStrategy(),
    BollingerStrategy(),
]

_RATE_LIMIT_DELAY = 13.0  # seconds between requests on Polygon free tier


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fetch_signals(pairs: list[str], period: int) -> tuple[list[PairResult], list[str]]:
    """Fetch OHLCV and compute signals for each pair, with rate-limit delay."""
    results: list[PairResult] = []
    warnings: list[str] = []

    progress = st.progress(0.0, text="Starting fetch…")

    for i, pair in enumerate(pairs):
        progress.progress((i) / len(pairs), text=f"Fetching {pair} ({i + 1}/{len(pairs)})…")
        try:
            ohlcv = fetch_ohlcv(pair, period)
            signals = [s.generate(pair, ohlcv) for s in STRATEGIES]
            result = aggregate_signals(pair, signals, STRATEGIES)
            results.append(result)
        except DataFetchError as e:
            warnings.append(f"Skipped **{pair}**: {e}")
        except Exception as e:
            warnings.append(f"Error on **{pair}**: {e}")

        if i < len(pairs) - 1:
            time.sleep(_RATE_LIMIT_DELAY)

    progress.progress(1.0, text="Done.")
    return results, warnings


def _results_to_df(results: list[PairResult]) -> pd.DataFrame:
    strategy_order = ["EMA Crossover", "RSI", "MACD", "Bollinger Bands"]
    rows = []
    for r in results:
        sig_map = {s.strategy: s.direction.value for s in r.signals}
        row = {"Pair": r.pair}
        for name in strategy_order:
            row[name] = sig_map.get(name, "N/A")
        row["Combined"] = r.combined.value
        row["Confidence"] = f"{r.combined_confidence * 100:.0f}%"
        rows.append(row)
    return pd.DataFrame(rows)


def _cell_style(val: str) -> str:
    if val == "BUY":
        return "background:#d4edda;color:#155724;font-weight:bold;text-align:center;padding:6px 10px"
    if val == "SELL":
        return "background:#f8d7da;color:#721c24;font-weight:bold;text-align:center;padding:6px 10px"
    if val == "HOLD":
        return "background:#fff3cd;color:#856404;font-weight:bold;text-align:center;padding:6px 10px"
    try:
        pct = int(val.strip("%"))
        color = "#155724" if pct >= 66 else "#856404" if pct >= 40 else "#721c24"
        return f"color:{color};font-weight:bold;text-align:center;padding:6px 10px"
    except ValueError:
        return "text-align:center;padding:6px 10px"


def _build_html_table(df: pd.DataFrame) -> str:
    direction_cols = {"EMA Crossover", "RSI", "MACD", "Bollinger Bands", "Combined", "Confidence"}
    header = "".join(
        f"<th style='padding:8px 12px;border-bottom:2px solid #dee2e6;text-align:center'>{c}</th>"
        for c in df.columns
    )
    rows_html = ""
    for _, row in df.iterrows():
        cells = ""
        for col, val in row.items():
            style = _cell_style(str(val)) if col in direction_cols else "padding:6px 10px;font-weight:bold"
            cells += f"<td style='{style}'>{val}</td>"
        rows_html += f"<tr style='border-bottom:1px solid #dee2e6'>{cells}</tr>"
    return (
        "<div style='overflow-x:auto'>"
        "<table style='border-collapse:collapse;width:100%;font-size:14px'>"
        f"<thead><tr style='background:#f8f9fa'>{header}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )


def _results_to_json(results: list[PairResult]) -> str:
    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Direction):
            return obj.value
        raise TypeError(type(obj))

    from dataclasses import asdict
    return json.dumps([asdict(r) for r in results], indent=2, default=_default)


def _estimate_time(n: int) -> str:
    total = n * _RATE_LIMIT_DELAY
    mins, secs = divmod(int(total), 60)
    return f"{mins}m {secs}s" if mins else f"{secs}s"


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Trading Signal Generator",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Trading Signal Generator")
st.caption("Powered by Polygon.io · EMA Crossover · RSI · MACD · Bollinger Bands")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Settings")

    market = st.selectbox(
        "Market",
        options=["forex", "crypto", "all"],
        format_func=lambda m: {"forex": "Forex Majors", "crypto": "Crypto Altcoins", "all": "Forex + Crypto"}[m],
    )

    all_pairs = list(get_pairs_for_market(market).keys())
    selected_pairs = st.multiselect(
        "Pairs (leave empty for all)",
        options=all_pairs,
        default=[],
        placeholder="All pairs selected",
    )
    pairs_to_fetch = selected_pairs if selected_pairs else all_pairs

    period = st.slider("History (days)", min_value=60, max_value=200, value=100, step=10)

    st.divider()
    st.caption(f"⏱ Est. fetch time: **{_estimate_time(len(pairs_to_fetch))}** on free tier")
    st.caption(f"Pairs selected: **{len(pairs_to_fetch)}**")

    generate = st.button("🚀 Generate Signals", type="primary", use_container_width=True)

# ── Main area ─────────────────────────────────────────────────────────────────

if generate:
    st.session_state.pop("results", None)  # clear previous cache on manual refresh

    with st.spinner(""):
        results, warnings = _fetch_signals(pairs_to_fetch, period)

    st.session_state["results"] = results
    st.session_state["warnings"] = warnings
    st.session_state["fetched_at"] = datetime.now(timezone.utc)

# Show results if available in session state
if "results" in st.session_state:
    results: list[PairResult] = st.session_state["results"]
    warnings: list[str] = st.session_state.get("warnings", [])
    fetched_at: datetime = st.session_state.get("fetched_at")

    for w in warnings:
        st.warning(w)

    if not results:
        st.error("No signals generated. Check your POLYGON_API_KEY in the .env file.")
    else:
        # Summary metric cards
        buy_count = sum(1 for r in results if r.combined == Direction.BUY)
        sell_count = sum(1 for r in results if r.combined == Direction.SELL)
        hold_count = sum(1 for r in results if r.combined == Direction.HOLD)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Pairs", len(results))
        col2.metric("🟢 BUY", buy_count)
        col3.metric("🔴 SELL", sell_count)
        col4.metric("🟡 HOLD", hold_count)

        st.divider()

        # Color-coded signals table
        market_label = {"forex": "Forex", "crypto": "Crypto", "all": "Forex & Crypto"}.get(
            st.session_state.get("market", market), "Signals"
        )
        ts = fetched_at.strftime("%Y-%m-%d %H:%M UTC") if fetched_at else ""
        st.subheader(f"{market_label} Signals — {ts}")

        df = _results_to_df(results)
        st.markdown(_build_html_table(df), unsafe_allow_html=True)

        st.divider()

        # Download button
        json_str = _results_to_json(results)
        st.download_button(
            label="⬇️ Download signals as JSON",
            data=json_str,
            file_name=f"signals_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
        )

else:
    st.info("Configure your settings in the sidebar and click **Generate Signals** to start.")
    st.markdown("""
**How it works:**
1. Select a market and optionally specific pairs
2. Click **Generate Signals**
3. The system fetches daily OHLCV data from Polygon.io and runs four strategies:
   - **EMA Crossover** — trend direction from EMA20/EMA50 crossover
   - **RSI** — overbought (>70 → SELL) / oversold (<30 → BUY)
   - **MACD** — momentum crossover signal
   - **Bollinger Bands** — price outside band signals mean reversion
4. A weighted combined signal with confidence score is shown per pair
""")
