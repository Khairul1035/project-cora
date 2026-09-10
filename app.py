from pathlib import Path

code = r'''import streamlit as st
import requests
from textblob import TextBlob
import pandas as pd
import pydeck as pdk

# ==============================================================================
# PROJECT CORA — Corporate Operations & Risk Analytics
# Revised for: syntax stability, API correctness, transparent heuristics,
# graceful fallbacks, and clearer enterprise presentation.
# ==============================================================================

st.set_page_config(
    page_title="Project CORA | Risk Analytics",
    page_icon="🚢",
    layout="wide",
)

st.title("🚢 Project CORA: Corporate Operations & Risk Analytics")

st.markdown("### **Lead Author & Independent Researcher**")
st.subheader("👨‍💻 Mohd Khairul Ridhuan bin Mohd Fadzil")
st.markdown(
    "*Specialization: Structured Analytic Techniques (SAT), alternative risk "
    "ingestion, cognitive-bias mitigation, and geospatial risk visualization.*"
)
st.caption(
    "Prototype analytical dashboard | Open-source intelligence inputs | "
    "Decision-support use only"
)
st.divider()


# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

NODE_CONFIG = {
    "Red Sea / Bab al-Mandab": {
        "button": "🔴 Node A: Red Sea / Bab al-Mandab",
        "gdelt_keyword": '"Bab al-Mandab" (attack OR crisis OR shipping OR vessel)',
        "wolfram_query": "distance from Suez Canal to Bab el Mandeb",
        "base_delay_days": 4.5,
        "asset_exposure": 15_000_000,
        "daily_delay_cost": 45_000,
        "node_lat": 12.5833,
        "node_lon": 43.3333,
        "origin_lat": 29.9667,
        "origin_lon": 32.5500,
        "cached_spatial_metric": "≈ 2,210 km (cached baseline)",
    },
    "Strait of Hormuz": {
        "button": "🟡 Node B: Strait of Hormuz",
        "gdelt_keyword": '"Strait of Hormuz" (military OR tanker OR shipping OR attack)',
        "wolfram_query": "width of Strait of Hormuz",
        "base_delay_days": 3.5,
        "asset_exposure": 22_000_000,
        "daily_delay_cost": 60_000,
        "node_lat": 26.5667,
        "node_lon": 56.2500,
        "origin_lat": 25.0109,
        "origin_lon": 55.0617,  # Jebel Ali vicinity
        "cached_spatial_metric": "≈ 39 km at narrowest navigable area (cached baseline)",
    },
    "Malacca Strait": {
        "button": "🟢 Node C: Malacca Strait",
        "gdelt_keyword": '"Strait of Malacca" (piracy OR shipping OR vessel OR disruption)',
        "wolfram_query": "length of Strait of Malacca",
        "base_delay_days": 1.5,
        "asset_exposure": 8_000_000,
        "daily_delay_cost": 25_000,
        "node_lat": 4.0000,
        "node_lon": 99.0000,
        "origin_lat": 1.2644,
        "origin_lon": 103.8400,  # Singapore port vicinity
        "cached_spatial_metric": "≈ 800 km (cached baseline)",
    },
}

REQUEST_TIMEOUT = 8
DEFAULT_HEADLINE = (
    "No recent matching headline was returned by the configured open-data query."
)
DEFAULT_SOURCE = "https://www.gdeltproject.org/"


# ==============================================================================
# 2. NETWORK HELPERS
# ==============================================================================

@st.cache_data(ttl=900, show_spinner=False)
def fetch_wolfram_short_answer(query: str, app_id: str):
    """
    Retrieve a concise textual answer from the Wolfram|Alpha Short Answers API.

    Returns:
        tuple[str | None, str | None]: (answer, error_message)
    """
    if not app_id:
        return None, "Wolfram AppID is not configured."

    url = "https://api.wolframalpha.com/v1/result"
    params = {
        "appid": app_id,
        "i": query,
        "units": "metric",
    }

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        answer = response.text.strip()
        if not answer:
            return None, "Wolfram returned an empty response."

        return answer, None

    except requests.RequestException as exc:
        return None, f"Wolfram request failed: {exc}"


@st.cache_data(ttl=900, show_spinner=False)
def fetch_gdelt_latest(keyword: str):
    """
    Retrieve the newest matching GDELT DOC 2.0 article within the last 15 minutes.

    Returns:
        tuple[str, str, str | None]: (headline, source_url, error_message)
    """
    url = "https://api.gdeltproject.org/api/v2/doc/doc"

    params = {
        "query": keyword,
        "mode": "artlist",
        "format": "json",
        "maxrecords": 10,
        "timespan": "15min",
        "sort": "datedesc",
    }

    headers = {
        "User-Agent": "Project-CORA/1.0 (research decision-support prototype)"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

        articles = payload.get("articles", [])
        if not articles:
            return DEFAULT_HEADLINE, DEFAULT_SOURCE, None

        article = articles[0]
        headline = article.get("title") or DEFAULT_HEADLINE
        source_url = article.get("url") or DEFAULT_SOURCE

        return headline, source_url, None

    except (requests.RequestException, ValueError) as exc:
        return DEFAULT_HEADLINE, DEFAULT_SOURCE, f"GDELT request failed: {exc}"


def sentiment_polarity(text: str) -> float:
    """Return TextBlob polarity, falling back safely to 0.0."""
    try:
        return float(TextBlob(text).sentiment.polarity)
    except Exception:
        return 0.0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


# ==============================================================================
# 3. ACTIVE NODE SELECTION
# ==============================================================================

st.write("### 📍 Active Maritime Risk Node")
st.caption(
    "Select a commercial maritime chokepoint. The dashboard refreshes the "
    "open-source query, risk indicators, financial exposure, and map."
)

if "selected_node" not in st.session_state:
    st.session_state.selected_node = "Red Sea / Bab al-Mandab"

button_cols = st.columns(3)

for col, (node_name, config) in zip(button_cols, NODE_CONFIG.items()):
    if col.button(config["button"], use_container_width=True):
        st.session_state.selected_node = node_name

current_node = st.session_state.selected_node
cfg = NODE_CONFIG[current_node]

st.info(f"**Selected node:** {current_node}")


# ==============================================================================
# 4. LIVE / CACHED DATA INGESTION
# ==============================================================================

st.write("### 🌐 Open-Source Data Ingestion")

try:
    WOLFRAM_APP_ID = st.secrets.get("WOLFRAM_APP_ID", "")
except Exception:
    WOLFRAM_APP_ID = ""

wolfram_answer, wolfram_error = fetch_wolfram_short_answer(
    cfg["wolfram_query"],
    WOLFRAM_APP_ID,
)

spatial_metric = wolfram_answer or cfg["cached_spatial_metric"]

live_headline, live_source, gdelt_error = fetch_gdelt_latest(
    cfg["gdelt_keyword"]
)

col_data_1, col_data_2 = st.columns(2)

col_data_1.info(
    f"📍 **Spatial reference**  \n"
    f"Query: `{cfg['wolfram_query']}`  \n"
    f"Result: **{spatial_metric}**"
)

col_data_2.success(
    f"📡 **GDELT latest matching article**  \n"
    f"[Open source article]({live_source})"
)

st.warning(f"📰 **Latest matching headline:** “{live_headline}”")

with st.expander("Data-source health"):
    if wolfram_error:
        st.warning(
            f"{wolfram_error} Using the configured cached spatial baseline instead."
        )
    else:
        st.success("Wolfram spatial query returned successfully.")

    if gdelt_error:
        st.warning(gdelt_error)
    else:
        st.success("GDELT query completed successfully.")

    st.caption(
        "GDELT availability and matching volume vary by query and time window. "
        "A lack of returned articles does not prove the absence of real-world risk."
    )

st.divider()


# ==============================================================================
# 5. ANALYTICAL HEURISTICS & FINANCIAL EXPOSURE
# ==============================================================================

st.header("🧠 Analytical Signals & Financial Exposure")

sentiment_score = sentiment_polarity(live_headline)

# IMPORTANT:
# Headline sentiment is used only as a weak narrative signal.
# It is NOT treated as proof of operational disruption or hostile action.
negative_signal = sentiment_score < -0.05
strong_negative_signal = sentiment_score < -0.25

# Simple prototype risk score: 0–100.
# Chokepoint baseline + headline sentiment contribution.
node_baseline = {
    "Red Sea / Bab al-Mandab": 55,
    "Strait of Hormuz": 45,
    "Malacca Strait": 25,
}[current_node]

sentiment_component = max(0.0, -sentiment_score) * 35
risk_score = int(round(clamp(node_baseline + sentiment_component, 0, 100)))

if risk_score >= 70:
    risk_band = "HIGH"
elif risk_score >= 45:
    risk_band = "ELEVATED"
else:
    risk_band = "MODERATE"

# Scenario assumptions — explicitly labelled, not represented as market quotes.
assumed_premium_rate = 0.075 if risk_score >= 70 else 0.035 if risk_score >= 45 else 0.015
calculated_premium = cfg["asset_exposure"] * assumed_premium_rate

if risk_score >= 70:
    projected_days_delayed = max(1, round(cfg["base_delay_days"] * 2.0))
elif risk_score >= 45:
    projected_days_delayed = max(1, round(cfg["base_delay_days"]))
else:
    projected_days_delayed = 1

total_delay_impact = projected_days_delayed * cfg["daily_delay_cost"]

col_m1, col_m2, col_m3, col_m4 = st.columns(4)

col_m1.metric(
    "Narrative polarity",
    f"{sentiment_score:.2f}",
    "Negative signal" if negative_signal else "Neutral / positive",
)

col_m2.metric(
    "Prototype risk score",
    f"{risk_score}/100",
    risk_band,
)

col_m3.metric(
    "Scenario war-risk premium",
    f"USD {calculated_premium:,.0f}",
    f"{assumed_premium_rate:.1%} assumption",
)

col_m4.metric(
    "Scenario delay exposure",
    f"USD {total_delay_impact:,.0f}",
    f"{projected_days_delayed} day(s)",
)

with st.expander("ℹ️ How to interpret this model"):
    st.markdown(
        """
- **Headline polarity** is a narrative indicator, not an event-verification engine.
- **Risk score** is a transparent prototype heuristic combining a node baseline
  with negative headline sentiment.
- **Premium and delay values are scenario assumptions**, not live insurance quotes
  or forecasts.
- A professional deployment should triangulate multiple independent variables
  such as AIS vessel movement, port congestion, verified security incidents,
  weather, NOTAM/NAVTEX notices, sanctions, insurance-market data, and commodity
  or freight indicators.
        """
    )

st.divider()


# ==============================================================================
# 6. COMPETING HYPOTHESES MATRIX
# ==============================================================================

st.header("📊 Competing Hypotheses Matrix")

# These scores are illustrative analytical-consistency scores.
# Higher = greater inconsistency with currently observed prototype signals.
h1_weather_inconsistency = 6 if risk_score >= 70 else 3 if risk_score >= 45 else 1
h2_operational_inconsistency = 5 if risk_score >= 70 else 3 if risk_score >= 45 else 2
h3_exogenous_inconsistency = 2 if risk_score >= 70 else 4 if risk_score >= 45 else 7

chart_data = pd.DataFrame(
    {
        "Hypothesis": [
            "Weather disruption (H1)",
            "Internal operational bottleneck (H2)",
            "Exogenous security/geopolitical disruption (H3)",
        ],
        "Inconsistency Score": [
            h1_weather_inconsistency,
            h2_operational_inconsistency,
            h3_exogenous_inconsistency,
        ],
    }
)

col_c_left, col_c_right = st.columns(2)

with col_c_left:
    st.write("#### Numerical assessment")
    st.caption(
        "Lower inconsistency means the hypothesis is more compatible with the "
        "current prototype signals. It does not establish causality."
    )
    st.dataframe(
        chart_data,
        hide_index=True,
        use_container_width=True,
    )

with col_c_right:
    st.write("#### Comparative hypothesis view")
    st.bar_chart(
        data=chart_data,
        x="Hypothesis",
        y="Inconsistency Score",
        use_container_width=True,
    )

st.divider()


# ==============================================================================
# 7. 3D GEOSPATIAL VISUALIZATION
# ==============================================================================

st.header("🌐 Geospatial Risk Visualization")
st.caption(
    "Illustrative route arc and risk column. Height reflects the prototype risk "
    "score, not a measured physical threat radius."
)

threat_elevation = max(1_000.0, float(risk_score) * 25_000.0)

map_data = pd.DataFrame(
    {
        "from_lat": [cfg["origin_lat"]],
        "from_lon": [cfg["origin_lon"]],
        "to_lat": [cfg["node_lat"]],
        "to_lon": [cfg["node_lon"]],
        "risk_score": [risk_score],
        "threat_elevation": [threat_elevation],
        "node": [current_node],
        "risk_band": [risk_band],
    }
)

view_state = pdk.ViewState(
    latitude=cfg["node_lat"],
    longitude=cfg["node_lon"],
    zoom=4,
    pitch=50,
    bearing=0,
)

arc_layer = pdk.Layer(
    "ArcLayer",
    data=map_data,
    get_source_position="[from_lon, from_lat]",
    get_target_position="[to_lon, to_lat]",
    get_source_color=[0, 180, 255, 180],
    get_target_color=[255, 80, 80, 220],
    get_width=5,
    pickable=True,
)

column_layer = pdk.Layer(
    "ColumnLayer",
    data=map_data,
    get_position="[to_lon, to_lat]",
    get_elevation="threat_elevation",
    elevation_scale=1,
    radius=50_000,
    get_fill_color=[255, 80, 80, 160],
    pickable=True,
    auto_highlight=True,
)

deck = pdk.Deck(
    layers=[arc_layer, column_layer],
    initial_view_state=view_state,
    map_style=None,
    tooltip={
        "html": (
            "<b>{node}</b><br/>"
            "Prototype risk score: {risk_score}/100<br/>"
            "Risk band: {risk_band}"
        ),
        "style": {"backgroundColor": "steelblue", "color": "white"},
    },
)

st.pydeck_chart(deck, use_container_width=True)

st.divider()


# ==============================================================================
# 8. PRESCRIPTIVE DECISION-SUPPORT PLAYBOOK
# ==============================================================================

st.header("⚡ Decision-Support Playbook")

if risk_score >= 70:
    st.error(
        f"🚨 HIGH-RISK PROTOTYPE SIGNAL AT {current_node.upper()}"
    )

    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown(
            f"""
#### 🗺️ 1. Operational review
- Pause **new discretionary exposure** pending verification.
- Obtain independent confirmation from operational and security sources.
- Compare normal route against contingency-routing options.
- Model an indicative delay of approximately **{projected_days_delayed} day(s)**.
            """
        )

    with col_p2:
        st.markdown(
            f"""
#### 🛡️ 2. Financial and governance review
- Revalidate war-risk insurance terms with the actual underwriter or broker.
- Quantify scenario exposure against the current asset value of
  **USD {cfg['asset_exposure']:,.0f}**.
- Preserve the underlying sources and assumptions for auditability.
- Escalate the decision to the appropriate risk owner before material rerouting.
            """
        )

elif risk_score >= 45:
    st.warning(
        f"⚠️ ELEVATED PROTOTYPE SIGNAL AT {current_node.upper()}"
    )
    st.markdown(
        """
- Increase monitoring frequency.
- Verify the headline against at least one independent source.
- Review contingency routing and insurance clauses.
- Avoid treating the current signal as sufficient evidence for a major operational decision.
        """
    )

else:
    st.success(
        f"✅ MODERATE PROTOTYPE SIGNAL AT {current_node.upper()}"
    )
    st.markdown(
        """
- Continue baseline monitoring.
- Maintain normal escalation thresholds.
- Reassess if verified operational, security, weather, or navigation indicators change.
        """
    )

st.divider()

st.caption(
    "Developed by Mohd Khairul Ridhuan bin Mohd Fadzil © 2026 | "
    "Project CORA is a research/portfolio decision-support prototype. "
    "Outputs are not operational, legal, insurance, or investment advice."
)
'''

path = Path("/mnt/data/project_cora_fixed.py")
path.write_text(code, encoding="utf-8")

# Syntax check without importing external dependencies.
import py_compile
py_compile.compile(str(path), doraise=True)

req = """streamlit
requests
textblob
pandas
pydeck
"""
Path("/mnt/data/requirements.txt").write_text(req, encoding="utf-8")

print("Created:", path)
print("Syntax check: PASSED")
print("Lines:", len(code.splitlines()))
