import streamlit as st
import requests
from textblob import TextBlob
import pandas as pd
import pydeck as pdk
from datetime import datetime, timezone

# ==============================================================================
# PROJECT CORA V3 — Interactive Maritime Intelligence & Decision Simulator
# ============================================================================

st.set_page_config(
    page_title="Project CORA V3 | Interactive Maritime Intelligence Simulator",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------
# Light enterprise styling
# -------------------------------
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        background: rgba(127,127,127,0.06);
        border: 1px solid rgba(127,127,127,0.18);
        padding: 14px;
        border-radius: 12px;
    }
    .small-note {font-size: 0.84rem; opacity: 0.78;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

NODE_CONFIG = {
    "Red Sea / Bab al-Mandab": {
        "gdelt_keyword": '"Bab al-Mandab" (attack OR crisis OR shipping OR vessel OR missile)',
        "gdelt_fallback": '"Bab al-Mandab" shipping',
        "wolfram_query": "distance Suez Canal Bab el Mandeb",
        "spatial_reference": "≈ 2,210 km",
        "spatial_description": "Approximate Suez Canal–Bab al-Mandab route baseline",
        "spatial_source": "Verified geographic baseline",
        "baseline_risk": 55,
        "default_delay_days": 5,
        "default_asset": 15_000_000,
        "default_daily_delay": 45_000,
        "node_lat": 12.5833,
        "node_lon": 43.3333,
        "origin_lat": 29.9667,
        "origin_lon": 32.5500,
    },
    "Strait of Hormuz": {
        "gdelt_keyword": '"Strait of Hormuz" (military OR tanker OR shipping OR attack OR seizure)',
        "gdelt_fallback": '"Strait of Hormuz" shipping',
        "wolfram_query": "Strait of Hormuz width",
        "spatial_reference": "≈ 39 km",
        "spatial_description": "Approximate width of the Strait of Hormuz at its narrowest area",
        "spatial_source": "Verified geographic baseline",
        "baseline_risk": 45,
        "default_delay_days": 4,
        "default_asset": 22_000_000,
        "default_daily_delay": 60_000,
        "node_lat": 26.5667,
        "node_lon": 56.2500,
        "origin_lat": 25.0109,
        "origin_lon": 55.0617,
    },
    "Malacca Strait": {
        "gdelt_keyword": '"Strait of Malacca" (piracy OR shipping OR vessel OR disruption OR collision)',
        "gdelt_fallback": '"Strait of Malacca" shipping',
        "wolfram_query": "Strait of Malacca length",
        "spatial_reference": "≈ 800 km",
        "spatial_description": "Approximate length of the Strait of Malacca",
        "spatial_source": "Verified geographic baseline",
        "baseline_risk": 25,
        "default_delay_days": 2,
        "default_asset": 8_000_000,
        "default_daily_delay": 25_000,
        "node_lat": 4.0000,
        "node_lon": 99.0000,
        "origin_lat": 1.2644,
        "origin_lon": 103.8400,
    },
}

SHOCKS = {
    "None": {"risk": 0, "delay_mult": 1.0, "cost_mult": 1.0, "label": "No additional shock"},
    "Missile / drone attack": {"risk": 18, "delay_mult": 1.7, "cost_mult": 1.20, "label": "Kinetic attack scenario"},
    "Port closure": {"risk": 22, "delay_mult": 2.4, "cost_mult": 1.30, "label": "Port / channel closure scenario"},
    "Vessel seizure": {"risk": 20, "delay_mult": 1.9, "cost_mult": 1.35, "label": "Seizure / detention scenario"},
    "GPS disruption": {"risk": 12, "delay_mult": 1.35, "cost_mult": 1.10, "label": "Navigation interference scenario"},
    "Cyberattack": {"risk": 14, "delay_mult": 1.45, "cost_mult": 1.15, "label": "Operational cyber disruption scenario"},
    "Oil price shock": {"risk": 7, "delay_mult": 1.10, "cost_mult": 1.25, "label": "Fuel / commodity price scenario"},
}

REQUEST_TIMEOUT = 8
DEFAULT_HEADLINE = "No recent matching headline was returned by the configured GDELT query."
DEFAULT_SOURCE = "https://www.gdeltproject.org/"


# ==============================================================================
# 2. HELPERS
# ==============================================================================

@st.cache_data(ttl=600, show_spinner=False)
def fetch_gdelt_latest(primary_keyword: str, fallback_keyword: str):
    """
    Best-effort GDELT retrieval.

    Returns a dict with:
      ok, headline, url, error, query_used, window
    """
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    headers = {"User-Agent": "Project-CORA/2.2 research prototype"}

    attempts = [
        (primary_keyword, "15min", 5),
        (fallback_keyword, "1h", 6),
    ]

    last_error = None

    for query, window, timeout_s in attempts:
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": 5,
            "timespan": window,
            "sort": "datedesc",
        }

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout_s,
            )
            response.raise_for_status()
            payload = response.json()
            articles = payload.get("articles", [])

            if articles:
                article = articles[0]
                return {
                    "ok": True,
                    "headline": article.get("title") or "Untitled GDELT result",
                    "url": article.get("url") or DEFAULT_SOURCE,
                    "error": None,
                    "query_used": query,
                    "window": window,
                }

        except (requests.RequestException, ValueError, TypeError) as exc:
            last_error = str(exc)

    return {
        "ok": False,
        "headline": None,
        "url": None,
        "error": last_error or "No matching GDELT article was returned.",
        "query_used": None,
        "window": None,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_wolfram(query: str, app_id: str):
    if not app_id:
        return None, "Wolfram AppID is not configured."

    try:
        response = requests.get(
            "https://api.wolframalpha.com/v1/result",
            params={"appid": app_id, "i": query, "units": "metric"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.text.strip()
        return (result if result else None), None
    except requests.RequestException as exc:
        return None, f"Wolfram request failed: {exc}"


def polarity(text: str) -> float:
    try:
        return float(TextBlob(text).sentiment.polarity)
    except Exception:
        return 0.0


def clamp(value, low, high):
    return max(low, min(value, high))


def money(value):
    return f"USD {value:,.0f}"


def risk_band(score):
    if score >= 75:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "ELEVATED"
    return "MODERATE"


def confidence_band(score):
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


# ==============================================================================
# 3. HEADER
# ==============================================================================

st.title("🚢 Project CORA")
st.subheader("Interactive Maritime Intelligence & Decision Simulator")
st.caption(
    "An interactive OSINT-enabled prototype for building, challenging, comparing and recording maritime crisis decisions."
)
st.markdown("**Principal Investigator:** Mohd Khairul Ridhuan bin Mohd Fadzil")
st.divider()


# ==============================================================================
# 4. SIDEBAR — CONTROL ROOM
# ==============================================================================

with st.sidebar:
    st.header("🎛️ CORA Control Room")

    scenario_name = st.text_input(
        "Scenario name",
        value="Maritime Crisis Scenario",
        help="Give the current simulation a name before saving it to Decision History.",
    )

    current_node = st.selectbox(
        "Maritime chokepoint",
        list(NODE_CONFIG.keys()),
        index=0,
    )
    cfg = NODE_CONFIG[current_node]

    st.markdown("### Company exposure")
    asset_exposure = st.number_input(
        "Fleet / vessel value (USD)",
        min_value=0,
        value=int(cfg["default_asset"]),
        step=500_000,
    )
    cargo_value = st.number_input(
        "Cargo value (USD)",
        min_value=0,
        value=8_500_000,
        step=250_000,
    )
    ships_exposed = st.number_input(
        "Ships exposed",
        min_value=1,
        max_value=100,
        value=3,
        step=1,
    )
    daily_delay_cost = st.number_input(
        "Daily delay cost per ship (USD)",
        min_value=0,
        value=int(cfg["default_daily_delay"]),
        step=5_000,
    )

    st.markdown("### Scenario assumptions")
    threat_severity = st.slider(
        "Analyst threat severity",
        min_value=0,
        max_value=100,
        value=55,
        help="User-adjustable analyst judgement. It is not a measured probability.",
    )
    expected_disruption_days = st.slider(
        "Expected disruption (days)",
        min_value=1,
        max_value=30,
        value=int(cfg["default_delay_days"]),
    )
    assumed_premium_rate = st.slider(
        "Scenario insurance premium (%)",
        min_value=0.0,
        max_value=15.0,
        value=4.5,
        step=0.5,
    ) / 100

    analyst_confidence = st.select_slider(
        "Analyst confidence",
        options=["Low", "Medium", "High"],
        value="Medium",
    )

    risk_appetite = st.select_slider(
        "Management risk appetite",
        options=["Conservative", "Balanced", "Aggressive"],
        value="Balanced",
        help="Changes how strongly CORA penalizes residual risk when ranking decisions.",
    )

    st.markdown("### Decision priorities")
    cost_priority = st.slider(
        "Cost priority",
        min_value=0,
        max_value=100,
        value=40,
        help="Relative importance of estimated financial cost.",
    )
    risk_priority = st.slider(
        "Risk priority",
        min_value=0,
        max_value=100,
        value=45,
        help="Relative importance of residual risk.",
    )
    delay_priority = st.slider(
        "Delay priority",
        min_value=0,
        max_value=100,
        value=15,
        help="Relative importance of time delay.",
    )

    priority_sum = max(cost_priority + risk_priority + delay_priority, 1)
    cost_weight = cost_priority / priority_sum
    risk_weight = risk_priority / priority_sum
    delay_weight = delay_priority / priority_sum

    shock = st.selectbox("Scenario shock", list(SHOCKS.keys()))
    shock_cfg = SHOCKS[shock]

    st.markdown("### Evidence controls")
    verified_incident = st.checkbox("Verified security incident", value=False)
    navigation_disruption = st.checkbox("Navigation / AIS anomaly", value=False)
    port_disruption = st.checkbox("Port / channel disruption", value=False)
    insurer_confirmation = st.checkbox("Insurance / broker confirmation", value=False)

    st.markdown("### Intelligence source mode")
    intelligence_mode = st.selectbox(
        "Primary intelligence mode",
        [
            "Hybrid: GDELT + analyst",
            "Analyst only",
            "GDELT only",
        ],
        index=0,
        help="Hybrid uses live/cached GDELT when available and keeps analyst judgement explicit.",
    )

    manual_event = st.selectbox(
        "Analyst-observed event",
        [
            "No additional event",
            "Security incident",
            "Navigation interference",
            "Port disruption",
            "Vessel detention / seizure",
            "Cyber disruption",
            "Other operational concern",
        ],
        index=0,
    )

    manual_event_severity = st.slider(
        "Manual event severity",
        min_value=0,
        max_value=100,
        value=50,
        disabled=(manual_event == "No additional event"),
        help="Severity of the analyst-entered event. This is an assumption, not a probability.",
    )

    manual_source_confidence = st.select_slider(
        "Manual source confidence",
        options=["Low", "Medium", "High"],
        value="Medium",
        disabled=(manual_event == "No additional event"),
    )

    manual_note = st.text_input(
        "Analyst note (optional)",
        placeholder="e.g., port authority notice, broker call, internal operations report",
    )

    run = st.button("▶ Run / Refresh Scenario", use_container_width=True, type="primary")

    st.caption("Inputs recalculate automatically. The button is provided as an explicit control-room action.")


# ==============================================================================
# 5. LIVE DATA
# ==============================================================================

try:
    WOLFRAM_APP_ID = st.secrets.get("WOLFRAM_APP_ID", "")
except Exception:
    WOLFRAM_APP_ID = ""

gdelt_result = fetch_gdelt_latest(
    cfg["gdelt_keyword"],
    cfg["gdelt_fallback"],
)

# Persist the last successful GDELT result for this browser session.
if "last_good_gdelt" not in st.session_state:
    st.session_state.last_good_gdelt = {}

if gdelt_result["ok"]:
    st.session_state.last_good_gdelt[current_node] = {
        "headline": gdelt_result["headline"],
        "url": gdelt_result["url"],
        "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "query_used": gdelt_result["query_used"],
        "window": gdelt_result["window"],
    }

last_good = st.session_state.last_good_gdelt.get(current_node)

if intelligence_mode == "Analyst only":
    gdelt_state = "DISABLED"
    headline = None
    source_url = None
    headline_sentiment = None
    gdelt_age_note = "Live GDELT is disabled by analyst selection."
elif gdelt_result["ok"]:
    gdelt_state = "LIVE"
    headline = gdelt_result["headline"]
    source_url = gdelt_result["url"]
    headline_sentiment = polarity(headline)
    gdelt_age_note = f"Live result | window: {gdelt_result['window']}"
elif last_good and intelligence_mode != "Analyst only":
    gdelt_state = "LAST SUCCESS"
    headline = last_good["headline"]
    source_url = last_good["url"]
    headline_sentiment = polarity(headline)
    gdelt_age_note = f"Last successful session result captured {last_good['captured_utc']}"
else:
    gdelt_state = "UNKNOWN"
    headline = None
    source_url = None
    headline_sentiment = None
    gdelt_age_note = "No live or session-cached GDELT result is available."

gdelt_error = gdelt_result["error"]

# Geography is treated as a stable reference, not as a live dependency.
# Wolfram is optional enrichment/validation only.
spatial_metric = cfg["spatial_reference"]
spatial_answer, wolfram_error = fetch_wolfram(cfg["wolfram_query"], WOLFRAM_APP_ID)

if spatial_answer:
    wolfram_status = "LIVE VALIDATION AVAILABLE"
    wolfram_status_icon = "🟢"
else:
    wolfram_status = "OPTIONAL VALIDATION UNAVAILABLE"
    wolfram_status_icon = "⚪"

# ==============================================================================
# 6. RISK ENGINE
# ==============================================================================

# Transparent prototype scoring, not a probability model.
# Missing GDELT data is UNKNOWN, not neutral.
# Live results receive full heuristic weight; session-cached results receive half weight.
if headline_sentiment is None or intelligence_mode == "Analyst only":
    headline_component = 0.0
elif gdelt_state == "LIVE":
    headline_component = max(0, -headline_sentiment) * 15
elif gdelt_state == "LAST SUCCESS":
    headline_component = max(0, -headline_sentiment) * 7.5
else:
    headline_component = 0.0

manual_confidence_weight = {"Low": 0.45, "Medium": 0.70, "High": 1.00}[manual_source_confidence]
manual_event_component = 0.0
if intelligence_mode != "GDELT only" and manual_event != "No additional event":
    manual_event_component = (manual_event_severity / 100) * 18 * manual_confidence_weight
threat_component = threat_severity * 0.35
verification_component = (
    (12 if verified_incident else 0)
    + (8 if navigation_disruption else 0)
    + (10 if port_disruption else 0)
    + (6 if insurer_confirmation else 0)
)

raw_risk = (
    cfg["baseline_risk"] * 0.45
    + threat_component
    + headline_component
    + verification_component
    + shock_cfg["risk"]
    + manual_event_component
)

risk_score = int(round(clamp(raw_risk, 0, 100)))
band = risk_band(risk_score)

confidence_numeric = {"Low": 35, "Medium": 60, "High": 82}[analyst_confidence]
objective_evidence_count = sum([
    verified_incident,
    navigation_disruption,
    port_disruption,
    insurer_confirmation,
])
confidence_adjustment = objective_evidence_count * 4

if intelligence_mode != "Analyst only" and gdelt_state == "UNKNOWN":
    confidence_adjustment -= 10
elif gdelt_state == "LAST SUCCESS":
    confidence_adjustment -= 4

if intelligence_mode != "GDELT only" and manual_event != "No additional event":
    confidence_adjustment += {"Low": 1, "Medium": 3, "High": 5}[manual_source_confidence]

confidence_score = int(clamp(confidence_numeric + confidence_adjustment, 0, 95))

adjusted_delay_days = max(
    1,
    round(expected_disruption_days * shock_cfg["delay_mult"])
)

premium_cost = asset_exposure * assumed_premium_rate * shock_cfg["cost_mult"]
base_delay_exposure = adjusted_delay_days * daily_delay_cost * ships_exposed
cargo_at_risk = cargo_value * (risk_score / 100)

# Decision scenarios
continue_cost = (
    premium_cost
    + base_delay_exposure * 0.45
    + cargo_at_risk * 0.08
    + asset_exposure * (risk_score / 100) * 0.025
)

hold_days = max(2, round(adjusted_delay_days * 0.55))
hold_cost = (
    hold_days * daily_delay_cost * ships_exposed
    + premium_cost * 0.55
    + cargo_at_risk * 0.02
)

reroute_days = max(3, round(adjusted_delay_days * 0.75 + 3))
reroute_cost = (
    reroute_days * daily_delay_cost * ships_exposed * 1.12
    + premium_cost * 0.30
    + cargo_value * 0.01
)

continue_risk = risk_score
hold_risk = int(clamp(risk_score - 18, 0, 100))
reroute_risk = int(clamp(risk_score - 30, 0, 100))

scenario_df = pd.DataFrame({
    "Decision": ["Continue transit", "Hold / delay", "Reroute"],
    "Estimated Cost (USD)": [continue_cost, hold_cost, reroute_cost],
    "Indicative Delay (days)": [1, hold_days, reroute_days],
    "Residual Risk Score": [continue_risk, hold_risk, reroute_risk],
})
scenario_df["Risk Band"] = scenario_df["Residual Risk Score"].apply(risk_band)

# User-adjustable decision score: lower is better.
# Management risk appetite changes the penalty applied to residual risk.
appetite_multiplier = {
    "Conservative": 1.25,
    "Balanced": 1.00,
    "Aggressive": 0.78,
}[risk_appetite]

normalized_cost = (
    scenario_df["Estimated Cost (USD)"]
    / max(scenario_df["Estimated Cost (USD)"].max(), 1)
)
normalized_risk = scenario_df["Residual Risk Score"] / 100
normalized_delay = (
    scenario_df["Indicative Delay (days)"]
    / max(scenario_df["Indicative Delay (days)"].max(), 1)
)

scenario_df["Decision Score"] = (
    normalized_cost * cost_weight
    + normalized_risk * risk_weight * appetite_multiplier
    + normalized_delay * delay_weight
) * 100

recommended_row = scenario_df.loc[scenario_df["Decision Score"].idxmin()]
recommended_action = recommended_row["Decision"]


# ==============================================================================
# 7. EXECUTIVE OVERVIEW
# ==============================================================================

st.markdown(f"### 📍 Active Node: {current_node}")
if shock != "None":
    st.warning(f"**Scenario shock active:** {shock_cfg['label']}")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Risk score", f"{risk_score}/100", band)
m2.metric("Confidence", f"{confidence_score}%", confidence_band(confidence_score))
m3.metric("Ships exposed", f"{ships_exposed}")
m4.metric("Adjusted disruption", f"{adjusted_delay_days} days")
m5.metric("Scenario premium", money(premium_cost))

st.progress(risk_score / 100, text=f"Overall prototype risk: {band} ({risk_score}/100)")

if band in ["CRITICAL", "HIGH"]:
    st.error(
        f"CORA currently assesses **{band}** prototype risk at {current_node}. "
        "The model recommends comparing mitigation options before committing additional exposure."
    )
elif band == "ELEVATED":
    st.warning(
        f"CORA currently assesses **ELEVATED** prototype risk at {current_node}. "
        "Independent verification is recommended before a material route decision."
    )
else:
    st.success(
        f"CORA currently assesses **MODERATE** prototype risk at {current_node}. "
        "Baseline monitoring remains appropriate under current assumptions."
    )

st.divider()


# ==============================================================================
# 8. INTERACTIVE DECISION SIMULATOR
# ==============================================================================

st.header("🧭 Interactive Decision Simulator")
st.caption(
    "Change any Control Room assumption and all management options recalculate immediately. "
    "You can also select your own decision and compare it with CORA's recommendation."
)

priority_cols = st.columns(4)
priority_cols[0].metric("Cost weight", f"{cost_weight:.0%}")
priority_cols[1].metric("Risk weight", f"{risk_weight:.0%}")
priority_cols[2].metric("Delay weight", f"{delay_weight:.0%}")
priority_cols[3].metric("Risk appetite", risk_appetite)

show_df = scenario_df[[
    "Decision",
    "Estimated Cost (USD)",
    "Indicative Delay (days)",
    "Residual Risk Score",
    "Risk Band",
    "Decision Score",
]].copy()

show_df["Estimated Cost (USD)"] = show_df["Estimated Cost (USD)"].round(0).astype(int)
show_df["Decision Score"] = show_df["Decision Score"].round(1)

st.dataframe(
    show_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Estimated Cost (USD)": st.column_config.NumberColumn(format="USD %,.0f"),
        "Residual Risk Score": st.column_config.ProgressColumn(min_value=0, max_value=100),
        "Decision Score": st.column_config.NumberColumn(format="%.1f"),
    },
)

c1, c2, c3 = st.columns(3)
for col, (_, row) in zip([c1, c2, c3], scenario_df.iterrows()):
    with col:
        st.subheader(row["Decision"])
        st.metric("Estimated cost", money(row["Estimated Cost (USD)"]))
        st.metric("Residual risk", f"{int(row['Residual Risk Score'])}/100", row["Risk Band"])
        st.metric("Delay", f"{int(row['Indicative Delay (days)'])} day(s)")
        st.caption(f"Decision score: {row['Decision Score']:.1f}")

st.info(
    f"**CORA recommendation:** {recommended_action}. "
    "It currently has the lowest weighted cost–risk–delay score under your selected priorities and risk appetite."
)

st.markdown("### 👤 Management decision")
user_decision = st.radio(
    "Which action would you choose?",
    scenario_df["Decision"].tolist(),
    horizontal=True,
    index=scenario_df["Decision"].tolist().index(recommended_action),
)

user_row = scenario_df.loc[scenario_df["Decision"] == user_decision].iloc[0]
rec_row = scenario_df.loc[scenario_df["Decision"] == recommended_action].iloc[0]

decision_match = user_decision == recommended_action

if decision_match:
    st.success("Your selected action currently matches CORA's recommended option.")
else:
    cost_delta = user_row["Estimated Cost (USD)"] - rec_row["Estimated Cost (USD)"]
    risk_delta = int(user_row["Residual Risk Score"] - rec_row["Residual Risk Score"])
    delay_delta = int(user_row["Indicative Delay (days)"] - rec_row["Indicative Delay (days)"])

    st.warning(
        f"Your decision differs from CORA. Compared with **{recommended_action}**, "
        f"your choice changes estimated cost by **{money(cost_delta)}**, "
        f"residual risk by **{risk_delta:+d} points**, and delay by **{delay_delta:+d} day(s)**."
    )

# ------------------------------------------------------------------
# Stress-test laboratory
# ------------------------------------------------------------------
st.markdown("### 🧪 Stress-Test Laboratory")
st.caption(
    "Test how sensitive the current decision is to different threat conditions without changing the saved Control Room inputs."
)

stress_options = {
    "Current assumptions": 0,
    "Threat +15": 15,
    "Threat +30": 30,
    "Threat -15": -15,
}
stress_choice = st.selectbox("Stress test", list(stress_options.keys()), index=0)
stress_delta = stress_options[stress_choice]

stress_risk = int(clamp(risk_score + stress_delta, 0, 100))

stress_df = scenario_df[["Decision", "Estimated Cost (USD)", "Indicative Delay (days)"]].copy()
stress_df["Stress Residual Risk"] = [
    stress_risk,
    int(clamp(stress_risk - 18, 0, 100)),
    int(clamp(stress_risk - 30, 0, 100)),
]
stress_df["Stress Risk Band"] = stress_df["Stress Residual Risk"].apply(risk_band)

stress_cost = stress_df["Estimated Cost (USD)"] / max(stress_df["Estimated Cost (USD)"].max(), 1)
stress_risk_norm = stress_df["Stress Residual Risk"] / 100
stress_delay = stress_df["Indicative Delay (days)"] / max(stress_df["Indicative Delay (days)"].max(), 1)

stress_df["Stress Decision Score"] = (
    stress_cost * cost_weight
    + stress_risk_norm * risk_weight * appetite_multiplier
    + stress_delay * delay_weight
) * 100

stress_recommendation = stress_df.loc[stress_df["Stress Decision Score"].idxmin(), "Decision"]

s1, s2, s3 = st.columns(3)
s1.metric("Stress-test risk", f"{stress_risk}/100", risk_band(stress_risk))
s2.metric("Current recommendation", recommended_action)
s3.metric("Stress recommendation", stress_recommendation)

if stress_recommendation != recommended_action:
    st.warning(
        f"⚠️ Recommendation changes from **{recommended_action}** to "
        f"**{stress_recommendation}** under `{stress_choice}`."
    )
else:
    st.success(
        f"Recommendation remains **{recommended_action}** under `{stress_choice}`."
    )

# ------------------------------------------------------------------
# Save decision to session history
# ------------------------------------------------------------------
if "decision_history" not in st.session_state:
    st.session_state.decision_history = []

save_col, clear_col = st.columns([1, 1])

with save_col:
    if st.button("💾 Save current scenario to Decision History", use_container_width=True):
        st.session_state.decision_history.append(
            {
                "Timestamp UTC": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "Scenario": scenario_name,
                "Node": current_node,
                "Risk Score": risk_score,
                "Risk Band": band,
                "Confidence": confidence_score,
                "Shock": shock,
                "Management Choice": user_decision,
                "CORA Recommendation": recommended_action,
                "Selected Cost USD": round(float(user_row["Estimated Cost (USD)"]), 2),
                "Selected Residual Risk": int(user_row["Residual Risk Score"]),
                "Selected Delay Days": int(user_row["Indicative Delay (days)"]),
                "Risk Appetite": risk_appetite,
            }
        )
        st.success("Scenario saved to this session's Decision History.")

with clear_col:
    if st.button("🗑️ Clear Decision History", use_container_width=True):
        st.session_state.decision_history = []
        st.success("Decision History cleared.")

if st.session_state.decision_history:
    history_df = pd.DataFrame(st.session_state.decision_history)
    st.markdown("### 🕘 Decision History")
    st.dataframe(history_df, hide_index=True, use_container_width=True)

    st.download_button(
        "⬇ Download Decision History (CSV)",
        data=history_df.to_csv(index=False).encode("utf-8"),
        file_name="cora_decision_history.csv",
        mime="text/csv",
    )
else:
    st.caption("No scenarios have been saved during this session yet.")

st.divider()


# ==============================================================================
# 9. CHALLENGE THE INTELLIGENCE
# ==============================================================================

st.header("🔎 Challenge the Intelligence")

for_count = 0
against_count = 0

for_evidence = []
against_evidence = []

if verified_incident:
    for_evidence.append("Verified security incident selected")
    for_count += 1
else:
    against_evidence.append("No verified security incident selected")
    against_count += 1

if navigation_disruption:
    for_evidence.append("Navigation / AIS anomaly selected")
    for_count += 1
else:
    against_evidence.append("No navigation / AIS anomaly selected")
    against_count += 1

if port_disruption:
    for_evidence.append("Port / channel disruption selected")
    for_count += 1
else:
    against_evidence.append("No port / channel disruption selected")
    against_count += 1

if insurer_confirmation:
    for_evidence.append("Insurance / broker confirmation selected")
    for_count += 1
else:
    against_evidence.append("No insurer / broker confirmation selected")
    against_count += 1

if headline_sentiment is not None:
    if headline_sentiment < -0.05:
        for_evidence.append(
            f"{gdelt_state.title()} GDELT headline has negative polarity ({headline_sentiment:.2f})"
        )
    else:
        against_evidence.append(
            f"{gdelt_state.title()} GDELT headline is not materially negative ({headline_sentiment:.2f})"
        )
elif intelligence_mode != "Analyst only":
    against_evidence.append("GDELT status is UNKNOWN; absence of data is not treated as neutral evidence")

if intelligence_mode != "GDELT only" and manual_event != "No additional event":
    for_evidence.append(
        f"Analyst-entered event: {manual_event} | severity {manual_event_severity}/100 | "
        f"source confidence {manual_source_confidence}"
    )

if shock != "None":
    for_evidence.append(f"Scenario stressor applied: {shock}")

left, right = st.columns(2)
with left:
    st.markdown("#### Evidence supporting elevated risk")
    if for_evidence:
        for item in for_evidence:
            st.write(f"✓ {item}")
    else:
        st.write("No additional supporting indicators selected.")

with right:
    st.markdown("#### Evidence limiting the assessment")
    if against_evidence:
        for item in against_evidence:
            st.write(f"✗ {item}")
    else:
        st.write("No major limiting indicators selected.")

st.metric("Analytical confidence", f"{confidence_score}%", confidence_band(confidence_score))
st.caption(
    "Confidence reflects user-selected analyst confidence plus the number of corroborating evidence controls. "
    "It is not a calibrated statistical probability."
)


st.markdown("### 💬 Ask CORA")
question = st.selectbox(
    "Ask a decision question",
    [
        "Why is CORA recommending this option?",
        "What could make this assessment wrong?",
        "What evidence would change the recommendation?",
        "What is the biggest financial exposure?",
        "What is the weakest part of the intelligence?",
    ],
)

if question == "Why is CORA recommending this option?":
    st.write(
        f"CORA recommends **{recommended_action}** because it has the lowest weighted "
        f"decision score under your current priorities: cost {cost_weight:.0%}, "
        f"risk {risk_weight:.0%}, delay {delay_weight:.0%}, with a "
        f"**{risk_appetite.lower()}** management risk appetite."
    )
    st.write(
        f"The option's residual risk is **{int(rec_row['Residual Risk Score'])}/100**, "
        f"estimated cost is **{money(rec_row['Estimated Cost (USD)'])}**, and "
        f"indicative delay is **{int(rec_row['Indicative Delay (days)'])} day(s)**."
    )

elif question == "What could make this assessment wrong?":
    weaknesses = []
    if gdelt_state in ["UNKNOWN", "LAST SUCCESS", "DISABLED"]:
        weaknesses.append(f"GDELT evidence is currently {gdelt_state.lower()}.")
    if not verified_incident:
        weaknesses.append("No verified security incident has been selected.")
    if not navigation_disruption:
        weaknesses.append("No navigation/AIS anomaly has been selected.")
    if not port_disruption:
        weaknesses.append("No port/channel disruption has been selected.")
    if not insurer_confirmation:
        weaknesses.append("No insurer/broker confirmation has been selected.")
    if manual_event != "No additional event" and manual_source_confidence == "Low":
        weaknesses.append("The analyst-entered event has low source confidence.")
    if not weaknesses:
        weaknesses.append(
            "The main remaining weakness is that CORA is still a heuristic prototype rather than a calibrated predictive model."
        )
    for w in weaknesses:
        st.write(f"• {w}")

elif question == "What evidence would change the recommendation?":
    st.write(
        "The recommendation is most likely to change if one or more of these variables move materially:"
    )
    st.write("• verified incident status or port/navigation disruption")
    st.write("• threat severity")
    st.write("• expected disruption days")
    st.write("• insurance premium assumption")
    st.write("• management cost/risk/delay priorities")
    st.write("• management risk appetite")
    st.write(
        f"Current stress-test result: **{stress_recommendation}** under `{stress_choice}`."
    )

elif question == "What is the biggest financial exposure?":
    exposures = {
        "Fleet / vessel value": float(asset_exposure),
        "Cargo value": float(cargo_value),
        "Base delay exposure": float(base_delay_exposure),
        "Scenario premium": float(premium_cost),
    }
    biggest_name = max(exposures, key=exposures.get)
    st.write(
        f"The largest direct exposure currently entered is **{biggest_name}** at "
        f"**{money(exposures[biggest_name])}**."
    )
    st.caption(
        "This is a direct comparison of configured scenario values, not an expected-loss calculation."
    )

else:
    if gdelt_state == "UNKNOWN":
        st.write(
            "**Weakest intelligence element:** live external corroboration. "
            "GDELT is currently UNKNOWN, so CORA is relying more heavily on analyst inputs and selected evidence controls."
        )
    elif objective_evidence_count == 0:
        st.write(
            "**Weakest intelligence element:** corroboration. No independent evidence control "
            "has been selected beyond the headline/manual scenario inputs."
        )
    else:
        st.write(
            f"The current analytical confidence is **{confidence_score}% ({confidence_band(confidence_score)})**. "
            "Review the Evidence limiting the assessment panel above for the weakest assumptions."
        )


st.divider()


# ==============================================================================
# 10. LIVE OSINT PANEL
# ==============================================================================

st.header("🌐 Open-Source Intelligence Inputs")
os1, os2 = st.columns([2, 1])

with os1:
    st.markdown("#### GDELT intelligence feed")

    state_icon = {
        "LIVE": "🟢",
        "LAST SUCCESS": "🟠",
        "UNKNOWN": "⚪",
        "DISABLED": "🔵",
    }[gdelt_state]

    st.markdown(f"**Source status:** {state_icon} {gdelt_state}")
    st.caption(gdelt_age_note)

    if headline:
        st.write(f"**{headline}**")
        if source_url:
            st.link_button("Open source article", source_url)

        if headline_sentiment is not None:
            st.caption(
                f"Headline polarity: {headline_sentiment:.2f} | "
                f"Risk-engine weight: {'full' if gdelt_state == 'LIVE' else 'reduced'}"
            )
    else:
        st.info(
            "No GDELT evidence is currently being scored. "
            "CORA treats this state as **UNKNOWN**, not as neutral or safe."
        )

    if intelligence_mode != "GDELT only":
        st.markdown("#### Analyst intelligence")
        if manual_event == "No additional event":
            st.caption("No additional analyst-entered event is active.")
        else:
            st.write(
                f"**{manual_event}** — severity **{manual_event_severity}/100**, "
                f"source confidence **{manual_source_confidence}**"
            )
            if manual_note:
                st.caption(f"Analyst note: {manual_note}")

    with st.expander("GDELT technical diagnostics"):
        st.write(f"Configured mode: **{intelligence_mode}**")
        st.write(f"Current state: **{gdelt_state}**")
        if gdelt_result["ok"]:
            st.success(
                f"Live GDELT query succeeded using window {gdelt_result['window']}."
            )
            st.caption(f"Query used: {gdelt_result['query_used']}")
        else:
            st.warning(
                "Live retrieval did not succeed. CORA continues operating without "
                "treating missing data as a neutral signal."
            )
            if gdelt_error:
                st.code(gdelt_error)

with os2:
    st.markdown("#### Spatial reference")
    st.metric("Geographic baseline", spatial_metric)
    st.caption(cfg["spatial_description"])
    st.markdown("**Source status:** 🔵 STATIC REFERENCE")
    st.caption(cfg["spatial_source"])

    with st.expander("Optional Wolfram validation"):
        st.write(f"{wolfram_status_icon} **{wolfram_status}**")
        st.caption(f"Validation query: {cfg['wolfram_query']}")
        if spatial_answer:
            st.success(f"Wolfram response: {spatial_answer}")
        else:
            st.caption(
                "The CORA risk engine does not depend on this lookup. "
                "The verified static geographic baseline remains in use."
            )
            if wolfram_error:
                st.caption(f"Technical detail: {wolfram_error}")

st.caption(
    "CORA separates source availability from source meaning. A failed GDELT request "
    "does not imply a neutral security environment. Geographic dimensions remain "
    "stable reference data; Wolfram is optional validation only."
)

st.divider()


# ==============================================================================
# 11. GEOSPATIAL VIEW
# ==============================================================================

st.header("🗺️ Geospatial Decision View")

map_df = pd.DataFrame({
    "from_lat": [cfg["origin_lat"]],
    "from_lon": [cfg["origin_lon"]],
    "to_lat": [cfg["node_lat"]],
    "to_lon": [cfg["node_lon"]],
    "risk_score": [risk_score],
    "risk_band": [band],
    "node": [current_node],
    "elevation": [max(1_000, risk_score * 25_000)],
})

arc_layer = pdk.Layer(
    "ArcLayer",
    data=map_df,
    get_source_position="[from_lon, from_lat]",
    get_target_position="[to_lon, to_lat]",
    get_source_color=[60, 170, 255, 180],
    get_target_color=[255, 90, 90, 220],
    get_width=5,
    pickable=True,
)

column_layer = pdk.Layer(
    "ColumnLayer",
    data=map_df,
    get_position="[to_lon, to_lat]",
    get_elevation="elevation",
    elevation_scale=1,
    radius=50_000,
    get_fill_color=[255, 90, 90, 165],
    pickable=True,
    auto_highlight=True,
)

view_state = pdk.ViewState(
    latitude=cfg["node_lat"],
    longitude=cfg["node_lon"],
    zoom=4,
    pitch=50,
    bearing=0,
)

st.pydeck_chart(
    pdk.Deck(
        layers=[arc_layer, column_layer],
        initial_view_state=view_state,
        map_style=None,
        tooltip={
            "html": "<b>{node}</b><br/>Risk: {risk_score}/100<br/>Band: {risk_band}",
            "style": {"backgroundColor": "#1f2937", "color": "white"},
        },
    ),
    use_container_width=True,
)

st.divider()


# ==============================================================================
# 12. COMPETING HYPOTHESES
# ==============================================================================

st.header("📊 Competing Hypotheses Matrix")
st.caption("Lower inconsistency = more compatible with the current selected indicators.")

weather_score = int(clamp(7 - (2 if shock == "None" else 0), 1, 10))
ops_score = int(clamp(6 - (2 if port_disruption else 0), 1, 10))
exo_score = int(clamp(8 - objective_evidence_count - (2 if shock != "None" else 0), 1, 10))

hypothesis_df = pd.DataFrame({
    "Hypothesis": [
        "H1 Weather / environmental disruption",
        "H2 Internal operational bottleneck",
        "H3 Exogenous security / geopolitical disruption",
    ],
    "Inconsistency Score": [weather_score, ops_score, exo_score],
})

h1, h2 = st.columns(2)
with h1:
    st.dataframe(hypothesis_df, hide_index=True, use_container_width=True)
with h2:
    st.bar_chart(hypothesis_df, x="Hypothesis", y="Inconsistency Score", use_container_width=True)

st.divider()


# ==============================================================================
# 13. ASSUMPTION AUDIT TRAIL
# ==============================================================================

st.header("🧾 Assumption & Audit Trail")

audit_df = pd.DataFrame({
    "Parameter": [
        "Node",
        "Fleet / vessel value",
        "Cargo value",
        "Ships exposed",
        "Daily delay cost / ship",
        "Threat severity",
        "Expected disruption",
        "Insurance premium assumption",
        "Scenario shock",
        "Analyst confidence",
        "Management risk appetite",
        "Cost priority",
        "Risk priority",
        "Delay priority",
        "Management selected decision",
        "Intelligence mode",
        "GDELT state",
        "Analyst-entered event",
        "Manual event severity",
        "Manual source confidence",
        "Calculated risk score",
        "Recommended action",
    ],
    "Value": [
        current_node,
        money(asset_exposure),
        money(cargo_value),
        str(ships_exposed),
        money(daily_delay_cost),
        f"{threat_severity}/100",
        f"{expected_disruption_days} day(s)",
        f"{assumed_premium_rate:.1%}",
        shock,
        analyst_confidence,
        risk_appetite,
        f"{cost_weight:.0%}",
        f"{risk_weight:.0%}",
        f"{delay_weight:.0%}",
        user_decision,
        intelligence_mode,
        gdelt_state,
        manual_event,
        f"{manual_event_severity}/100" if manual_event != "No additional event" else "N/A",
        manual_source_confidence if manual_event != "No additional event" else "N/A",
        f"{risk_score}/100 ({band})",
        recommended_action,
    ],
})

st.dataframe(audit_df, hide_index=True, use_container_width=True)

csv_bytes = audit_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇ Download scenario audit trail (CSV)",
    data=csv_bytes,
    file_name="cora_scenario_audit_trail.csv",
    mime="text/csv",
)

st.divider()


# ==============================================================================
# 14. METHODOLOGY / LIMITATIONS
# ==============================================================================

with st.expander("ℹ️ Methodology, limitations and responsible use"):
    st.markdown(
        """
        **What CORA does**
        - combines configurable business exposure with open-source signals;
        - applies transparent scenario heuristics;
        - compares three decision options: continue, hold, reroute;
        - allows user-selected risk appetite and decision priorities;
        - records session-based Decision History and stress-test results;
        - exposes evidence, assumptions and confidence rather than hiding them.

        **What CORA does not do**
        - it does not predict attacks;
        - it does not provide live insurer quotations;
        - it does not establish causality from headline sentiment;
        - it does not replace AIS, port, security, legal, insurance or operational verification.

        **Model status**
        - research / portfolio prototype;
        - scenario outputs are illustrative and should not be used as operational instructions.
        """
    )

st.caption(
    f"Developed by Mohd Khairul Ridhuan bin Mohd Fadzil © 2026 | "
    f"Last session render: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | "
    "Project CORA V3 — interactive research decision-support prototype."
)
