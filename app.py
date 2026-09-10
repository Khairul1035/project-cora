import streamlit as st
import requests
from textblob import TextBlob
import pandas as pd
import pydeck as pdk
from datetime import datetime, timezone

# ==============================================================================
# PROJECT CORA V2 — Maritime Crisis Decision Simulator
# ============================================================================

st.set_page_config(
    page_title="Project CORA | Maritime Crisis Decision Simulator",
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
        "wolfram_query": "distance from Suez Canal to Bab el Mandeb",
        "baseline_risk": 55,
        "default_delay_days": 5,
        "default_asset": 15_000_000,
        "default_daily_delay": 45_000,
        "node_lat": 12.5833,
        "node_lon": 43.3333,
        "origin_lat": 29.9667,
        "origin_lon": 32.5500,
        "cached_spatial_metric": "≈ 2,210 km (cached baseline)",
    },
    "Strait of Hormuz": {
        "gdelt_keyword": '"Strait of Hormuz" (military OR tanker OR shipping OR attack OR seizure)',
        "wolfram_query": "width of Strait of Hormuz",
        "baseline_risk": 45,
        "default_delay_days": 4,
        "default_asset": 22_000_000,
        "default_daily_delay": 60_000,
        "node_lat": 26.5667,
        "node_lon": 56.2500,
        "origin_lat": 25.0109,
        "origin_lon": 55.0617,
        "cached_spatial_metric": "≈ 39 km (cached baseline)",
    },
    "Malacca Strait": {
        "gdelt_keyword": '"Strait of Malacca" (piracy OR shipping OR vessel OR disruption OR collision)',
        "wolfram_query": "length of Strait of Malacca",
        "baseline_risk": 25,
        "default_delay_days": 2,
        "default_asset": 8_000_000,
        "default_daily_delay": 25_000,
        "node_lat": 4.0000,
        "node_lon": 99.0000,
        "origin_lat": 1.2644,
        "origin_lon": 103.8400,
        "cached_spatial_metric": "≈ 800 km (cached baseline)",
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

@st.cache_data(ttl=900, show_spinner=False)
def fetch_gdelt_latest(keyword: str):
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": keyword,
        "mode": "artlist",
        "format": "json",
        "maxrecords": 10,
        "timespan": "15min",
        "sort": "datedesc",
    }
    headers = {"User-Agent": "Project-CORA/2.0 research prototype"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        articles = payload.get("articles", [])

        if not articles:
            return DEFAULT_HEADLINE, DEFAULT_SOURCE, None

        article = articles[0]
        return (
            article.get("title") or DEFAULT_HEADLINE,
            article.get("url") or DEFAULT_SOURCE,
            None,
        )
    except (requests.RequestException, ValueError, TypeError) as exc:
        return DEFAULT_HEADLINE, DEFAULT_SOURCE, f"GDELT request failed: {exc}"


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
st.subheader("Maritime Crisis Decision Simulator")
st.caption(
    "A transparent OSINT-enabled decision-support prototype for comparing maritime crisis responses."
)
st.markdown("**Principal Investigator:** Mohd Khairul Ridhuan bin Mohd Fadzil")
st.divider()


# ==============================================================================
# 4. SIDEBAR — CONTROL ROOM
# ==============================================================================

with st.sidebar:
    st.header("🎛️ CORA Control Room")

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

    shock = st.selectbox("Scenario shock", list(SHOCKS.keys()))
    shock_cfg = SHOCKS[shock]

    st.markdown("### Evidence controls")
    verified_incident = st.checkbox("Verified security incident", value=False)
    navigation_disruption = st.checkbox("Navigation / AIS anomaly", value=False)
    port_disruption = st.checkbox("Port / channel disruption", value=False)
    insurer_confirmation = st.checkbox("Insurance / broker confirmation", value=False)

    run = st.button("▶ Run / Refresh Scenario", use_container_width=True, type="primary")

    st.caption("Inputs recalculate automatically. The button is provided as an explicit control-room action.")


# ==============================================================================
# 5. LIVE DATA
# ==============================================================================

try:
    WOLFRAM_APP_ID = st.secrets.get("WOLFRAM_APP_ID", "")
except Exception:
    WOLFRAM_APP_ID = ""

headline, source_url, gdelt_error = fetch_gdelt_latest(cfg["gdelt_keyword"])
headline_sentiment = polarity(headline)
spatial_answer, wolfram_error = fetch_wolfram(cfg["wolfram_query"], WOLFRAM_APP_ID)
spatial_metric = spatial_answer or cfg["cached_spatial_metric"]

# ==============================================================================
# 6. RISK ENGINE
# ==============================================================================

# Transparent prototype scoring, not a probability model.
headline_component = max(0, -headline_sentiment) * 15
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
confidence_score = int(clamp(confidence_numeric + objective_evidence_count * 4, 0, 95))

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

# Weighted decision score: lower is better
scenario_df["Decision Score"] = (
    (scenario_df["Estimated Cost (USD)"] / max(scenario_df["Estimated Cost (USD)"].max(), 1)) * 45
    + (scenario_df["Residual Risk Score"] / 100) * 45
    + (scenario_df["Indicative Delay (days)"] / max(scenario_df["Indicative Delay (days)"].max(), 1)) * 10
)
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
# 8. DECISION COMPARISON
# ==============================================================================

st.header("🧭 A/B/C Decision Comparison")
st.caption(
    "Change any sidebar assumption and the three management options recalculate immediately. "
    "The recommendation is a transparent prototype heuristic, not operational advice."
)

show_df = scenario_df[[
    "Decision",
    "Estimated Cost (USD)",
    "Indicative Delay (days)",
    "Residual Risk Score",
    "Risk Band",
]].copy()
show_df["Estimated Cost (USD)"] = show_df["Estimated Cost (USD)"].round(0).astype(int)

st.dataframe(
    show_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Estimated Cost (USD)": st.column_config.NumberColumn(format="USD %,.0f"),
        "Residual Risk Score": st.column_config.ProgressColumn(min_value=0, max_value=100),
    },
)

c1, c2, c3 = st.columns(3)
for col, (_, row) in zip([c1, c2, c3], scenario_df.iterrows()):
    with col:
        st.subheader(row["Decision"])
        st.metric("Estimated cost", money(row["Estimated Cost (USD)"]))
        st.metric("Residual risk", f"{int(row['Residual Risk Score'])}/100", row["Risk Band"])
        st.metric("Delay", f"{int(row['Indicative Delay (days)'])} day(s)")

st.info(
    f"**Prototype recommendation:** {recommended_action}. "
    "This option currently has the lowest combined cost–risk–delay decision score under your assumptions."
)

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

if headline_sentiment < -0.05:
    for_evidence.append(f"Negative headline polarity ({headline_sentiment:.2f})")
else:
    against_evidence.append(f"Headline polarity is not materially negative ({headline_sentiment:.2f})")

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

st.divider()


# ==============================================================================
# 10. LIVE OSINT PANEL
# ==============================================================================

st.header("🌐 Open-Source Intelligence Inputs")
os1, os2 = st.columns([2, 1])

with os1:
    st.markdown("#### Latest matching GDELT headline")
    st.write(f"**{headline}**")
    st.link_button("Open source article", source_url)
    st.caption(f"Headline polarity: {headline_sentiment:.2f}")
    if gdelt_error:
        st.warning(gdelt_error)

with os2:
    st.markdown("#### Spatial reference")
    st.write(f"**{spatial_metric}**")
    st.caption(cfg["wolfram_query"])
    if wolfram_error:
        st.info("Using cached spatial baseline because live Wolfram data is unavailable.")

st.caption(
    "GDELT and Wolfram are supporting inputs only. Lack of an article or API response does not establish absence of risk."
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
    "Project CORA V2 — research decision-support prototype."
)
